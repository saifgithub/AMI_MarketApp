"""Admin ticker interest API — /v1/admin/ticker-interest/* (CR200-R001).

Statistical breakdown of which tickers/tickets users research and trade, and
order fulfilment (filled vs. pending vs. rejected/cancelled/expired). Sub-CR
of CR200 — own console tab, not folded into /v1/admin/analytics/*.

Endpoint map:
  GET /v1/admin/ticker-interest/top?days=30&limit=25         Room runs by ticker
  GET /v1/admin/ticker-interest/orders?days=30&limit=25       Fill state by ticker
  GET /v1/admin/ticker-interest/watchlist?days=30&limit=25    Watchlist adds by ticker
  GET /v1/admin/ticker-interest/detail/{ticker}?days=90       One symbol's full history

Gating follows every other admin route: `Depends(get_admin)`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.admin import get_admin
from app.services import ticker_interest

router = APIRouter(
    prefix="/v1/admin/ticker-interest",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


@router.get("/top")
def top_tickers(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    return ticker_interest.top_tickers(days=days, limit=limit)


@router.get("/orders")
def ticker_orders(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    return ticker_interest.ticker_orders(days=days, limit=limit)


@router.get("/watchlist")
def watchlist_interest(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    return ticker_interest.watchlist_interest(days=days, limit=limit)


@router.get("/detail/{ticker}")
def ticker_detail(
    ticker: str,
    days: int = Query(default=90, ge=1, le=365),
) -> dict[str, Any]:
    return ticker_interest.ticker_detail(ticker=ticker, days=days)
