"""Beta Room thumbs routes (CR278 / CR267 WP-36).

    POST /v1/room/{run_id}/rating      owner only; one answer per Room, changeable
    GET  /v1/admin/room-ratings        admin: totals + newest ratings (WP-53 exit report)

The user route is a second router on the `/v1/room` prefix so `room.py` (large,
shared) stays untouched; the admin route follows `/v1/admin/config-check`'s
gating exactly (`Depends(get_admin)`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, StrictBool

from app.api.admin import get_admin
from app.api.dependencies import get_current_user
from app.db.models import User
from app.services import room_rating

router = APIRouter(prefix="/v1/room", tags=["room"])
admin_router = APIRouter(
    prefix="/v1/admin/room-ratings",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


class RoomRatingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    helpful: StrictBool


class RoomRatingOut(BaseModel):
    run_id: UUID
    helpful: bool
    created_at: datetime
    updated_at: datetime
    changed: bool


@router.post("/{run_id}/rating", response_model=RoomRatingOut)
def rate_room(
    run_id: UUID,
    body: RoomRatingIn,
    current_user: User = Depends(get_current_user),
) -> RoomRatingOut:
    try:
        stored = room_rating.set_rating(
            run_id=run_id, user_id=current_user.id, helpful=body.helpful,
        )
    except room_rating.RoomNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room run not found")
    except room_rating.NotRoomOwner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    except room_rating.RoomNotRateable:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this Room has no verdict to rate yet",
        )
    return RoomRatingOut(
        run_id=stored.run_id, helpful=stored.helpful,
        created_at=stored.created_at, updated_at=stored.updated_at,
        changed=stored.changed,
    )


@admin_router.get("")
def room_ratings_summary(
    limit: int = Query(100, ge=1, le=1000),
    since: datetime | None = None,
) -> dict[str, Any]:
    return room_rating.summary(limit=limit, since=since)
