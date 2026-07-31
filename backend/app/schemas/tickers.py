"""Ticker existence validation schemas (CR128).

Shared shape between `GET /v1/tickers/validate` (the client's pre-submit
check) and the 422 body the three action endpoints (Room convene, trade
preview/submit, watchlist add) return when their server-side guard rejects a
ticker a client somehow still submitted.
"""

from __future__ import annotations

from pydantic import BaseModel


class TickerSuggestion(BaseModel):
    ticker: str
    company_name: str
    exchange: str


class TickerValidateResponse(BaseModel):
    ticker: str
    exists: bool
    company_name: str | None = None
    exchange: str | None = None
    suggestion: TickerSuggestion | None = None
