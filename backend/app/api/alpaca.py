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

POST /v1/alpaca/link       — exchange an OAuth code, RETURN the tokens (no storage)
POST /v1/alpaca/link_state — the device reports WHETHER it holds a credential
POST /v1/alpaca/order_log  — the device reports the outcome of a submitOrder() call (CR230)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.schemas.alpaca import AlpacaOrderLogIn
from app.services.alpaca_service import AlpacaError, exchange_code
from app.services.audit import record_alpaca_order

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


class LinkStateRequest(BaseModel):
    linked: bool


class LinkStateResponse(BaseModel):
    linked: bool
    linked_at: datetime | None = None


@router.post("/link_state", response_model=LinkStateResponse)
def report_link_state(
    body: LinkStateRequest,
    current_user: User = Depends(get_current_user),
) -> LinkStateResponse:
    """CR203 — the device tells us it has (or no longer has) a linked account.

    This is the ONLY thing the host learns about a user's Alpaca account, and
    it is deliberately the least it can learn: a boolean, stamped with when it
    was said. No key, no token, nothing that could authenticate to Alpaca.

    **It is a report, not an observation.** The device is the only party that
    can see the credential, so this is necessarily self-declared and can go
    stale in ways this host cannot detect — a revoked key, a wiped app, a new
    phone. That is why the column stores a timestamp and every reader surfaces
    it: an unqualified "linked: true" would assert something we cannot check
    (the DEF059 class). Under-reporting is the safe direction and the one this
    design takes — a device that never calls simply reads as not linked.

    Idempotent: reporting `linked: true` repeatedly refreshes the timestamp,
    which is what makes the value's age meaningful.
    """
    _require_claimed(current_user)

    stamped = datetime.now(timezone.utc) if body.linked else None
    with get_session() as s:
        row = s.execute(select(User).where(User.id == current_user.id)).scalar_one()
        row.alpaca_linked_at = stamped
        s.commit()

    return LinkStateResponse(linked=body.linked, linked_at=stamped)


@router.post("/order_log", status_code=status.HTTP_204_NO_CONTENT)
def log_order(
    body: AlpacaOrderLogIn,
    current_user: User = Depends(get_current_user),
) -> None:
    """CR230 — the device reports the outcome of an `AlpacaClient.submitOrder()`
    call: accepted, rejected by Alpaca, or refused client-side before ever
    reaching Alpaca (wrong order type, non-paper host). Fire-and-forget on
    the client side — the trade ticket's own success/failure banner is
    already final by the time this call is made; a failure to log here must
    never surface as a trade failure.

    Same "report, not observation" posture as `report_link_state` above: the
    backend never holds the Alpaca credential, so it cannot independently
    confirm this against Alpaca's own order book. Write-only in v1 — no read
    endpoint yet.
    """
    _require_claimed(current_user)
    record_alpaca_order(
        user_id=current_user.id,
        symbol=body.symbol,
        side=body.side,
        qty=body.qty,
        destination=body.destination,
        outcome=body.outcome,
        detail=body.detail,
        alpaca_order_id=body.alpaca_order_id,
        alpaca_status=body.alpaca_status,
    )
