"""Valuation & fundamentals math — finished figures the LLM must never derive.

Two jobs:

* `multiple_compression_downside` — CR046 M07. Answers "if this P/E compresses by
  N points, how far does the price fall?" The Room's Bear Researcher used to state
  this as a fact computed inline by a formula that was simply wrong
  (`int(pe/(pe+10)*100-50)` printed ~16% for a real 50% drop). Price moves with the
  multiple when earnings are held constant, so a `delta`-point compression from a
  P/E of `pe` is a `delta/pe` drawdown — nothing more exotic.

* the unit conversions behind CR046 M04 — the deterministic decimal→percent,
  dollars→millions, and dividend-yield conversions that turn a raw yfinance `info`
  value into the finished figure an analyst quotes. They lived inline in
  `services/fundamentals.py`; centralised here so the ledger has one home and one
  guard test for each.

Pure — floats in, floats out. No yfinance import, no I/O; the caller fetches the
raw values and hands them in.
"""

from __future__ import annotations

from typing import Sequence

# Above this, the figure is a flow-over-point artifact rather than a rate —
# see `cost_of_debt_pct`. Distressed corporate borrowing tops out well below it.
_MAX_PLAUSIBLE_COST_OF_DEBT_PCT = 40.0


def multiple_compression_downside(pe: float | None, delta_pts: float) -> float | None:
    """Downside %, if a P/E of `pe` compresses by `delta_pts` points.

    Price is proportional to the multiple when earnings are held constant, so a
    compression of `d` points from `pe` costs `d/pe` of the price. Capped at the
    full multiple (a compression can't take the price below zero). Returns None
    for a nonsensical multiple (non-positive P/E, e.g. a loss-making company) or a
    non-positive compression, so the caller states no downside figure rather than
    a bogus one.

    >>> multiple_compression_downside(20, 10)   # 20x -> 10x is a halving
    50.0
    """
    if pe is None or pe <= 0 or delta_pts <= 0:
        return None
    compression = min(delta_pts, pe)  # can't compress past a 0x multiple
    return round(compression / pe * 100, 1)


def ratio_to_pct(ratio: float | None, decimals: int = 0) -> float | None:
    """A yfinance decimal ratio (0.05) → a percent figure (5). None passes through.

    yfinance reports growth/margin as decimals; the prompt wants whole percents
    (revenue growth, profit margin) or one-decimal percents (FCF yield). One place,
    one rounding rule.
    """
    if ratio is None:
        return None
    return round(ratio * 100) if decimals == 0 else round(ratio * 100, decimals)


def fcf_yield_pct(free_cash_flow: float | None, market_cap: float | None) -> float | None:
    """Free-cash-flow yield as a percent = FCF / market cap × 100 (1 dp).

    None when either input is missing or the market cap is non-positive.
    """
    if free_cash_flow is None or market_cap is None or market_cap <= 0:
        return None
    return round(free_cash_flow / market_cap * 100, 1)


def cost_of_debt_pct(
    annual_interest: float | None, gross_debt: float | None
) -> float | None:
    """Implied annual cost of debt % = annual interest / gross debt (1 dp).

    CR221 A3 — asked for 6 times by 4 agents ("what average interest rate is
    this company paying?"). Both inputs come from the caller already annualised
    and already agreed on a basis; the four-quarters-or-nothing rule that makes
    the numerator honest lives in `edgar_pit.ttm`, not here.

    `abs()` on the numerator for the reason `interest_coverage` uses it: filers
    sign interest expense as a cost or as a magnitude, and both mean the same
    outflow.

    Refused above `_MAX_PLAUSIBLE_COST_OF_DEBT_PCT`, because the numerator is a
    FLOW over the year and the denominator a POINT at the end of it: a company
    that repaid most of its debt in Q4 pays a full year of interest against a
    stub balance and computes to a triple-digit "rate". Distressed borrowers
    reach the high teens, so the ceiling clears every real cost of debt and
    catches only the artifact.

    >>> cost_of_debt_pct(-1_842, 45_146)   # Caterpillar FY2025, $M
    4.1
    """
    if annual_interest is None or gross_debt is None or gross_debt <= 0:
        return None
    pct = round(abs(annual_interest) / gross_debt * 100, 1)
    return None if pct > _MAX_PLAUSIBLE_COST_OF_DEBT_PCT else pct


def net_cash_millions(total_cash: float | None, total_debt: float | None) -> int | None:
    """Net cash (cash − debt) in millions of dollars, rounded. Negative = net debt.

    None when either input is missing. The caller decides the label (net cash vs
    net debt) from the sign — see `net_position_phrase`.
    """
    if total_cash is None or total_debt is None:
        return None
    return round((total_cash - total_debt) / 1_000_000)


def net_position_phrase(net_cash_m: int | None) -> str | None:
    """Sign-aware balance-sheet phrase: 'net cash $X M' or 'net debt $Y M'.

    A negative net-cash figure was being rendered as 'Net cash: $-42000M', which
    reads as a fabricated fact; a levered company carries net *debt*.
    """
    if net_cash_m is None:
        return None
    if net_cash_m < 0:
        return f"net debt ${abs(net_cash_m)}M"
    return f"net cash ${net_cash_m}M"


def dividend_yield_pct(raw: float | None) -> float | None:
    """yfinance `info['dividendYield']` → a percent figure (2 dp). None passes through.

    Convention note (CR046 M04, verified 2026-07-21 on the pinned **yfinance
    1.5.1** running on the Alpha backend): `dividendYield` is returned **already as
    a percent** — KO 2.58, T 5.06, AAPL 0.33 all matched the real yield, while the
    sibling `trailingAnnualDividendYield` is the decimal fraction (0.025, 0.051,
    0.0032). So this is a pass-through round, NOT a ×100. It is deliberately not
    auto-detecting fraction-vs-percent: a 0.33% payer's percent value (0.33) is
    indistinguishable from a fraction (33%), so any heuristic would misfire on low
    yielders. If a future yfinance bump flips the convention back to a fraction,
    this one function is where it changes.
    """
    if raw is None:
        return None
    return round(raw, 2)
