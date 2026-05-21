"""Admin back-office request + response schemas (AT:R27).

All endpoints under /v1/admin/ use these shapes. The `get_admin` dependency
in api/admin.py validates the static ADMIN_SECRET bearer before any of these
schemas are ever deserialised.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request bodies ────────────────────────────────────────────────────────────

class AdminPlanChangeRequest(BaseModel):
    plan: str
    note: Optional[str] = None


class AdminTrialGrantRequest(BaseModel):
    days: int = Field(gt=0, description="Trial length in calendar days")
    note: Optional[str] = None


class AdminTrialUpdateRequest(BaseModel):
    action: Literal["extend", "revoke"]
    days: Optional[int] = Field(default=None, gt=0, description="Days to add (extend only)")
    note: Optional[str] = None


class AdminCreditsRequest(BaseModel):
    delta: int = Field(description="Positive = add, negative = deduct")
    note: Optional[str] = None


class AdminNoteRequest(BaseModel):
    note: Optional[str] = None


# ── Response shapes ───────────────────────────────────────────────────────────

class AdminUserSummary(BaseModel):
    id: UUID
    email: Optional[str]
    plan: str
    credit_balance: int
    is_anonymous: bool
    suspended_at: Optional[datetime]
    trial_expires_at: Optional[datetime]
    created_at: datetime


class SubscriptionEventOut(BaseModel):
    id: UUID
    user_id: UUID
    event_type: str
    from_value: Optional[str]
    to_value: Optional[str]
    source: str
    admin_id: Optional[UUID]
    note: Optional[str]
    created_at: datetime


class AdminUserDetail(BaseModel):
    id: UUID
    email: Optional[str]
    phone: Optional[str]
    apple_id: Optional[str]
    google_id: Optional[str]
    plan: str
    credit_balance: int
    locale: str
    timezone: str
    is_anonymous: bool
    device_user_id: Optional[UUID]
    # BL1 (AT:R33): device + build context, refreshed on every /v1/auth/anon.
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    last_app_version: Optional[str] = None
    suspended_at: Optional[datetime]
    trial_started_at: Optional[datetime]
    trial_expires_at: Optional[datetime]
    claimed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    recent_events: list[SubscriptionEventOut] = Field(default_factory=list)


class AdminEventsResponse(BaseModel):
    events: list[SubscriptionEventOut]
    total: int
    limit: int
    offset: int
