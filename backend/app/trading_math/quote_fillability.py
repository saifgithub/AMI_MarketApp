"""DEF305 — may this quote move a real user's ledger?

**One rule, one implementation.** This lived as a private `_quote_is_fillable`
inside `sim_resting_orders.py`, applied on the ENTRY book only. The exit book —
the stop/target sweep, in the same file and the same tick — delegated to
`SimEngine.evaluate_outcomes`, which took a bare `float` and therefore could not
consult a source it never received. So one half of a single tick refused to fill
on a fabricated price while the other half liquidated the whole book on one.

That is DEF190's shape exactly: *the guard is real, it is just not on the path
that moves the money.* Copying the predicate into `sim_engine` would have been
DEF098's shape instead — two derivations of one rule, which disagree the first
time either moves. So it lives here, imported by both.

**What it cost.** On 2026-08-14 one sweep tick closed 8 bracketed positions
across 2 portfolios at prices drawn from `market_data._walk_for`'s
`50 + rng.uniform(0, 400)` band — `HPQ` target `32.23` closed at `334.96`, `BAC`
target `68.77` at `420.78` — and credited the proceeds as real cash. One
portfolio read `$10,000 -> $12,390.29` (+23.9%) when its true marked value was
`$9,432.24` (-5.7%). The ledger reconciled internally to the cent, which is why
nothing else flagged it.

**This fires routinely, by design.** The upstream yfinance fault that produces
the fallback fired 23 times in 24 hours. A guard on this path is a normal
operating event, not an alarm — callers must log it at a volume that suits
something happening every hour, or the signal gets muted and we are back where
we started.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings

#: `current_quote`'s sentinel when no provider answered at all. Booking on it
#: would fire every buy limit and every sell stop in the book simultaneously.
UNAVAILABLE = "unavailable"

#: The deterministic random walk. Real under `USE_REAL_MARKET_DATA=false`,
#: where it IS the intended provider; a degraded fallback when real data is on.
MOCK_WALK = "mock_walk"


class _QuoteLike(Protocol):
    price: float
    source: str


def is_fillable(quote: _QuoteLike | None) -> bool:
    """Whether `quote` may be booked into a real user's ledger.

    `None`, the `unavailable` sentinel and any non-positive price are refused
    outright. `mock_walk` is refused only when real market data is switched on —
    with it off, the walk is the intended provider and refusing it would stop
    the simulator working at all.
    """
    if quote is None:
        return False
    if quote.source == UNAVAILABLE or quote.price <= 0:
        return False
    if settings.use_real_market_data and quote.source == MOCK_WALK:
        return False
    return True


def refusal_reason(quote: _QuoteLike | None) -> str | None:
    """Why this quote was refused, or `None` if it was not.

    Separate from `is_fillable` so a caller can say *what* happened without
    re-deriving the branch — and so the reason reaching a user or a log is the
    same string the predicate actually acted on, rather than a second guess at
    it (the CR038 class: two descriptions of one fact drift).
    """
    if quote is None:
        return "no quote was returned"
    if quote.source == UNAVAILABLE:
        return "no market-data provider answered"
    if quote.price <= 0:
        return f"provider returned a non-positive price ({quote.price})"
    if settings.use_real_market_data and quote.source == MOCK_WALK:
        return (
            "the live feed fell through to the deterministic mock walk, whose "
            "prices have no relationship to the market"
        )
    return None
