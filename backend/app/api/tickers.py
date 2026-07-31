"""Ticker existence validation (CR128).

GET /v1/tickers/validate?ticker=XXX

Called by the Flutter client at submit-time from all three ticker-entry
points (Convene the Room, Start Trade, Add to Watchlist) before the actual
action request. No auth — read-only reference lookup, no user-specific data,
same shape as `/v1/glossary/*`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import get_session
from app.schemas.tickers import TickerSuggestion, TickerValidateResponse
from app.services.ticker_reference import lookup_ticker, suggest_closest

router = APIRouter(prefix="/v1/tickers", tags=["tickers"])


@router.get("/validate", response_model=TickerValidateResponse)
async def validate_ticker(ticker: str = Query(..., min_length=1)) -> TickerValidateResponse:
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
