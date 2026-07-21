"""Guard tests for the CR054-W0d additions to `trading_math` (CR046 M09–M12).

Bond price/YTM/duration, option payoff & break-even, portfolio variance/
correlation/beta, and the hand-rolled return metrics (CAGR, max drawdown,
Sharpe) — the math the BOK's Wave-1 worked examples route through (CR054
§4.5). Pure functions checked against hand-computable textbook values, plus
the None-on-nonsense guards the library's degrade-loudly convention requires.
"""

from __future__ import annotations

import pytest

from app.trading_math import (
    beta,
    bond_price,
    bond_ytm,
    cagr_pct,
    correlation,
    covariance,
    macaulay_duration,
    max_drawdown_pct,
    modified_duration,
    option_break_even,
    option_intrinsic_value,
    option_payoff,
    portfolio_variance,
    purification_amount,
    sharia_debt_ratio,
    sharia_impermissible_income_ratio,
    sharia_liquidity_ratio,
    sharia_screen,
    sharpe_ratio,
    variance,
)

# ── bond.bond_price / bond_ytm / durations (M09) ─────────────────────────────


def test_bond_price_discount_textbook_value():
    # 5% semiannual coupon, 10y, priced at a 6% YTM — the classic $925.61.
    assert bond_price(1000, 5, 6, 10, 2) == 925.61


def test_bond_price_par_premium_discount():
    assert bond_price(1000, 5, 5, 10, 2) == 1000.0  # coupon == ytm -> par
    premium = bond_price(1000, 5, 4, 10, 2)
    assert premium is not None and premium > 1000  # ytm below coupon
    discount = bond_price(1000, 5, 6, 10, 2)
    assert discount is not None and discount < 1000  # ytm above coupon


def test_bond_price_zero_coupon():
    # Pure discounting of the face: 1000 / 1.03^20.
    assert bond_price(1000, 0, 6, 10, 2) == 553.68


def test_bond_price_rejects_nonsense():
    assert bond_price(0, 5, 6, 10, 2) is None  # no face
    assert bond_price(1000, -1, 6, 10, 2) is None  # negative coupon
    assert bond_price(1000, 5, 6, 0, 2) is None  # no maturity
    assert bond_price(1000, 5, 6, 1.3, 2) is None  # fractional periods (2.6)
    assert bond_price(1000, 5, -250, 10, 2) is None  # yield below -100%


def test_bond_ytm_round_trips_the_price():
    assert bond_ytm(925.61, 1000, 5, 10, 2) == pytest.approx(6.0, abs=0.001)
    assert bond_ytm(1000.0, 1000, 5, 10, 2) == pytest.approx(5.0, abs=0.001)


def test_bond_ytm_rejects_unattainable_prices():
    assert bond_ytm(0, 1000, 5, 10, 2) is None  # no price
    assert bond_ytm(1, 1000, 5, 10, 2) is None  # below the +1000%-yield floor
    assert bond_ytm(1e10, 1000, 5, 10, 2) is None  # above the -90%-yield cap


def test_macaulay_duration_textbook_value():
    # 5% annual coupon, 3y, at par: the classic 2.86-year duration.
    assert macaulay_duration(1000, 5, 5, 3, 1) == 2.86


def test_macaulay_duration_of_zero_coupon_is_maturity():
    assert macaulay_duration(1000, 0, 6, 10, 2) == 10.0


def test_modified_duration_divides_by_gross_period_yield():
    # 2.85941 / 1.05 = 2.72.
    assert modified_duration(1000, 5, 5, 3, 1) == 2.72


def test_durations_reject_nonsense():
    assert macaulay_duration(1000, 5, 6, 0, 2) is None
    assert macaulay_duration(1000, 5, -250, 3, 1) is None
    assert modified_duration(0, 5, 6, 10, 2) is None


# ── option payoff / break-even (M10) ─────────────────────────────────────────


def test_call_payoff_and_break_even():
    assert option_payoff("call", 100, 120, 5) == 15.0  # ITM: 20 intrinsic - 5
    assert option_payoff("call", 100, 90, 5) == -5.0  # max loss = premium
    assert option_break_even("call", 100, 5) == 105.0


def test_put_payoff_and_break_even():
    assert option_payoff("put", 100, 80, 5) == 15.0
    assert option_payoff("put", 100, 110, 5) == -5.0
    assert option_break_even("put", 100, 5) == 95.0


def test_option_intrinsic_value_including_bankruptcy_put():
    assert option_intrinsic_value("call", 100, 120) == 20.0
    assert option_intrinsic_value("call", 100, 80) == 0.0
    assert option_intrinsic_value("put", 100, 0) == 100.0  # underlying at zero


def test_option_kind_is_normalised_and_guarded():
    assert option_payoff("Call", 100, 120, 5) == 15.0  # case-insensitive
    assert option_payoff("straddle", 100, 120, 5) is None  # unknown kind
    assert option_payoff("call", 0, 120, 5) is None  # no strike
    assert option_payoff("call", 100, -5, 5) is None  # negative underlying
    assert option_payoff("call", 100, 120, -1) is None  # negative premium


def test_put_break_even_requires_premium_below_strike():
    assert option_break_even("put", 5, 5) is None
    assert option_break_even("put", 5, 7) is None


# ── portfolio_stats (M11) ────────────────────────────────────────────────────


def test_variance_is_sample_convention():
    assert variance([2.0, 4.0, 6.0]) == 4.0  # squared devs 8 / (n-1)=2
    assert variance([3.0]) is None


def test_covariance_and_correlation():
    assert covariance([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 2.0
    assert correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0
    assert correlation([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == -1.0
    assert correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None  # flat series
    assert covariance([1.0, 2.0], [1.0, 2.0, 3.0]) is None  # length mismatch


def test_beta_of_a_levered_clone_is_two():
    assert beta([2.0, 4.0, 6.0], [1.0, 2.0, 3.0]) == 2.0
    assert beta([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None  # flat market


def test_portfolio_variance_two_asset_textbook_value():
    # σ1=20%, σ2=10%, ρ=0.3, weights 60/40 — the classic MPT worked example.
    weights = [0.6, 0.4]
    cov = [[0.04, 0.006], [0.006, 0.01]]
    got = portfolio_variance(weights, cov)
    assert got == pytest.approx(0.01888)
    # Same number the two-asset teaching formula spells out ...
    spelled = 0.6**2 * 0.04 + 0.4**2 * 0.01 + 2 * 0.6 * 0.4 * 0.3 * 0.2 * 0.1
    assert got == pytest.approx(spelled)
    # ... and the diversification point itself: portfolio vol < weighted-average vol.
    assert got is not None
    assert got**0.5 < 0.6 * 0.2 + 0.4 * 0.1


def test_portfolio_variance_guards():
    assert portfolio_variance([], []) is None
    assert portfolio_variance([0.5, 0.5], [[0.04, 0.006]]) is None  # not square
    assert portfolio_variance([0.5, 0.5], [[0.04], [0.006, 0.01]]) is None  # ragged
    asymmetric = [[0.04, 0.02], [0.006, 0.01]]
    assert portfolio_variance([0.5, 0.5], asymmetric) is None
    non_psd = [[0.0, 0.02], [0.02, 0.0]]  # symmetric but not PSD
    assert portfolio_variance([1.0, -1.0], non_psd) is None  # negative variance


# ── returns.cagr_pct / max_drawdown_pct / sharpe_ratio (M12) ─────────────────


def test_cagr_doubling_in_ten_years():
    # 2^(1/10) - 1 = 7.18%/yr — the doubling anchor every compounding lesson uses.
    assert cagr_pct(10_000, 20_000, 10) == 7.18


def test_cagr_is_negative_for_a_losing_span():
    assert cagr_pct(10_000, 5_000, 10) == -6.7


def test_cagr_rejects_nonsense():
    assert cagr_pct(0, 20_000, 10) is None
    assert cagr_pct(10_000, -5, 10) is None
    assert cagr_pct(10_000, 20_000, 0) is None


def test_max_drawdown_is_peak_to_trough_not_first_to_last():
    # Peak 140 -> trough 70 = 50%, deeper than the earlier 120 -> 90 = 25%.
    assert max_drawdown_pct([100.0, 120.0, 90.0, 140.0, 70.0]) == 50.0
    assert max_drawdown_pct([100.0, 110.0, 120.0]) == 0.0  # never falls
    assert max_drawdown_pct([100.0]) == 0.0


def test_max_drawdown_rejects_nonsense():
    assert max_drawdown_pct([]) is None
    assert max_drawdown_pct([100.0, 0.0, 120.0]) is None  # no peak denominator


def test_sharpe_known_value_and_annualisation():
    # mean 2 / sample sd sqrt(2), annualised by sqrt(252) -> 22.45.
    assert sharpe_ratio([1.0, 3.0], 0.0, 252) == 22.45
    assert sharpe_ratio([1.0, 3.0], 0.0, 1) == 1.41  # no annualisation


def test_sharpe_risk_free_rate_lowers_the_ratio():
    # Annual rf of 252% -> 1.0 per period; excess mean halves, sd unchanged.
    with_rf = sharpe_ratio([1.0, 3.0], risk_free_rate_pct=252.0, periods_per_year=252)
    assert with_rf == 11.22
    no_rf = sharpe_ratio([1.0, 3.0], 0.0, 252)
    assert no_rf is not None and with_rf is not None and with_rf < no_rf


def test_sharpe_rejects_nonsense():
    assert sharpe_ratio([2.0], 0.0, 252) is None  # one observation
    assert sharpe_ratio([2.0, 2.0, 2.0], 0.0, 252) is None  # flat -> zero sd
    assert sharpe_ratio([1.0, 3.0], 0.0, 0) is None  # no periods


# ── screening.sharia_* / purification_amount (M13) ───────────────────────────


def test_sharia_debt_ratio_textbook_value():
    assert sharia_debt_ratio(10e9, 100e9) == 10.0


def test_sharia_liquidity_ratio_textbook_value():
    assert sharia_liquidity_ratio(20e9, 100e9) == 20.0


def test_sharia_impermissible_income_ratio_textbook_value():
    assert sharia_impermissible_income_ratio(3, 100) == 3.0


def test_sharia_ratios_reject_nonpositive_denominator():
    assert sharia_debt_ratio(10e9, 0) is None
    assert sharia_liquidity_ratio(20e9, -1) is None
    assert sharia_impermissible_income_ratio(3, 0) is None


def test_sharia_screen_passes_when_all_ratios_under_cap():
    result = sharia_screen(
        interest_bearing_debt=10e9,
        cash_plus_interest_securities=20e9,
        market_cap=100e9,
        non_compliant_income=3,
        total_revenue=100,
    )
    assert result is not None
    assert result.debt_ratio_pct == 10.0
    assert result.liquidity_ratio_pct == 20.0
    assert result.income_ratio_pct == 3.0
    assert result.debt_passes is True
    assert result.liquidity_passes is True
    assert result.income_passes is True
    assert result.passes is True


def test_sharia_screen_fails_when_one_ratio_over_cap():
    # Debt 40B / 100B mkt cap = 40% > the 33% default cap.
    result = sharia_screen(
        interest_bearing_debt=40e9,
        cash_plus_interest_securities=20e9,
        market_cap=100e9,
        non_compliant_income=3,
        total_revenue=100,
    )
    assert result is not None
    assert result.debt_ratio_pct == 40.0
    assert result.debt_passes is False
    assert result.liquidity_passes is True
    assert result.income_passes is True
    assert result.passes is False


def test_sharia_screen_rejects_nonpositive_denominators():
    assert (
        sharia_screen(
            interest_bearing_debt=10e9,
            cash_plus_interest_securities=20e9,
            market_cap=0,
            non_compliant_income=3,
            total_revenue=100,
        )
        is None
    )
    assert (
        sharia_screen(
            interest_bearing_debt=10e9,
            cash_plus_interest_securities=20e9,
            market_cap=100e9,
            non_compliant_income=3,
            total_revenue=0,
        )
        is None
    )


def test_purification_amount_textbook_value():
    # 5B non-compliant / 100B total income * $200 dividend = $10.
    assert purification_amount(5e9, 100e9, 200) == 10.0


def test_purification_amount_rejects_nonpositive_total_income():
    assert purification_amount(5e9, 0, 200) is None
    assert purification_amount(5e9, -1, 200) is None
