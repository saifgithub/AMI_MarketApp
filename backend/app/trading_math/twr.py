"""Time-weighted return — the pure maths behind CR109's equity curve.

GIPS-standard TWR, not a simple (end/start - 1) return: a raw NAV series
conflates market performance with capital flows (a reset, a top-up), so a
naive whole-period return can read a real loss followed by a fresh stake as
roughly flat. TWR isolates performance by chain-linking sub-period returns
split at every capital event, so the loss stays visible no matter what
capital did around it.

No DB — `NavPoint` is the caller's own shape (`PortfolioNavDailyRow` maps to
it one field at a time), matching the style of `returns.py` / `risk.py` /
`portfolio_stats.py` elsewhere in this package.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import NamedTuple, Optional


class NavPoint(NamedTuple):
    """One NAV observation, ascending by `as_of`.

    `capital_event` marks a row whose NAV moved for a reason other than
    market performance (`open` / `restart` / `topup`) — the point where the
    TWR chain must split rather than blend into the prior sub-period.
    """

    as_of: date
    nav: float
    capital_event: Optional[str] = None


def sub_period_returns(navs: Sequence[NavPoint]) -> list[float]:
    """Per-sub-period returns, split at every capital event.

    A new sub-period starts at the first point and at every subsequent point
    carrying a `capital_event` — that point's NAV becomes the new baseline,
    never blended into the return of the period before it. Returns within a
    sub-period telescope directly to (end/start - 1), so this walks the
    points once rather than compounding day-by-day deltas.

    A sub-period with no second observation before the chain splits again
    (e.g. two capital events back to back, or a series that ends right on
    one) contributes nothing — there is no elapsed performance to report.
    A non-positive baseline NAV is skipped rather than divided by, the same
    defensive contract `returns.py` uses elsewhere in this package.
    """
    if len(navs) < 2:
        return []

    returns: list[float] = []
    period_start_nav = navs[0].nav
    last_nav = navs[0].nav
    has_observation = False

    for point in navs[1:]:
        if point.capital_event:
            if has_observation and period_start_nav > 0:
                returns.append(last_nav / period_start_nav - 1.0)
            period_start_nav = point.nav
            last_nav = point.nav
            has_observation = False
        else:
            last_nav = point.nav
            has_observation = True

    if has_observation and period_start_nav > 0:
        returns.append(last_nav / period_start_nav - 1.0)

    return returns


def time_weighted_return(navs: Sequence[NavPoint]) -> float | None:
    """TWR = Π(1 + rᵢ) − 1 over the chain-linked sub-period returns.

    `None` below two points — there is nothing to compound. `0.0` (not
    `None`) when two-plus points exist but no sub-period ever accrued an
    observed return (e.g. a capital event on the very next row): that is a
    correctly flat answer, not a missing one.
    """
    if len(navs) < 2:
        return None
    product = 1.0
    for r in sub_period_returns(navs):
        product *= 1.0 + r
    return product - 1.0


def alpha_vs_benchmark(run_twr: float, benchmark_twr: float) -> float:
    """Excess return — the run's TWR minus the benchmark's over the same
    window. Positive means the run beat the benchmark; the thin-field
    scoring basis (CR109 slice 3) is built on this number."""
    return run_twr - benchmark_twr
