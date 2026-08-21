"""Alpaca paper trading routes.

**CR202 — almost nothing is left here, and that is the point.** The user's
Alpaca credentials live on their device and the device talks to
`paper-api.alpaca.markets` directly, so the status / portfolio / positions
proxies and both link-and-store routes are gone along with the columns they
wrote to. Link state is device-local; there is nothing on this host to ask.

The one surviving route is the parked OAuth token exchange. Alpaca's token
endpoint requires `client_secret` and documents no PKCE, so that single call
cannot move to the device — but its result can: this returns the tokens to the
caller and stores nothing. It is unreachable today (`ALPACA_CLIENT_ID` unset,
client OAuth tab disabled) and exists so the OAuth path stays open without
re-introducing host custody.

POST /v1/alpaca/link — exchange an OAuth code, RETURN the tokens (no storage)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.db.models import User
from app.services.alpaca_service import AlpacaError, exchange_code

router = APIRouter(prefix="/v1/alpaca", tags=["alpaca"])


def _require_claimed(user: User) -> User:
    if user.is_anonymous:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account not claimed")
    return user


class LinkRequest(BaseModel):
    code: str


class LinkResponse(BaseModel):
    """The tokens go straight back to the device, which is the only place they
    are ever stored. Both field names match `http_audit`'s structural
    secret-field scrubber (DEF181), so neither is written to the audit log."""

    access_token: str
    refresh_token: str


@router.post("/link", response_model=LinkResponse, status_code=status.HTTP_200_OK)
def link_alpaca(
    body: LinkRequest,
    current_user: User = Depends(get_current_user),
) -> LinkResponse:
    _require_claimed(current_user)
    try:
        tokens = exchange_code(body.code)
    except AlpacaError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.detail) from exc

    return LinkResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
