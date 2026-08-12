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


# ── CR109 Amendment I — the account may not go negative ────────────────────
#
# Saiful, 2026-08-12, on being told a short posts its full notional:
# *"keep no leverage, but when the game ends, all positions must be closed.
# how do we keep the account from going negative?"*
#
# Amendment G left the leg unbounded below on purpose — *"the one position in
# the game whose loss is not bounded by what you put in"* — and said the run's
# own clock was the containment. It is not. A run's NAV feeds the TWR chain,
# and TWR is **undefined across a sign change**: one negative link makes every
# link after it arithmetic about nothing. So the containment has to be a real
# mechanism, and it is two of them.
#
# **Where the account actually breaks, in closed form.** `cash_posted` is the
# full notional, so `cash_posted = entry*q` and
#
#     leg = cash_posted + (entry - mark)*q = q*(2*entry - mark)
#
# which is zero at exactly `mark == 2*entry` and negative above it. A short
# therefore cannot take an account under until the name has DOUBLED. That is
# the whole trigger — no maintenance-margin table, no borrow rate, no
# per-ticker data we would have to invent (the CR040 fabrication CR171 §4
# spends a page avoiding).

MAINTENANCE_FLOOR_PCT = 0.10
"""Fraction of the posted collateral at which a short is bought in.

Not zero, because the cover has to be PAID for out of the leg. At exactly
`leg == 0` the cover fee (0.1% of a notional that has by then doubled) would
come out of the player's other positions — so a forced buy-in at the true
zero still leaks past it, in the one case built to prevent leaking. Ten
percent of the collateral is ~100x the cover fee at the trigger, which
absorbs the fee and an ordinary intraday move against the fill.
"""


def short_maintenance_floor(cash_posted: float) -> float:
    """Leg value at which `short_needs_buyin` fires."""
    return cash_posted * MAINTENANCE_FLOOR_PCT


def short_buyin_trigger_price(entry_price: float) -> float:
    """The mark that trips the buy-in — derived, never a second constant.

    Solving `q*(2*entry - mark) == MAINTENANCE_FLOOR_PCT * entry*q` for the
    mark gives `entry * (2 - MAINTENANCE_FLOOR_PCT)`; the quantity cancels,
    so the trigger is a pure multiple of the entry price and the ticket can
    show it before the player commits.
    """
    return entry_price * (2.0 - MAINTENANCE_FLOOR_PCT)


def short_needs_buyin(
    cash_posted: float, quantity: float, entry_price: float, mark: float,
) -> bool:
    """True when this short has eaten through all but the floor of its collateral."""
    return short_leg(cash_posted, quantity, entry_price, mark) <= short_maintenance_floor(
        cash_posted
    )


def nav_floor(total_value: float) -> tuple[float, float]:
    """`(nav, shortfall)` — a run's NAV never goes below zero.

    The buy-in above bounds an ORDERLY move; it cannot bound a GAP. A name
    that closes at 1.8x entry and opens at 3x fills the forced cover at 3x,
    and the account is already negative when the mechanism gets to run. That
    residual is real and is not designable away — a real short has it too,
    and it is why a real broker can hand you a bill.

    So the run floors at zero and busts. The excess is returned as
    `shortfall` rather than discarded, because the two numbers answer
    different questions: the NAV keeps the scoring chain defined (a wipeout
    is -100%, which is exactly what a wipeout is), and the shortfall is the
    honest extra fact — what a real broker would have billed — which the
    Close states in words instead of smuggling into a return.

    Flooring is NOT the `?? 0` class this feature keeps producing: nothing is
    being guessed or defaulted here. Both halves of the true value survive,
    in the two fields the two consumers need.
    """
    if total_value >= 0:
        return total_value, 0.0
    return 0.0, -total_value
