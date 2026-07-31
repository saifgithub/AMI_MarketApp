"""Watchlist routes (A18).

GET    /v1/watchlist/{user_id}                — list with live quotes
POST   /v1/watchlist/{user_id}                — add ticker (idempotent)
DELETE /v1/watchlist/{user_id}/{ticker}       — remove ticker

The list response embeds a live quote per row so the iPhone doesn't have
to fan-out one /sim/quote call per watchlist entry.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistEntryWithQuote,
    WatchlistListResponse,
)
from app.services.market_data import get_market_data_provider
from app.services.ticker_reference import TickerNotFoundError, ticker_not_found_detail
from app.services.watchlist_store import get_watchlist_store

router = APIRouter(
    prefix="/v1/watchlist",
    tags=["watchlist"],
    dependencies=[Depends(get_current_user)],
)


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.get("/{user_id}", response_model=WatchlistListResponse)
async def list_watchlist(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> WatchlistListResponse:
    _own(current_user, user_id)
    entries = get_watchlist_store().list_for_user(user_id)
    provider = get_market_data_provider()
    items: list[WatchlistEntryWithQuote] = []
    for e in entries:
        try:
            quote = provider.quote(e.ticker)
        except Exception:  # pragma: no cover — defensive
            quote = None
        items.append(WatchlistEntryWithQuote(
            entry=e,
            price=quote.price if quote else None,
            day_change_pct=quote.change_pct if quote else None,
            price_source=quote.source if quote else None,
        ))
    return WatchlistListResponse(items=items, total=len(items))


@router.post(
    "/{user_id}",
    response_model=WatchlistEntryWithQuote,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    user_id: UUID,
    req: WatchlistAddRequest,
    current_user: User = Depends(get_current_user),
) -> WatchlistEntryWithQuote:
    _own(current_user, user_id)
    try:
        entry = get_watchlist_store().add(user_id, req.ticker, req.notes)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ticker_not_found_detail(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    provider = get_market_data_provider()
    try:
        quote = provider.quote(entry.ticker)
    except Exception:  # pragma: no cover — defensive
        quote = None
    return WatchlistEntryWithQuote(
        entry=entry,
        price=quote.price if quote else None,
        day_change_pct=quote.change_pct if quote else None,
        price_source=quote.source if quote else None,
    )


@router.delete("/{user_id}/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    user_id: UUID,
    ticker: str,
    current_user: User = Depends(get_current_user),
) -> None:
    _own(current_user, user_id)
    removed = get_watchlist_store().remove(user_id, ticker)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticker not on watchlist")
