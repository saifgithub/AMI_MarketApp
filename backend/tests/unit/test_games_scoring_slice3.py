"""CR109 slice 3 — pure-function tests for `games_scoring.py`'s new
constants and formulas: the achievable benchmark, the alpha->points curve,
cadence weighting, the finish stipend, the negative-TWR partial-credit
rule, the wildness index, and the "held your first picks" counterfactual.

No DB, no sim engine — every function under test here is pure. The
DB-touching orchestration (the scoring pass itself) is covered by
`test_cr109_scoring_pass.py`.

implementation_plan.md §9 test matrix items 7, 12, 28, 31, 32.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.games_scoring import (
    ALPHA_FULL,
    CADENCE_GAIN_WEIGHT,
    CADENCE_LOSS_WEIGHT,
    FEE_BPS,
    FINISH_STIPEND,
    NEGATIVE_TWR_PARTIAL_CREDIT,
    TradeLeg,
    achievable_benchmark,
    alpha_to_points,
    apply_negative_twr_partial_credit,
    cadence_period_key,
    cadence_weight,
    counterfactual_hold_first_picks_pct,
    finish_stipend,
    wildness_index,
)


# ── achievable_benchmark (§6.6.2) ──────────────────────────────────────


def test_achievable_benchmark_nets_the_one_entry_fee():
    assert FEE_BPS == 10.0  # 10 bps == 0.001 as a fraction
    assert achievable_benchmark(0.05) == pytest.approx(0.049)
    assert achievable_benchmark(0.0) == pytest.approx(-0.001)
    assert achievable_benchmark(-0.02) == pytest.approx(-0.021)


# ── alpha -> points (§6.6.1) ────────────────────────────────────────────


def test_alpha_full_constant_is_pinned():
    """Loud test the module promises — a retune is a one-line change here
    that fails until this pin is updated too."""
    assert ALPHA_FULL == 0.03


def test_alpha_to_points_convex_top_shallow_bottom():
    # +1% excess -> a=1/3 -> convex top, ~19.2
    assert alpha_to_points(0.01) == pytest.approx(19.245, abs=0.01)
    # +2% excess -> a=2/3 -> ~54.4, in the placement table's "good finish" range
    assert alpha_to_points(0.02) == pytest.approx(54.433, abs=0.01)
    # A loss is linear and shallow: -1% excess -> a=-1/3 -> -40/3
    assert alpha_to_points(-0.01) == pytest.approx(-13.333, abs=0.01)
    assert alpha_to_points(0.0) == pytest.approx(0.0)


def test_alpha_to_points_never_pays_more_than_winning_a_field_outright():
    """Test matrix item 7 / item 31 — placement's own base tops out at
    +100 for p=1.0 (design §6.2); no alpha magnitude may exceed that, and
    no loss magnitude may exceed placement's own -40 floor."""
    for huge_alpha in (0.031, 0.05, 1.0, 1_000.0):
        assert alpha_to_points(huge_alpha) == pytest.approx(100.0)
    for huge_loss in (-0.031, -0.05, -1.0, -1_000.0):
        assert alpha_to_points(huge_loss) == pytest.approx(-40.0)


# ── cadence weighting + the period key ──────────────────────────────────


def test_cadence_weight_week_is_a_noop_in_slice_3():
    assert CADENCE_GAIN_WEIGHT["week"] == 1.0
    assert CADENCE_LOSS_WEIGHT["week"] == 1.0
    assert cadence_weight("week", negative=False) == 1.0
    assert cadence_weight("week", negative=True) == 1.0


def test_cadence_weight_defaults_unknown_cadence_to_one():
    assert cadence_weight("annual", negative=False) == 1.0


def test_cadence_period_key_same_iso_week_same_key_different_week_differs():
    monday = date(2026, 8, 10)
    same_week_friday = date(2026, 8, 14)
    next_monday = date(2026, 8, 17)
    assert cadence_period_key("week", monday) == cadence_period_key(
        "week", same_week_friday,
    )
    assert cadence_period_key("week", monday) != cadence_period_key(
        "week", next_monday,
    )
    iso_year, iso_week, _ = monday.isocalendar()
    assert cadence_period_key("week", monday) == f"week:{iso_year}-W{iso_week:02d}"


# ── the finish stipend (§6.5) ────────────────────────────────────────────


def test_finish_stipend_constant_and_weekly_value():
    assert FINISH_STIPEND == 5
    assert finish_stipend("week") == 5


# ── the ×0.5 negative-TWR partial-credit rule (§6.5) ──────────────────────


def test_negative_twr_partial_credit_halves_points_only_when_twr_negative():
    assert NEGATIVE_TWR_PARTIAL_CREDIT == 0.5
    assert apply_negative_twr_partial_credit(80.0, 0.02) == pytest.approx(80.0)
    assert apply_negative_twr_partial_credit(80.0, 0.0) == pytest.approx(80.0)
    assert apply_negative_twr_partial_credit(80.0, -0.001) == pytest.approx(40.0)
    # A loss still gets halved too — the rule is symmetric in sign of points.
    assert apply_negative_twr_partial_credit(-40.0, -0.01) == pytest.approx(-20.0)


# ── the wildness index — private mirror, no scoring effect ──────────────


def test_wildness_index_concentrated_is_wilder_than_diversified():
    concentrated = wildness_index(
        holding_weights=[1.0], total_notional_traded=0.0,
        starting_capital=10_000.0, daily_returns=[],
    )
    diversified = wildness_index(
        holding_weights=[0.2, 0.2, 0.2, 0.2, 0.2], total_notional_traded=0.0,
        starting_capital=10_000.0, daily_returns=[],
    )
    assert concentrated == pytest.approx(0.45)
    assert diversified == pytest.approx(0.05)
    assert concentrated > diversified


def test_wildness_index_all_cash_book_is_not_treated_as_concentrated():
    all_cash = wildness_index(
        holding_weights=[], total_notional_traded=0.0,
        starting_capital=10_000.0, daily_returns=[],
    )
    assert all_cash == pytest.approx(0.0)


def test_wildness_index_turnover_and_volatility_raise_the_score():
    baseline = wildness_index(
        holding_weights=[0.2] * 5, total_notional_traded=0.0,
        starting_capital=10_000.0, daily_returns=[],
    )
    with_turnover = wildness_index(
        holding_weights=[0.2] * 5, total_notional_traded=50_000.0,  # 5x cap
        starting_capital=10_000.0, daily_returns=[],
    )
    with_vol = wildness_index(
        holding_weights=[0.2] * 5, total_notional_traded=0.0,
        starting_capital=10_000.0, daily_returns=[0.05, -0.05, 0.05, -0.05],
    )
    assert with_turnover > baseline
    assert with_vol > baseline


# ── the "held your first picks" counterfactual (design §10.4) ────────────


def test_counterfactual_first_picks_none_with_no_trades():
    assert counterfactual_hold_first_picks_pct([], {}, 10_000.0) is None


def test_counterfactual_first_picks_holds_day_one_ignores_later_trades():
    day1 = date(2026, 8, 10)
    day2 = date(2026, 8, 11)
    trades = [
        TradeLeg(ticker="AAPL", side="buy", quantity=10, price=100.0, opened_at=day1),
        # A later trade in a DIFFERENT name must not enter the counterfactual.
        TradeLeg(ticker="TSLA", side="buy", quantity=5, price=200.0, opened_at=day2),
    ]
    final_marks = {"AAPL": 120.0, "TSLA": 50.0}
    pct = counterfactual_hold_first_picks_pct(trades, final_marks, 10_000.0)
    # spent = 10*100 + fee(1000) = 1000 + 1.00 = 1001; leftover = 8999
    # value_at_close = 8999 + 10*120 (TSLA excluded) = 10199
    # pct = (10199/10000 - 1) * 100 = 1.99
    assert pct == pytest.approx(1.99)


def test_counterfactual_first_picks_multiple_buys_same_day_aggregate():
    day1 = date(2026, 8, 10)
    trades = [
        TradeLeg(ticker="AAPL", side="buy", quantity=5, price=100.0, opened_at=day1),
        TradeLeg(ticker="AAPL", side="buy", quantity=5, price=100.0, opened_at=day1),
    ]
    pct = counterfactual_hold_first_picks_pct(trades, {"AAPL": 100.0}, 10_000.0)
    assert pct is not None
