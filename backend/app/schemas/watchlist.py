"""Watchlist schemas — A18.

Tickers are free-form strings (anything the market_data provider can
quote). Notes are optional; the iPhone uses them to remind why the user
is watching that name.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


class WatchlistEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    ticker: str
    notes: str | None = None
    added_at: datetime = Field(default_factory=_utcnow)


class WatchlistAddRequest(BaseModel):
    ticker: str
    notes: str | None = None


class WatchlistEntryWithQuote(BaseModel):
    """The list response — entry plus a live quote so the UI doesn't have to
    fan-out one /quote call per row."""

    entry: WatchlistEntry
    price: float | None = None
    day_change_pct: float | None = None
    price_source: str | None = None  # 'live' | 'mock' | None


class WatchlistListResponse(BaseModel):
    items: list[WatchlistEntryWithQuote]
    total: int
