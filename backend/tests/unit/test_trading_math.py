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
    risk_tier_cap,
    rsi,
    rsi_tone,
    sma,
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
