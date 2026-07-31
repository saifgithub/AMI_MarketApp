"""Price alert routes (CR027 §4).

POST   /v1/price_alerts/{user_id}              — create (active)
GET    /v1/price_alerts/{user_id}?status=      — list, optionally filtered
DELETE /v1/price_alerts/{user_id}/{alert_id}   — cancel (soft — never a
                                                  real delete, audit trail)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.price_alert import (
    PriceAlertCreate,
    PriceAlertListResponse,
    PriceAlertOut,
)
from app.services.price_alert_store import (
    PriceAlertConflictError,
    get_price_alert_store,
)
from app.services.ticker_reference import TickerNotFoundError, ticker_not_found_detail

router = APIRouter(
    prefix="/v1/price_alerts",
    tags=["price_alerts"],
    dependencies=[Depends(get_current_user)],
)


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.post("/{user_id}", response_model=PriceAlertOut, status_code=status.HTTP_201_CREATED)
async def create_price_alert(
    user_id: UUID,
    req: PriceAlertCreate,
    current_user: User = Depends(get_current_user),
) -> PriceAlertOut:
    _own(current_user, user_id)
    try:
        return get_price_alert_store().create(user_id, req)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ticker_not_found_detail(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/{user_id}", response_model=PriceAlertListResponse)
async def list_price_alerts(
    user_id: UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
) -> PriceAlertListResponse:
    _own(current_user, user_id)
    items = get_price_alert_store().list_for_user(user_id, status=status_filter)
    return PriceAlertListResponse(items=items, total=len(items))


@router.delete("/{user_id}/{alert_id}", response_model=PriceAlertOut)
async def cancel_price_alert(
    user_id: UUID,
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
) -> PriceAlertOut:
    _own(current_user, user_id)
    try:
        cancelled = get_price_alert_store().cancel(user_id, alert_id)
    except PriceAlertConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if cancelled is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "price alert not found")
    return cancelled
