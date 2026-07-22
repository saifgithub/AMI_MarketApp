"""Sharia screening math — compliance ratios and purification, computed not authored.

CR046 M13, opened for CR058: a Sharia halal/haram screen and its purification
(the fraction of dividend income that must be donated away) are numbers a
lesson states as fact, so — same CR046 rigor as the rest of this package
(§7 of CR058: a wrong halal-screen number is worse than none) — they route
through here instead of being hand-authored. AAOIFI-style screen: debt,
liquidity, and impermissible-income ratios each checked against a threshold
(33% / 33% / 5% by default, but callers pass whichever standard they name).

Pure — floats in, floats/a NamedTuple/None out. No I/O.

NOT REACHABLE FROM THE `halal` MANDATE FLAG TODAY (DEF084). Despite the name,
none of this module is wired into the `halal` enforcement path. That flag is
enforced by membership in a fixed, curated *demonstration universe*
(`sim_engine.DEFAULT_HALAL_DEMO_UNIVERSE`), NOT by these ratio computations.
The only references to `sharia_screen()` & friends outside this module are the
re-exports in `trading_math/__init__.py`. Wiring this in (routing the `halal`
flag through `sharia_screen()` with a real fundamentals feed and a named
standard) is DEF084 Option 1 — deferred; Saiful chose Option 2 (tell the truth
about the allowlist). See docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/.
"""

from __future__ import annotations

from typing import NamedTuple


def sharia_debt_ratio(interest_bearing_debt: float, market_cap: float) -> float | None:
    """Interest-bearing debt as a percent of market cap (1 dp).

    None when market cap is non-positive — the ratio has no denominator.
    """
    if market_cap <= 0:
        return None
    return round(interest_bearing_debt / market_cap * 100, 1)


def sharia_liquidity_ratio(
    cash_plus_interest_securities: float, market_cap: float
) -> float | None:
    """Cash + interest-bearing securities as a percent of market cap (1 dp).

    None when market cap is non-positive.
    """
    if market_cap <= 0:
        return None
    return round(cash_plus_interest_securities / market_cap * 100, 1)


def sharia_impermissible_income_ratio(
    non_compliant_income: float, total_revenue: float
) -> float | None:
    """Non-compliant income as a percent of total revenue (1 dp).

    None when total revenue is non-positive.
    """
    if total_revenue <= 0:
        return None
    return round(non_compliant_income / total_revenue * 100, 1)


class ShariaScreenResult(NamedTuple):
    """The three AAOIFI-style screen ratios, each checked against its cap."""

    debt_ratio_pct: float
    liquidity_ratio_pct: float
    income_ratio_pct: float
    debt_passes: bool
    liquidity_passes: bool
    income_passes: bool
    passes: bool


def sharia_screen(
    interest_bearing_debt: float,
    cash_plus_interest_securities: float,
    market_cap: float,
    non_compliant_income: float,
    total_revenue: float,
    debt_max: float = 33.0,
    liquidity_max: float = 33.0,
    income_max: float = 5.0,
) -> ShariaScreenResult | None:
    """Full Sharia compliance screen: three ratios, each vs. its cap, and overall pass.

    Thresholds are parameters, not constants — the caller names the standard
    (AAOIFI defaults 33/33/5); this only checks. None when market cap or
    total revenue is non-positive (an underlying ratio has no denominator).
    """
    debt_ratio = sharia_debt_ratio(interest_bearing_debt, market_cap)
    liquidity_ratio = sharia_liquidity_ratio(cash_plus_interest_securities, market_cap)
    income_ratio = sharia_impermissible_income_ratio(non_compliant_income, total_revenue)
    if debt_ratio is None or liquidity_ratio is None or income_ratio is None:
        return None
    debt_passes = debt_ratio <= debt_max
    liquidity_passes = liquidity_ratio <= liquidity_max
    income_passes = income_ratio <= income_max
    return ShariaScreenResult(
        debt_ratio_pct=debt_ratio,
        liquidity_ratio_pct=liquidity_ratio,
        income_ratio_pct=income_ratio,
        debt_passes=debt_passes,
        liquidity_passes=liquidity_passes,
        income_passes=income_passes,
        passes=debt_passes and liquidity_passes and income_passes,
    )


def purification_amount(
    non_compliant_income: float, total_income: float, dividend_received: float
) -> float | None:
    """Dollar amount of a dividend that must be purified (donated away), 2 dp.

    `(non_compliant_income / total_income) × dividend_received`. None when
    total income is non-positive — the fraction has no denominator.
    """
    if total_income <= 0:
        return None
    return round((non_compliant_income / total_income) * dividend_received, 2)
