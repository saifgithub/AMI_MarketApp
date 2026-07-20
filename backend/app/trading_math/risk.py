"""Single-position risk math — how much a proposed trade can cost the portfolio.

`drawdown_contribution` answers the question DEF066 got wrong: a position of size
P% with a stop S% below entry contributes about P×S/100 percentage points to total
portfolio drawdown — NOT S%. The original error compared a per-trade stop distance
straight against the portfolio-level drawdown cap, overstating risk ~20× and making
16 of 64 benchmark tickers un-buyable. The formula is trivial; the point is that it
lives in exactly one place and every caller — prompt, compliance, test — reads the
same number.
"""

from __future__ import annotations

from typing import NamedTuple


class DrawdownContribution(NamedTuple):
    """A single position's contribution to portfolio drawdown if stopped out."""

    stop_distance_pct: float  # how far the stop sits below entry, in %
    contribution_pts: float  # percentage points this position adds to drawdown


def drawdown_contribution(
    size_pct: float, entry: float, stop: float
) -> DrawdownContribution | None:
    """Points a single position contributes to portfolio drawdown if stopped out.

    Returns None for a nonsensical proposal — non-positive size or entry, or a stop
    not strictly between 0 and entry — so the caller keeps its portfolio-level
    guidance without a per-trade figure rather than emitting a bogus one.
    """
    if size_pct > 0 and entry > 0 and 0 < stop < entry:
        stop_distance_pct = (entry - stop) / entry * 100
        contribution_pts = size_pct * stop_distance_pct / 100
        return DrawdownContribution(stop_distance_pct, contribution_pts)
    return None
