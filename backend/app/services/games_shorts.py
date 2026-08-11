"""Short positions in the GAME lane — CR109 Amendment G.

Saiful, 2026-08-11: *"the game does not allow 'short' selling? we will need
to add a 'fee' for short selling. lets set it at 0.3% for now."* CR109 §5.1
said *"Long only. There is no short"*; this is that rule being lifted for
the contest, deliberately and with a price on it.

**This module is the game's own.** It writes `game_short_positions` and
nothing else, and it is reached only from `SimEngine.submit_game_trade` —
the §7.1 fence that keeps the game's trade path structurally separate from
training's `submit()` still holds, and no training code path can reach a
row here. The arithmetic is in `trading_math/shorts.py`; what lives here is
the three transitions and the rules about which one a fill is.

**A sell never crosses zero.** Given a holding of `h` and a sell of `q`:

    h >= q   sell to close  — unchanged, the long path
    h == 0   sell to open   — a short
    0 < h < q                — REFUSED, naming both numbers

Real venues split that third case into a close plus a short. We refuse it:
the split turns one user action into two fills, two cost bases and an
ambiguous P&L attribution, which is precisely the class of bug DEF166 and
DEF110 have already cost this project twice. Refusing costs one sentence of
copy and removes the class.

The mirror rule applies to the cover: a BUY on a ticker with an open short
covers it IN FULL or is refused. A partial cover would leave a position
whose entry price is a blend of two decisions, for the same reason.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.models import GameShortPositionRow, SimPortfolioRow
from app.schemas.trade import ShortLeg
from app.trading_math.shorts import short_cover_proceeds, short_unrealised_pnl


def _leg(row: GameShortPositionRow) -> ShortLeg:
    return ShortLeg(
        id=row.id,
        ticker=row.ticker,
        quantity=float(row.quantity),
        entry_price=float(row.entry_price),
        cash_posted=float(row.cash_posted),
        opened_at=row.opened_at,
    )


def open_shorts_for_portfolio(session, portfolio_id: UUID) -> list[ShortLeg]:
    """Every still-open short on a portfolio, oldest first."""
    rows = session.execute(
        select(GameShortPositionRow)
        .where(
            GameShortPositionRow.portfolio_id == portfolio_id,
            GameShortPositionRow.state == "open",
        )
        .order_by(GameShortPositionRow.opened_at.asc())
    ).scalars().all()
    return [_leg(r) for r in rows]


def find_open_short(session, portfolio_id: UUID, ticker: str) -> GameShortPositionRow | None:
    """The open short on one ticker, or None.

    At most one can exist: `open_short` refuses to add to a ticker that
    already carries one. Extending a short would blend two entry prices into
    one position, which is the same attribution problem the partial-cover
    rule refuses — and unlike a long, there is no `avg_cost` column here to
    hold the blend honestly.
    """
    return session.execute(
        select(GameShortPositionRow).where(
            GameShortPositionRow.portfolio_id == portfolio_id,
            GameShortPositionRow.ticker == ticker,
            GameShortPositionRow.state == "open",
        )
    ).scalars().first()


def open_short(
    session,
    *,
    portfolio_row: SimPortfolioRow,
    user_id: UUID,
    run_id: UUID,
    ticker: str,
    quantity: float,
    fill_price: float,
    fee: float,
    now: datetime | None = None,
) -> GameShortPositionRow:
    """Sell to open. Debits `cash_posted + fee` and writes the position row.

    The caller has already checked affordability — this does not re-check,
    for the same reason `_execute_fill`'s buy branch does its check before
    opening the transaction.
    """
    now = now or datetime.now(timezone.utc)
    cash_posted = round(fill_price * quantity, 2)
    row = GameShortPositionRow(
        id=uuid4(),
        user_id=user_id,
        run_id=run_id,
        portfolio_id=portfolio_row.id,
        ticker=ticker,
        quantity=quantity,
        entry_price=fill_price,
        cash_posted=cash_posted,
        fee_paid=fee,
        opened_at=now,
        state="open",
    )
    session.add(row)
    portfolio_row.current_cash = round(
        float(portfolio_row.current_cash) - cash_posted - fee, 2,
    )
    return row


def cover_short(
    session,
    *,
    portfolio_row: SimPortfolioRow,
    short_row: GameShortPositionRow,
    close_price: float,
    fee: float,
    reason: str = "user",
    now: datetime | None = None,
) -> float:
    """Buy to cover, in full. Credits the leg's marked value less the fee,
    settles the row, and returns the realised P&L (fees excluded).

    **Never refused for insufficient cash.** The cash to buy the shares back
    was posted at open and is being returned here; a cover that could be
    blocked by a low balance would leave a player unable to close the one
    position whose loss is unbounded. That is also why this credits rather
    than debits even on a losing short: the loss is taken out of the posted
    cash before it comes back, so the arithmetic cannot produce a refusal.
    """
    now = now or datetime.now(timezone.utc)
    quantity = float(short_row.quantity)
    entry_price = float(short_row.entry_price)
    cash_posted = float(short_row.cash_posted)

    proceeds = short_cover_proceeds(cash_posted, quantity, entry_price, close_price)
    realised = round(short_unrealised_pnl(quantity, entry_price, close_price), 2)

    portfolio_row.current_cash = round(
        float(portfolio_row.current_cash) + proceeds - fee, 2,
    )
    short_row.state = "closed"
    short_row.closed_at = now
    short_row.close_price = close_price
    short_row.close_reason = reason
    short_row.realised_pnl = realised
    session.add(short_row)
    return realised
