"""CR135 — wire schemas for the in-app notification centre.

NOTIFICATION_TYPES is the canonical vocabulary of every `type` the service
actually emits today — the preference toggles are keyed by it, and it is
the anchor the mobile half's Dart enum parity test (DEF210 class) will
check against. A new emitter adds its type string here in the same commit
that introduces it; test_cr135_notifications_api.py asserts every current
emitter's constant is present, so drift fails the suite, not the user.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

# Every type notification_service.notify() is called with today, by emitter:
#   price_alert_evaluator  -> price_alert
#   daily_reminder         -> daily_reminder
#   games_push             -> game_entries_closing | game_final_stretch |
#                             game_settled | game_rank_move
#   sim_order_push         -> resting_order_filled | resting_order_triggered |
#                             resting_order_rejected
NOTIFICATION_TYPES: tuple[str, ...] = (
    "price_alert",
    "daily_reminder",
    "game_entries_closing",
    "game_final_stretch",
    "game_settled",
    "game_rank_move",
    "resting_order_filled",
    "resting_order_triggered",
    "resting_order_rejected",
)


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    deep_link: dict[str, Any]
    source_ref: Optional[str]
    read_at: Optional[datetime]
    created_at: datetime


class NotificationListResponse(BaseModel):
    """One page, newest-first. `total` counts the user's whole history so
    the client can page without a second endpoint."""

    items: list[NotificationOut]
    total: int


class UnreadCountResponse(BaseModel):
    unread: int


class MarkAllReadResponse(BaseModel):
    updated: int


class NotificationPreferenceOut(BaseModel):
    """`updated_at is None` means never toggled — the enabled=True default,
    not a stored row."""

    type: str
    enabled: bool
    updated_at: Optional[datetime]


class NotificationPreferencesResponse(BaseModel):
    items: list[NotificationPreferenceOut]


class NotificationPreferencesPatch(BaseModel):
    """Partial update: only the types named change. Unknown types are a
    loud 422 naming the offender (CR040) — silently ignoring one would let
    a stale client believe it disabled something it didn't."""

    updates: dict[str, bool]

    @field_validator("updates")
    @classmethod
    def _known_types_only(cls, v: dict[str, bool]) -> dict[str, bool]:
        if not v:
            raise ValueError("updates must name at least one notification type")
        unknown = sorted(set(v) - set(NOTIFICATION_TYPES))
        if unknown:
            raise ValueError(
                f"unknown notification type(s): {', '.join(unknown)}"
            )
        return v
