"""CR102 — request/response schemas for in-app tester messaging.

User side: inbox rows + replies. Admin side: audience spec, preview
(count-only, no writes), send, broadcast listing, and the reply feed.
The Audience model is strict (`extra="forbid"`) so an unsupported key —
e.g. `platform`, deferred out of CR102 — errors loudly instead of being
silently ignored (CR040).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Audience(BaseModel):
    """Who a broadcast targets. One mode, mode-specific fields.

    Every mode — including explicit `user` ids — passes through the base
    real-tester filter (suspended, house desks, synthetics, seed rows,
    by-id exclusions); see inbox_store.resolve_audience.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["all", "build", "activity", "user"]
    # mode=build: users whose newest device build int (after '+') is < this.
    # Plain int compare on the build number, never semver (CR121 precedent).
    app_version_lt: Optional[str] = None
    # mode=activity: exactly one of the two windows.
    active_within_days: Optional[int] = Field(default=None, ge=1)
    dormant_beyond_days: Optional[int] = Field(default=None, ge=1)
    # mode=user: explicit ids.
    user_ids: Optional[list[UUID]] = None

    @model_validator(mode="after")
    def _mode_fields(self) -> "Audience":
        if self.mode == "build":
            if not self.app_version_lt or "+" not in self.app_version_lt:
                raise ValueError(
                    "mode=build requires app_version_lt with a '+<build>' suffix"
                )
            try:
                int(self.app_version_lt.split("+", 1)[1])
            except ValueError:
                raise ValueError(
                    "app_version_lt build suffix must be an integer"
                ) from None
        if self.mode == "activity":
            if (self.active_within_days is None) == (self.dormant_beyond_days is None):
                raise ValueError(
                    "mode=activity requires exactly one of "
                    "active_within_days / dormant_beyond_days"
                )
        if self.mode == "user" and not self.user_ids:
            raise ValueError("mode=user requires a non-empty user_ids list")
        return self


class AdminSendRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    # Optional translations keyed by locale, e.g. {"ar": "...", "ms": "..."}.
    body_i18n: Optional[dict[str, str]] = None
    priority: Literal["normal", "high"] = "normal"
    audience: Audience


class PreviewResponse(BaseModel):
    recipient_count: int


class SendResponse(BaseModel):
    broadcast_id: UUID
    recipient_count: int


class InboxMessageOut(BaseModel):
    id: UUID
    broadcast_id: Optional[UUID]
    direction: Literal["out", "in"]
    title: Optional[str]
    body: str
    # Broadcast priority for direction='out' rows (drives the high-priority
    # cold-start toast); None on replies.
    priority: Optional[str]
    reply_to_id: Optional[UUID]
    created_at: datetime
    read_at: Optional[datetime]
    toasted_at: Optional[datetime]


class ReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ReplyOut(BaseModel):
    id: UUID
    user_id: UUID
    broadcast_id: Optional[UUID]
    reply_to_id: Optional[UUID]
    body: str
    created_at: datetime


class BroadcastOut(BaseModel):
    id: UUID
    title: str
    body: str
    priority: str
    audience: dict
    recipient_count: int
    reply_count: int
    created_at: datetime
