"""WatchlistStore — Postgres-backed user watchlist (A18).

Tickers are stored upper-cased and free-form (anything the configured
market_data provider can quote). Adding the same ticker twice is a no-op:
the unique constraint on (user_id, ticker) prevents duplicates; the insert goes
through `claim()` (ISS001) so a concurrent loser gets the winner's row.

Why a dedicated store rather than a column on sim_portfolios: a watchlist
isn't a portfolio. The user can watch names they have no intention of
trading (research, learning, idle interest). Keeping it separate keeps the
sim_engine focused on positions + trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select

from app.db import get_session, init_schema
from app.db.ami_claim import claim
from app.db.models import SimWatchlistRow
from app.schemas.watchlist import WatchlistEntry
from app.services.ticker_reference import require_ticker_exists


class WatchlistStore:
    def __init__(self) -> None:
        init_schema()

    def list_for_user(self, user_id: UUID) -> list[WatchlistEntry]:
        with get_session() as s:
            rows = s.execute(
                select(SimWatchlistRow)
                .where(SimWatchlistRow.user_id == user_id)
                .order_by(SimWatchlistRow.added_at.desc())
            ).scalars().all()
            return [_row_to_entry(r) for r in rows]

    def add(self, user_id: UUID, ticker: str, notes: str | None = None) -> WatchlistEntry:
        ticker_norm = ticker.strip().upper()
        if not ticker_norm:
            raise ValueError("ticker cannot be empty")
        with get_session() as s:
            # CR128: defense in depth — the client already checked via
            # GET /v1/tickers/validate. Raises TickerNotFoundError (a
            # ValueError subclass); the route catches it specifically for a
            # structured 422 before the generic ValueError -> 400 mapping.
            require_ticker_exists(s, ticker_norm)
            # ISS001 / DEF308: the row existing is the goal; a loser that supplied notes still
            # applies them (add() has always meant "update notes if supplied").
            row = claim(
                s, SimWatchlistRow,
                key={"user_id": user_id, "ticker": ticker_norm},
                values={"notes": notes, "added_at": datetime.now(timezone.utc)},
            ).or_update(lambda r: setattr(r, "notes", notes) if notes is not None else None)
            return _row_to_entry(row)

    def remove(self, user_id: UUID, ticker: str) -> bool:
        ticker_norm = ticker.strip().upper()
        with get_session() as s:
            res = s.execute(
                delete(SimWatchlistRow).where(
                    SimWatchlistRow.user_id == user_id,
                    SimWatchlistRow.ticker == ticker_norm,
                )
            )
            return (res.rowcount or 0) > 0

    def clear(self) -> None:
        """Wipe — used by tests."""
        with get_session() as s:
            s.execute(delete(SimWatchlistRow))


def _row_to_entry(row: SimWatchlistRow) -> WatchlistEntry:
    return WatchlistEntry(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        notes=row.notes,
        added_at=row.added_at,
    )


_store: WatchlistStore | None = None


def get_watchlist_store() -> WatchlistStore:
    global _store
    if _store is None:
        _store = WatchlistStore()
    return _store
