"""In-app notification centre routes — CR135 backend half.

GET   /v1/notifications/{user_id}                        — list, newest-first, paginated
POST  /v1/notifications/{user_id}/{notification_id}/read — mark read (idempotent)
POST  /v1/notifications/{user_id}/read_all
GET   /v1/notifications/{user_id}/unread_count
GET   /v1/notifications/{user_id}/preferences
PATCH /v1/notifications/{user_id}/preferences

Ownership is two layers: a path user_id that isn't the token's user is a
403 (price_alerts pattern), and the per-row route 404s on another user's
row — indistinguishable from a nonexistent id, because the user_id
predicate IS the authorization (CR102 pattern). Rows are written only by
notification_service.notify(); this surface never creates notifications.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.notifications import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationPreferencesPatch,
    NotificationPreferencesResponse,
    UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.get("/{user_id}", response_model=NotificationListResponse)
def list_notifications(
    user_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    _own(current_user, user_id)
    items, total = notification_service.list_notifications(
        user_id, limit=limit, offset=offset,
    )
    return NotificationListResponse(items=items, total=total)


@router.post(
    "/{user_id}/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT,
)
def mark_read(
    user_id: UUID,
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
) -> None:
    _own(current_user, user_id)
    if not notification_service.mark_read(user_id, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")


@router.post("/{user_id}/read_all", response_model=MarkAllReadResponse)
def mark_all_read(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> MarkAllReadResponse:
    _own(current_user, user_id)
    return MarkAllReadResponse(updated=notification_service.mark_all_read(user_id))


@router.get("/{user_id}/unread_count", response_model=UnreadCountResponse)
def unread_count(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    _own(current_user, user_id)
    return UnreadCountResponse(unread=notification_service.unread_count(user_id))


@router.get("/{user_id}/preferences", response_model=NotificationPreferencesResponse)
def get_preferences(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    _own(current_user, user_id)
    return NotificationPreferencesResponse(
        items=notification_service.get_preferences(user_id),
    )


@router.patch("/{user_id}/preferences", response_model=NotificationPreferencesResponse)
def patch_preferences(
    user_id: UUID,
    req: NotificationPreferencesPatch,
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    _own(current_user, user_id)
    try:
        items = notification_service.set_preferences(user_id, req.updates)
    except ValueError as exc:
        # Schema validation already 422s unknown types; this is the same
        # loudness if the service is ever reached another way (CR040).
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc),
        ) from exc
    return NotificationPreferencesResponse(items=items)
