"""Ticker existence validation (CR128).

GET /v1/tickers/validate?ticker=XXX

Called by the Flutter client at submit-time from all three ticker-entry
points (Convene the Room, Start Trade, Add to Watchlist) before the actual
action request. No auth — read-only reference lookup, no user-specific data,
same shape as `/v1/glossary/*`.

GET /v1/tickers/resolve?q=&market=US|MY (CR283) — company name -> ticker
candidates on one market, for the Floor search box. Same no-auth reference
shape. Upstream failure is a 503 with a reason, never an empty list.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.db import get_session
from app.schemas.tickers import (
    TickerCandidate,
    TickerResolveResponse,
    TickerSuggestion,
    TickerValidateResponse,
)
from app.services import ticker_resolve
from app.services.ticker_reference import lookup_ticker, suggest_closest
from app.trading_math.markets import (
    Market,
    accepted_without_reference,
    market_enabled,
    spec_for,
)

router = APIRouter(prefix="/v1/tickers", tags=["tickers"])


@router.get("/validate", response_model=TickerValidateResponse)
def validate_ticker(ticker: str = Query(..., min_length=1)) -> TickerValidateResponse:
    normalized = ticker.upper().strip()
    with get_session() as session:
        row = lookup_ticker(session, normalized)
        if row is not None:
            return TickerValidateResponse(
                ticker=row.symbol,
                exists=True,
                company_name=row.company_name,
                exchange=row.exchange,
            )
        if accepted_without_reference(normalized):
            return TickerValidateResponse(
                ticker=normalized,
                exists=True,
                exchange=spec_for(Market.MY).exchange_label,
            )
        candidates = suggest_closest(session, normalized, limit=1)
        suggestion = None
        if candidates:
            match = candidates[0]
            suggestion = TickerSuggestion(
                ticker=match.symbol,
                company_name=match.company_name,
                exchange=match.exchange,
            )
        return TickerValidateResponse(ticker=normalized, exists=False, suggestion=suggestion)


@router.get("/resolve", response_model=TickerResolveResponse)
def resolve_ticker(
    q: str = Query(..., min_length=1, max_length=60),
    market: str = Query(...),
) -> TickerResolveResponse:
    try:
        m = Market(market.upper())
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown market: {market!r}",
        ) from None
    if not market_enabled(m):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{spec_for(m).exchange_label} is not available yet.",
        )
    query = q.strip()
    if not query:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "q must not be blank")
    try:
        found = ticker_resolve.resolve(query, m)
    except ticker_resolve.TickerResolveUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Name lookup is unavailable right now ({exc}).",
        ) from exc
    return TickerResolveResponse(
        query=query,
        market=m.value,
        candidates=[
            TickerCandidate(
                ticker=c.ticker,
                market=c.market.value,
                short_name=c.short_name,
                long_name=c.long_name,
            )
            for c in found
        ],
    )
