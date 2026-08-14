"""CR171 — short positions in the TRAINING lane.

The twin of `games_shorts.py`, and deliberately a separate module rather than a
`kind` branch inside it, because **the two lanes have different cash models and
that difference is the point of each.**

| | Game (CR109 Amendment G) | Training (CR171 §2/§7) |
|---|---|---|
| Posted at open | full notional | notional × 1.50 |
| Cash that leaves | full notional | notional × 0.50 |
| Margin call | none | forced buy-in below 1.30 |
| Why | gross exposure must never exceed the stake, or the contest is not scoreable against players who only go long | the margin call IS the lesson; a simulator that cannot deliver one teaches that a short is a long with the sign flipped |

One table with a `kind` column would need that branch on every read. Two tables
need it nowhere.

**What the two lanes DO share is the arithmetic**, and they share it through
`trading_math.shorts` rather than by copy. That works because `short_leg` is
written in terms of *the cash that left*:

    leg = cash_posted + (entry − mark) × quantity

which is identical to §2's `collateral − quantity × mark` whenever
`collateral = cash_posted + notional`. So training stores `cash_posted =
0.5 × notional` and gets §2's formula out of the game lane's function, with no
second derivation to drift apart (DEF098).

**The identity that must hold, in both lanes:** opening a short does not change
`total_value`, and covering at the same price does not change it either. At
`mark == entry` the leg is worth exactly the cash that left, so the sum is
unchanged. Everything else follows from that — most importantly that short
proceeds **never enter `current_cash`**. Credit them and a user who shorts
$5,000 has $15,000 of apparent buying power; worse, `current_cash` is read by
`total_value`, `total_drawdown_pct`, `portfolio_nav_daily`,
`portfolio_value_snapshots`, the TWR chain and `_risk_limit_context`, so a
credit that is not spendable is **indistinguishable from a profit** in the NAV
series.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db.models import SimPortfolioRow, SimShortPositionRow
from app.schemas.trade import ShortLeg
from app.services.short_borrow_rate import BorrowRate
from app.trading_math.shorts import short_cover_proceeds, short_unrealised_pnl


def _leg(row: SimShortPositionRow) -> ShortLeg:
    return ShortLeg(
        id=row.id,
        ticker=row.ticker,
        quantity=float(row.quantity),
        entry_price=float(row.entry_price),
        cash_posted=float(row.cash_posted),
        opened_at=row.opened_at,
    )


def open_shorts_for_portfolio(session, portfolio_id: UUID) -> list[ShortLeg]:
    """Every still-open training short, oldest first."""
    rows = session.execute(
        select(SimShortPositionRow)
        .where(
            SimShortPositionRow.portfolio_id == portfolio_id,
            SimShortPositionRow.state == "open",
        )
        .order_by(SimShortPositionRow.opened_at.asc())
    ).scalars().all()
    return [_leg(r) for r in rows]


def find_open_short(
    session, portfolio_id: UUID, ticker: str,
) -> SimShortPositionRow | None:
    """The open short on one ticker, or None. At most one can exist — adding to
    a short would blend two entry prices into one position, the same attribution
    problem §1's no-partial rule refuses, and there is no `avg_cost` column here
    to hold the blend honestly."""
    return session.execute(
        select(SimShortPositionRow).where(
            SimShortPositionRow.portfolio_id == portfolio_id,
            SimShortPositionRow.ticker == ticker,
            SimShortPositionRow.state == "open",
        )
    ).scalars().first()


def collateral_for(notional: float) -> float:
    """§7's initial margin — proceeds plus 50%."""
    return round(notional * float(settings.short_initial_margin), 2)


def cash_required_for(notional: float) -> float:
    """What actually leaves `current_cash`: collateral minus the proceeds the
    short generates. The proceeds are real, they are simply not spendable —
    keeping them out of cash is §2's whole design."""
    return round(collateral_for(notional) - notional, 2)


def open_short(
    session,
    *,
    portfolio_row: SimPortfolioRow,
    user_id: UUID,
    ticker: str,
    quantity: float,
    fill_price: float,
    borrow: BorrowRate,
    stop: float | None = None,
    target: float | None = None,
    now: datetime | None = None,
) -> SimShortPositionRow:
    """Sell to open. Debits only the margin above the proceeds, and writes the
    position row with the borrow rate resolved ONCE, here, with its provenance.

    The caller has already checked affordability, matching how
    `_execute_fill`'s buy branch checks before opening its transaction.
    """
    now = now or datetime.now(timezone.utc)
    notional = round(fill_price * quantity, 2)
    row = SimShortPositionRow(
        id=uuid4(),
        user_id=user_id,
        portfolio_id=portfolio_row.id,
        ticker=ticker,
        quantity=quantity,
        entry_price=fill_price,
        cash_posted=cash_required_for(notional),
        collateral_posted=collateral_for(notional),
        borrow_rate_pct=borrow.rate_pct,
        borrow_rate_source=borrow.source,
        borrow_rate_basis=borrow.basis,
        borrow_rate_as_of=borrow.as_of,
        borrow_accrued_total=0.0,
        stop=stop,
        target=target,
        opened_at=now,
        state="open",
    )
    session.add(row)
    portfolio_row.current_cash = round(
        float(portfolio_row.current_cash) - cash_required_for(notional), 2,
    )
    return row


def cover_short(
    session,
    *,
    portfolio_row: SimPortfolioRow,
    short_row: SimShortPositionRow,
    close_price: float,
    reason: str = "user",
    now: datetime | None = None,
) -> float:
    """Buy to cover, in full. Returns the realised P&L (borrow excluded).

    **Never refused for insufficient cash**, and on the forced-close path that
    is not a convenience but the containment mechanism itself: the collateral
    was posted at open precisely so a margin call cannot fail. A cover that
    could be blocked by a low balance would leave a user unable to close the one
    position whose loss is unbounded — the mechanism failing exactly when it is
    needed (§7).

    The arithmetic cannot produce a refusal in any case: the loss is taken out
    of the posted cash before what remains comes back.
    """
    now = now or datetime.now(timezone.utc)
    quantity = float(short_row.quantity)
    entry_price = float(short_row.entry_price)
    cash_posted = float(short_row.cash_posted)

    proceeds = short_cover_proceeds(cash_posted, quantity, entry_price, close_price)
    realised = round(short_unrealised_pnl(quantity, entry_price, close_price), 2)

    portfolio_row.current_cash = round(
        float(portfolio_row.current_cash) + proceeds, 2,
    )
    short_row.state = "closed"
    short_row.closed_at = now
    short_row.close_price = close_price
    short_row.close_reason = reason
    short_row.realised_pnl = realised
    session.add(short_row)
    return realised


def margin_ratio(row: SimShortPositionRow, mark: float) -> float:
    """§7's maintenance ratio: what the position is worth against what it would
    now cost to close.

        ratio = (collateral + entry×qty − mark×qty) / (mark × qty)

    Above 1.0 the collateral still covers the buy-back with room to spare;
    below `short_maintenance_margin` the account takes the decision away.

    A mark of zero cannot happen through `_quote_is_fillable` (which refuses
    non-positive prices), but the guard is here rather than at the call site
    because a division that only fails in production is not a guard.
    """
    quantity = float(row.quantity)
    cost_to_close = mark * quantity
    if cost_to_close <= 0:
        return float("inf")
    value = (
        float(row.collateral_posted)
        + float(row.entry_price) * quantity
        - cost_to_close
    )
    return value / cost_to_close


def is_margin_breached(row: SimShortPositionRow, mark: float) -> bool:
    return margin_ratio(row, mark) < float(settings.short_maintenance_margin)
