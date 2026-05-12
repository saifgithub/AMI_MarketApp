"""Watchlist routes (A18).

GET    /v1/watchlist/{user_id}                — list with live quotes
POST   /v1/watchlist/{user_id}                — add ticker (idempotent)
DELETE /v1/watchlist/{user_id}/{ticker}       — remove ticker

The list response embeds a live quote per row so the iPhone doesn't have
to fan-out one /sim/quote call per watchlist entry. Day-change% is
omitted for now — the configured market_data provider doesn't surface
the previous close yet (W11 was just point-in-time price). When that
lands, drop it into the schema with no client change.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistEntryWithQuote,
    WatchlistListResponse,
)
from app.services.market_data import get_market_data_provider
from app.services.watchlist_store import get_watchlist_store

router = APIRouter(prefix="/v1/watchlist", tags=["watchlist"])


@router.get("/{user_id}", response_model=WatchlistListResponse)
async def list_watchlist(user_id: UUID) -> WatchlistListResponse:
    entries = get_watchlist_store().list_for_user(user_id)
    provider = get_market_data_provider()
    source = getattr(provider, "name", None)
    items: list[WatchlistEntryWithQuote] = []
    for e in entries:
        try:
            price = provider.get_price(e.ticker)
        except Exception:  # pragma: no cover — defensive
            price = None
        items.append(WatchlistEntryWithQuote(
            entry=e, price=price, day_change_pct=None, price_source=source,
        ))
    return WatchlistListResponse(items=items, total=len(items))


@router.post(
    "/{user_id}",
    response_model=WatchlistEntryWithQuote,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    user_id: UUID, req: WatchlistAddRequest,
) -> WatchlistEntryWithQuote:
    try:
        entry = get_watchlist_store().add(user_id, req.ticker, req.notes)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    provider = get_market_data_provider()
    try:
        price = provider.get_price(entry.ticker)
    except Exception:  # pragma: no cover — defensive
        price = None
    return WatchlistEntryWithQuote(
        entry=entry,
        price=price,
        day_change_pct=None,
        price_source=getattr(provider, "name", None),
    )


@router.delete("/{user_id}/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(user_id: UUID, ticker: str) -> None:
    removed = get_watchlist_store().remove(user_id, ticker)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticker not on watchlist")
