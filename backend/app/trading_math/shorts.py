"""Short-position arithmetic for the GAME lane — CR109 Amendment G.

Pure: primitives in, primitives out, same contract as the rest of
`trading_math`. It exists as its own module rather than as three lines
inside `Portfolio.total_value` because the same identity has to hold in
four independent places — the run screen's value, the daily NAV snapshot,
the TWR chain the Close scores on, and the drawdown denominator — and a
formula copied into four places is a formula that will disagree in one of
them.

**The identity that must hold.** Opening a short must not change the
portfolio's total value, and covering it at the same price must not change
it either. Everything else in the design follows from that:

    open q at p:   cash_posted = p*q ; cash -= (cash_posted + fee)
    while open:    leg = cash_posted + (p - mark)*q
    cover at c:    cash += cash_posted + (p - c)*q - fee

At `mark == p` the leg is worth exactly the cash that left, so the sum is
unchanged — the fee is the only movement, which is true of a buy as well.
As the mark falls the leg grows; as it rises the leg shrinks, and it can
go NEGATIVE (a short that doubles against you costs more than it posted),
which is deliberate and is the whole lesson: this is the one position in
the game whose loss is not bounded by what you put in.

**No leverage.** `cash_posted` is the FULL notional, not a margin
fraction. A real short posts ~50% and is therefore 2:1 levered; CR109
§5.1's "Leverage / margin: None, ever" is not suspended by shorting, so
here a $5,000 short ties up $5,000 exactly as a $5,000 buy would. Gross
exposure can never exceed the stake, and a 10% move pays 10% whichever
direction it was taken from — which is what keeps the contest scoreable
against players who only go long.
"""

from __future__ import annotations

from collections.abc import Iterable


def short_leg(cash_posted: float, quantity: float, entry_price: float, mark: float) -> float:
    """One open short's contribution to portfolio value.

    `cash_posted` back, less what it would now cost to buy the shares back
    relative to where they were sold. Unbounded below by design — see the
    module docstring.
    """
    return cash_posted + (entry_price - mark) * quantity


def short_legs_value(legs: Iterable[tuple[float, float, float, float]]) -> float:
    """Σ `short_leg` over (cash_posted, quantity, entry_price, mark) tuples."""
    return sum(short_leg(c, q, e, m) for c, q, e, m in legs)


def short_unrealised_pnl(quantity: float, entry_price: float, mark: float) -> float:
    """Signed P&L on an open short: positive when the mark is BELOW entry.

    Excludes fees, which are burned at the fill and reported separately on
    the entry's `fees_paid` — a P&L line that netted them would double-count
    the cost the Close already shows.
    """
    return (entry_price - mark) * quantity


def short_cover_proceeds(
    cash_posted: float, quantity: float, entry_price: float, close_price: float,
) -> float:
    """Cash returned by covering a short in full, BEFORE the cover fee.

    Equal to `short_leg` evaluated at the close price — covering converts
    the leg back into cash at exactly its marked value, which is why the
    total is continuous across the cover.
    """
    return short_leg(cash_posted, quantity, entry_price, close_price)
