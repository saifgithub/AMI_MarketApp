"""Alpaca paper trading service.

Handles OAuth token exchange and proxies calls to the Alpaca Paper API.
All functions are synchronous — same as market_data.py — suitable for
FastAPI endpoints with `Depends()`.

Token exchange: POST to Alpaca's OAuth token endpoint with the auth code
returned by the embedded WebView. The client_secret stays server-side.

Portfolio proxy: GET calls to paper-api.alpaca.markets on behalf of the
user using their stored access_token. All calls are best-effort; callers
should catch AlpacaError and surface an appropriate HTTP error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import logger


class AlpacaError(Exception):
    """Raised when the Alpaca API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Alpaca {status_code}: {detail}")


@dataclass
class AlpacaTokens:
    access_token: str
    refresh_token: str


@dataclass
class AlpacaAccount:
    cash: float
    portfolio_value: float
    equity: float
    buying_power: float


@dataclass
class AlpacaPosition:
    symbol: str
    qty: float
    market_value: float
    unrealized_pl: float


_TIMEOUT = httpx.Timeout(10.0)


def exchange_code(code: str) -> AlpacaTokens:
    """Exchange an OAuth auth code for access + refresh tokens.

    The code is single-use and expires quickly; this must be called
    immediately after the WebView intercepts the callback URL.
    """
    if not settings.alpaca_client_id or not settings.alpaca_client_secret:
        raise AlpacaError(503, "Alpaca OAuth not configured — set ALPACA_CLIENT_ID + ALPACA_CLIENT_SECRET")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.alpaca_client_id,
        "client_secret": settings.alpaca_client_secret,
        "redirect_uri": settings.alpaca_redirect_uri,
    }
    try:
        resp = httpx.post(settings.alpaca_oauth_token_url, data=payload, timeout=_TIMEOUT)
    except httpx.RequestError as exc:
        raise AlpacaError(503, f"token exchange network error: {exc}") from exc

    if resp.status_code != 200:
        logger.warning("alpaca_token_exchange_failed", status=resp.status_code, body=resp.text[:200])
        raise AlpacaError(resp.status_code, resp.text[:200])

    data = resp.json()
    return AlpacaTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
    )


def _paper_get(access_token: str, path: str, params: dict | None = None) -> dict | list:
    """Authenticated GET against the Alpaca paper API."""
    url = f"{settings.alpaca_paper_base_url}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=_TIMEOUT)
    except httpx.RequestError as exc:
        raise AlpacaError(503, f"Alpaca network error: {exc}") from exc

    if resp.status_code == 401:
        raise AlpacaError(401, "Alpaca token expired or revoked — relink required")
    if resp.status_code != 200:
        raise AlpacaError(resp.status_code, resp.text[:200])

    return resp.json()


def get_account(access_token: str) -> AlpacaAccount:
    """Fetch the paper account summary (cash, equity, etc.)."""
    data = _paper_get(access_token, "/v2/account")
    return AlpacaAccount(
        cash=float(data.get("cash", 0)),
        portfolio_value=float(data.get("portfolio_value", 0)),
        equity=float(data.get("equity", 0)),
        buying_power=float(data.get("buying_power", 0)),
    )


def get_positions(access_token: str) -> list[AlpacaPosition]:
    """Fetch all open paper positions."""
    data = _paper_get(access_token, "/v2/positions")
    positions = []
    for item in data:  # type: ignore[union-attr]
        positions.append(
            AlpacaPosition(
                symbol=item.get("symbol", ""),
                qty=float(item.get("qty", 0)),
                market_value=float(item.get("market_value", 0)),
                unrealized_pl=float(item.get("unrealized_pl", 0)),
            )
        )
    return positions


def snapshot_text(access_token: str) -> str | None:
    """Build a compact text block for agent prompt injection.

    Returns None on any error so callers can safely skip the block.
    Format matches the HANDOVER spec:
      --- LIVE ALPACA PAPER PORTFOLIO ---
      Cash: $12,450.00 | Portfolio value: $48,320.00
      Positions: AAPL ×10 ($2,150 unrealised +$85), ...
      ---
    """
    try:
        account = get_account(access_token)
        positions = get_positions(access_token)
    except AlpacaError as exc:
        logger.warning("alpaca_snapshot_failed", detail=exc.detail)
        return None

    pos_parts = []
    for p in positions:
        sign = "+" if p.unrealized_pl >= 0 else ""
        pos_parts.append(
            f"{p.symbol} ×{p.qty:g} (${p.market_value:,.0f} unrealised {sign}${p.unrealized_pl:,.0f})"
        )
    pos_text = ", ".join(pos_parts) if pos_parts else "no open positions"

    return (
        f"--- LIVE ALPACA PAPER PORTFOLIO ---\n"
        f"Cash: ${account.cash:,.2f} | Portfolio value: ${account.portfolio_value:,.2f}"
        f" | Buying power: ${account.buying_power:,.2f}\n"
        f"Positions: {pos_text}\n"
        f"---"
    )
