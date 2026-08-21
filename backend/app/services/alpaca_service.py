"""Alpaca paper trading service.

**CR202 — this host holds no Alpaca credential.** The user's key ID and secret
live on their device (Keychain / Keystore) and the device calls
`paper-api.alpaca.markets` itself. What arrives here is a validated snapshot of
the *result* (`schemas/alpaca.AlpacaSnapshotIn`), supplied per request and never
stored. So this module makes **zero authenticated calls to a user's account** —
a strictly stronger property than the read-only one DEF145 originally locked,
and `tests/unit/test_def145_alpaca_stays_read_only.py` pins it.

What remains:

* `exchange_code` — the parked OAuth token exchange. Alpaca's token endpoint
  requires `client_secret` and documents no PKCE, so this exchange is the one
  Alpaca call that cannot move to the device. It is not reachable today
  (`ALPACA_CLIENT_ID` is unset and the client's OAuth tab is disabled) and it
  reads and writes nothing on the account — it trades an auth code for a token
  against Alpaca's *auth* host. Its caller returns the token to the device
  rather than storing it.
* `snapshot_text` / `render_snapshot` — pure formatting. No HTTP, no
  credentials. One renderer of the block, so the device can never control the
  layout of what lands in an agent prompt (the DEF098 class: two renderers of
  one rule, neither a superset).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.schemas.alpaca import AlpacaSnapshotIn


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
    immediately after the client intercepts the callback URL.

    CR202: the caller returns these tokens to the device. Nothing is persisted
    here — the device is the only place an Alpaca credential lives.
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


def snapshot_text(account: AlpacaAccount, positions: list[AlpacaPosition]) -> str:
    """Build a compact text block for agent prompt injection.

    Pure formatting — the caller has already obtained and validated the data.
    Format is unchanged from the pre-CR202 host-fetched version:
      --- LIVE ALPACA PAPER PORTFOLIO ---
      Cash: $12,450.00 | Portfolio value: $48,320.00 | Buying power: $...
      Positions: AAPL ×10 ($2,150 unrealised +$85), ...
      ---
    """
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


def render_snapshot(payload: AlpacaSnapshotIn | None) -> str | None:
    """Render a device-supplied snapshot into the prompt block, or None.

    None in ⇒ None out ⇒ no overlay, which is the path every user without a
    linked account already takes. This is the ONLY bridge from the wire model
    to the prompt: the device supplies validated values, this supplies the
    layout.
    """
    if payload is None:
        return None
    return snapshot_text(
        AlpacaAccount(
            cash=payload.cash,
            portfolio_value=payload.portfolio_value,
            # The device does not report `equity` — the block never showed it.
            equity=payload.portfolio_value,
            buying_power=payload.buying_power,
        ),
        [
            AlpacaPosition(
                symbol=p.symbol,
                qty=p.qty,
                market_value=p.market_value,
                unrealized_pl=p.unrealized_pl,
            )
            for p in payload.positions
        ],
    )
