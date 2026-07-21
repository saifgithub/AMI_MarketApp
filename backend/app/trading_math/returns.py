"""Return-series metrics — CAGR, max drawdown, Sharpe ratio.

CR046 M12, opened for CR054 Wave 1 (BOK M20–M21 evaluator's-math and
performance lessons): the "grew at X% a year", "fell Y% peak-to-trough", and
"Sharpe of Z" figures in worked examples are computed here, never authored by
hand (CR054 §4.5).

CR046 Decision D1 flagged `empyrical-reloaded` for this family, but that is a
new dependency (needs Saiful's sign-off) and the three the BOK needs are
trivial — hand-rolled here, stdlib-only, so the library stays copy-portable.
The wider family (Sortino, Calmar, rolling vol) stays on the D1 backlog and
would revisit adoption.

Conventions: values/returns as percents where suffixed `_pct`; Sharpe takes
per-period simple returns in percent and an ANNUAL risk-free percent, sample
(n-1) deviation, annualised by sqrt(periods_per_year). All three round 2 dp
(presented figures).

Pure — primitives in, a float or None out.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from .portfolio_stats import variance


def cagr_pct(start_value: float, end_value: float, years: float) -> float | None:
    """Compound annual growth rate, percent, 2 dp: (end/start)^(1/years) - 1.

    Negative when the holding lost money over the span. None when either value
    or the span is non-positive (no meaningful compounding).
    """
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None
    return round(((end_value / start_value) ** (1 / years) - 1) * 100, 2)


def max_drawdown_pct(values: Sequence[float]) -> float | None:
    """Deepest peak-to-trough fall over a value series, positive percent, 2 dp.

    The running-peak sibling of M05's point-in-time `drawdown_pct`. 0.0 for a
    series that never falls below a prior peak; None for an empty series or
    any non-positive value (no meaningful peak denominator).
    """
    if not values:
        return None
    if any(v <= 0 for v in values):
        return None
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        worst = max(worst, (peak - v) / peak * 100)
    return round(worst, 2)


def sharpe_ratio(
    returns_pct: Sequence[float],
    risk_free_rate_pct: float = 0.0,
    periods_per_year: int = 252,
) -> float | None:
    """Annualised Sharpe ratio, 2 dp: mean excess return / its sample deviation.

    `returns_pct` are per-period simple returns in percent;
    `risk_free_rate_pct` is ANNUAL and is spread evenly across the periods.
    None below 2 observations, on a flat excess series (zero deviation — a
    Sharpe of "infinity" is a number a lesson must not ship), or a
    non-positive `periods_per_year`.
    """
    if periods_per_year <= 0 or len(returns_pct) < 2:
        return None
    rf_per_period = risk_free_rate_pct / periods_per_year
    excess = [r - rf_per_period for r in returns_pct]
    var = variance(excess)
    if not var:
        return None
    mean_excess = sum(excess) / len(excess)
    return round(mean_excess / sqrt(var) * sqrt(periods_per_year), 2)
