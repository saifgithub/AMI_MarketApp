"""Unit tests for the portable `trading_math` library (CR046).

Pure math, tested in isolation from the app — the library takes primitives and
returns primitives, so these tests need no fixtures, no I/O, no mandate objects.
Covers what ships today: `risk` (drawdown contribution) and `sizing` (per-risk-
tier caps). Indicators land here after the CR046 build-vs-adopt decision (D1).
"""

from __future__ import annotations

import pytest

from app.trading_math import (
    DEFAULT_RISK_TIER_CAPS,
    SINGLE_NAME_ABSOLUTE_CAP_PCT,
    clamp_size,
    drawdown_contribution,
    drawdown_pct,
    dividend_yield_pct,
    fcf_yield_pct,
    multiple_compression_downside,
    net_cash_millions,
    net_position_phrase,
    position_pct,
    ratio_to_pct,
    risk_debator_sizes,
    risk_reward,
    risk_tier_cap,
    rr_is_coherent,
    rsi,
    rsi_tone,
    shares_for_size,
    sma,
    total_value,
    trade_asymmetry,
)

# ── indicators.rsi / sma / rsi_tone ──────────────────────────────────────────


def test_rsi_needs_period_plus_one_closes():
    assert rsi([1.0, 2.0, 3.0], period=14) is None


def test_rsi_pure_uptrend_hits_ceiling():
    closes = [float(i) for i in range(1, 21)]  # strictly increasing → no losses
    assert rsi(closes) == 100.0


def test_rsi_is_cutlers_simple_average_not_wilder():
    # 14 up-moves of +1 then one down-move of -2: simple-average RSI is a clean,
    # Wilder-independent value. avg_gain = 13/14, avg_loss = 2/14 → RS = 6.5.
    closes = [float(i) for i in range(15)]  # 0..14, fourteen +1 deltas
    closes.append(closes[-1] - 2.0)  # one -2 delta
    got = rsi(closes)
    assert got is not None
    assert got == pytest.approx(100 - 100 / (1 + 6.5))


def test_rsi_tone_bands():
    assert rsi_tone(75) == "overbought"
    assert rsi_tone(25) == "oversold"
    assert rsi_tone(50) == "neither overbought nor oversold"


def test_sma_window():
    assert sma([10.0, 20.0, 30.0], 3) == 20.0
    assert sma([10.0, 20.0], 3) is None


# ── risk.drawdown_contribution ───────────────────────────────────────────────


def test_drawdown_contribution_is_size_times_stop_distance():
    dc = drawdown_contribution(size_pct=5.0, entry=100.0, stop=90.0)
    assert dc is not None
    assert dc.stop_distance_pct == pytest.approx(10.0)
    # The DEF066 point: 5% size × 10% stop = 0.5 pts of drawdown, NOT 10.
    assert dc.contribution_pts == pytest.approx(0.5)


def test_drawdown_contribution_rejects_nonsense():
    assert drawdown_contribution(0, 100, 90) is None  # no size
    assert drawdown_contribution(5, 0, 0) is None  # no entry
    assert drawdown_contribution(5, 100, 100) is None  # stop == entry
    assert drawdown_contribution(5, 100, 110) is None  # stop above entry


# ── sizing.risk_tier_cap / clamp_size ────────────────────────────────────────


def test_default_policy_matches_enforced_ceilings():
    assert DEFAULT_RISK_TIER_CAPS == {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}
    for score, cap in DEFAULT_RISK_TIER_CAPS.items():
        assert risk_tier_cap(score) == cap


def test_risk_tier_cap_is_total_for_out_of_range_scores():
    assert risk_tier_cap(0) == risk_tier_cap(1)  # clamps down to lowest tier
    assert risk_tier_cap(9) == risk_tier_cap(5)  # clamps up to highest tier


def test_risk_tier_cap_accepts_a_custom_table():
    assert risk_tier_cap(2, caps={1: 10.0, 2: 20.0}) == 20.0


def test_risk_tier_cap_total_for_sparse_custom_tables():
    # CR046 O1: a sparse table + an intermediate score snaps to the nearest present
    # key (ties round down) instead of KeyError-ing — matters for reuse elsewhere.
    sparse = {1: 5.0, 5: 25.0}
    assert risk_tier_cap(1, caps=sparse) == 5.0
    assert risk_tier_cap(3, caps=sparse) == 5.0  # equidistant → rounds down to tier 1
    assert risk_tier_cap(4, caps=sparse) == 25.0  # nearest present key is 5
    assert risk_tier_cap(9, caps=sparse) == 25.0


def test_every_tier_cap_stays_under_the_absolute_backstop():
    assert all(c <= SINGLE_NAME_ABSOLUTE_CAP_PCT for c in DEFAULT_RISK_TIER_CAPS.values())


def test_clamp_size_lowers_to_cap_but_leaves_smaller_sizes():
    assert clamp_size(40.0, 4.5) == 4.5
    assert clamp_size(2.0, 4.5) == 2.0


# ── sizing.risk_debator_sizes (M03 spread) ───────────────────────────────────


def test_risk_debator_sizes_spread_around_trader():
    s = risk_debator_sizes(3.0)
    assert (s.aggressive, s.conservative, s.neutral) == (5.0, 1.5, 3.0)


def test_risk_debator_aggressive_never_exceeds_backstop():
    # A large trader size + the +2 push must still be capped by the absolute backstop.
    s = risk_debator_sizes(49.5)
    assert s.aggressive == SINGLE_NAME_ABSOLUTE_CAP_PCT  # 51.5 -> 50.0
    assert s.aggressive <= SINGLE_NAME_ABSOLUTE_CAP_PCT


def test_risk_debator_conservative_floored_at_token_size():
    s = risk_debator_sizes(1.0)  # 1.0 - 1.5 = -0.5 -> floored
    assert s.conservative == 0.5


# ── valuation.multiple_compression_downside (M07) ────────────────────────────


def test_multiple_compression_downside_is_delta_over_pe():
    # A 10-pt compression from 20x -> 10x halves the price: 50% downside.
    assert multiple_compression_downside(20, 10) == 50.0
    # From 55x, a 10-pt compression is ~18%, NOT the ~34% the old inline
    # `int(pe/(pe+10)*100-50)` formula printed (DEF075).
    assert multiple_compression_downside(55, 10) == pytest.approx(18.2, abs=0.1)


def test_multiple_compression_downside_beats_the_old_broken_formula():
    # RED-proof for DEF075: the replaced formula, evaluated here, disagrees with
    # the correct one — so a caller wired to the old code fails this class.
    for pe in (12.0, 20.0, 34.2, 55.0):
        old = int(pe / (pe + 10) * 100 - 50)  # the buggy inline expression
        correct = multiple_compression_downside(pe, 10)
        assert correct is not None
        assert round(correct) != old or pe == 0  # never coincidentally equal here


def test_multiple_compression_downside_capped_and_guarded():
    assert multiple_compression_downside(8, 20) == 100.0  # can't fall past 100%
    assert multiple_compression_downside(0, 10) is None  # no multiple
    assert multiple_compression_downside(-5, 10) is None  # loss-making
    assert multiple_compression_downside(20, 0) is None  # no compression


# ── valuation unit conversions (M04) ─────────────────────────────────────────


def test_ratio_to_pct_rounding_modes():
    assert ratio_to_pct(0.253) == 25  # whole percent (rev growth, margin)
    assert ratio_to_pct(0.0512, decimals=1) == 5.1  # one-dp percent (fcf yield)
    assert ratio_to_pct(None) is None


def test_fcf_yield_pct():
    assert fcf_yield_pct(5.0e9, 1.0e11) == 5.0
    assert fcf_yield_pct(1.0e9, 0) is None
    assert fcf_yield_pct(None, 1.0e11) is None


def test_net_cash_millions_and_phrase():
    assert net_cash_millions(80_000_000_000, 42_000_000_000) == 38_000
    assert net_position_phrase(38_000) == "net cash $38000M"
    # Negative net cash reads as net debt, not "$-42000M".
    assert net_cash_millions(10_000_000_000, 52_000_000_000) == -42_000
    assert net_position_phrase(-42_000) == "net debt $42000M"
    assert net_position_phrase(None) is None


def test_dividend_yield_pct_is_pass_through_on_pinned_yfinance():
    # yfinance 1.5.1 returns dividendYield already as a percent (verified live:
    # KO 2.58, AAPL 0.33). Pass-through round, NOT a x100.
    assert dividend_yield_pct(2.58) == 2.58
    assert dividend_yield_pct(0.33) == 0.33
    assert dividend_yield_pct(None) is None


# ── trade.risk_reward / trade_asymmetry / rr_is_coherent (M06/M08) ───────────


def test_risk_reward_long_setup():
    # entry 100, stop 94, target 113 -> reward 13 / risk 6 = 2.2
    assert risk_reward(100, 94, 113) == 2.2


def test_risk_reward_rejects_non_long_setups():
    assert risk_reward(100, 100, 113) is None  # stop == entry (no risk)
    assert risk_reward(100, 94, 100) is None  # target == entry (no reward)
    assert risk_reward(100, 105, 113) is None  # stop above entry
    assert risk_reward(None, 94, 113) is None


def test_trade_asymmetry_percentages():
    a = trade_asymmetry(100, 94, 113)
    assert a is not None
    assert (a.upside_pct, a.downside_pct) == (13.0, 6.0)


def test_trade_asymmetry_requires_ordered_levels():
    assert trade_asymmetry(100, 105, 113) is None  # stop above entry
    assert trade_asymmetry(100, 94, 90) is None  # target below entry


def test_rr_is_coherent_flags_a_lie():
    # Levels imply 2.2:1; a Trader stating "3:1" is not coherent.
    assert rr_is_coherent(100, 94, 113, stated_rr=2.2) is True
    assert rr_is_coherent(100, 94, 113, stated_rr=3.0) is False
    assert rr_is_coherent(100, 94, 113, stated_rr=None) is False


# ── portfolio math (M05) ─────────────────────────────────────────────────────


def test_total_value_and_drawdown_pct():
    # 10k cash + 5 shares @ $200 = 11k value; up on 10k start -> 0 drawdown.
    assert total_value(10_000, [(5, 200.0)]) == 11_000
    # Down to 8k on a 10k start -> 20% drawdown; up stays 0.
    assert drawdown_pct(10_000, 8_000) == 20.0
    assert drawdown_pct(10_000, 12_000) == 0.0
    assert drawdown_pct(0, 8_000) == 0.0  # no denominator


def test_position_pct():
    assert position_pct(450, 10_000) == 4.5
    assert position_pct(450, 0) == 0.0


def test_shares_for_size():
    # 4.5% of 10k = $450; at $90 -> 5 shares.
    assert shares_for_size(10_000, 4.5, 90.0) == 5
    # A tiny non-zero size still buys at least 1 share (never a no-op).
    assert shares_for_size(10_000, 0.001, 500.0) == 1
    assert shares_for_size(10_000, 4.5, 0) == 0  # unusable price
