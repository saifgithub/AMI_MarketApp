"""Alpaca paper trading routes.

All routes require a claimed (non-anonymous) user via get_current_user.
Anonymous users receive 403 — they have no account to link.

POST /v1/alpaca/link          — exchange OAuth code, store tokens
DELETE /v1/alpaca/unlink      — clear stored tokens
GET  /v1/alpaca/status        — is this user linked?
GET  /v1/alpaca/portfolio     — proxied paper account summary
GET  /v1/alpaca/positions     — proxied paper positions list
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.services.alpaca_service import (
    AlpacaError,
    exchange_code,
    get_account,
    get_positions,
)

router = APIRouter(prefix="/v1/alpaca", tags=["alpaca"])


def _require_claimed(user: User) -> User:
    if user.is_anonymous:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account not claimed")
    return user


def _require_linked(user: User) -> str:
    if not user.alpaca_access_token:
        raise HTTPException(status.HTTP_409_CONFLICT, "alpaca_not_linked")
    return user.alpaca_access_token


# ── Schemas ──────────────────────────────────────────────────────────────


class LinkRequest(BaseModel):
    code: str


class LinkResponse(BaseModel):
    linked: bool
    linked_at: datetime


class StatusResponse(BaseModel):
    linked: bool
    linked_at: datetime | None = None


class PortfolioResponse(BaseModel):
    cash: float
    portfolio_value: float
    equity: float
    buying_power: float


class PositionResponse(BaseModel):
    symbol: str
    qty: float
    market_value: float
    unrealized_pl: float


# ── Routes ───────────────────────────────────────────────────────────────


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

    linked_at = datetime.now(timezone.utc)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == current_user.id)).scalar_one()
        row.alpaca_access_token = tokens.access_token
        row.alpaca_refresh_token = tokens.refresh_token
        row.alpaca_linked_at = linked_at
        s.commit()

    return LinkResponse(linked=True, linked_at=linked_at)


@router.delete("/unlink", status_code=status.HTTP_200_OK)
def unlink_alpaca(
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_claimed(current_user)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == current_user.id)).scalar_one()
        row.alpaca_access_token = None
        row.alpaca_refresh_token = None
        row.alpaca_linked_at = None
        s.commit()
    return {"unlinked": True}


@router.get("/status", response_model=StatusResponse)
def alpaca_status(
    current_user: User = Depends(get_current_user),
) -> StatusResponse:
    _require_claimed(current_user)
    return StatusResponse(
        linked=bool(current_user.alpaca_access_token),
        linked_at=current_user.alpaca_linked_at,
    )


@router.get("/portfolio", response_model=PortfolioResponse)
def alpaca_portfolio(
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    _require_claimed(current_user)
    token = _require_linked(current_user)
    try:
        account = get_account(token)
    except AlpacaError as exc:
        code = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, exc.detail) from exc
    return PortfolioResponse(
        cash=account.cash,
        portfolio_value=account.portfolio_value,
        equity=account.equity,
        buying_power=account.buying_power,
    )


@router.get("/positions", response_model=list[PositionResponse])
def alpaca_positions(
    current_user: User = Depends(get_current_user),
) -> list[PositionResponse]:
    _require_claimed(current_user)
    token = _require_linked(current_user)
    try:
        positions = get_positions(token)
    except AlpacaError as exc:
        code = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, exc.detail) from exc
    return [
        PositionResponse(
            symbol=p.symbol,
            qty=p.qty,
            market_value=p.market_value,
            unrealized_pl=p.unrealized_pl,
        )
        for p in positions
    ]
