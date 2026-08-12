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


class AdminUserDevice(BaseModel):
    """BL2 (AT:R33): one row of the user's device list."""

    device_install_id: UUID
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime


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
    # BL2 (AT:R33): per-install device rows. Empty list for legacy users
    # not yet seen post-BL2; the BL2 backfill seeds one row per user with
    # device_user_id, so most users have at least one row.
    devices: list[AdminUserDevice] = Field(default_factory=list)
    # BL11 (AT:R33): effective plan after trial-expiry downgrade. Differs
    # from `plan` only when trial_expires_at is in the past — surfaces
    # cleanly when a tester's 7-day window has lapsed.
    effective_plan: str
    trial_active: bool
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


class FeatureGate(BaseModel):
    """One config-driven feature and whether it is actually live in this
    process. `configured` is a boolean derived from the setting — never the
    secret value itself (CR040)."""

    name: str
    setting: str
    configured: bool
    effect_when_unconfigured: str


class SettingsFieldState(BaseModel):
    """One `Settings` field and whether this container actually has it — for
    EVERY field, not the hand-picked few (CR175 F3).

    `gates` above is a curated list that must be extended by hand, and measured
    2026-08-12 it covered 9 of 98 fields. The miss that proves the shape:
    `adanos_api_key_secondary` was wired the same week *because* it had sat idle
    undetected, reached compose and `Settings`, and was still invisible to the
    check whose entire job is catching that. Nothing failed, because nothing
    fails when a hand-maintained list is incomplete.

    Derived from `Settings.model_fields`, so a field added tomorrow is covered
    the day it is added. `configured` is a boolean — never the value (CR040).
    """

    setting: str
    configured: bool
    annotated: bool


class AdminConfigCheckResponse(BaseModel):
    env: str
    gates: list[FeatureGate]
    dark_count: int
    # CR175 F3 — the complete field-level map. `gates` stays the curated,
    # human-annotated view (and `dark_count` keeps meaning what it meant);
    # this is what `scripts/promotion/postflight.py` diffs infra/alpha.env
    # against, because a set-diff needs the whole set.
    settings_coverage: list[SettingsFieldState] = []
    settings_total: int = 0
    # DEF113 — the configured 1-on-1 credit price. Not a FeatureGate (those
    # are booleans, "is X configured"); this is a tunable price, so "what are
    # we charging in production" is one curl instead of a code read.
    one_on_one_credit_cost: int
    # CR136 — which Portfolio Health gate mode this container is actually
    # running. Not a FeatureGate either: it is a loud `Literal`, never a
    # presence-gated silent fallback. M11 promotes `trial` → `plan` by env, and
    # this is how "did it take" is answered without reading the container's env.
    portfolio_health_gate_mode: str
    # CR121 — is a client-version floor currently active, and what is it.
    # DB-derived runtime state (client_release_floors), not a Settings
    # presence check, same shape as portfolio_health_gate_mode above. This is
    # the "surfaced in the admin config check" half of the version gate's
    # fail-open contract — an operator can see the gate's live state
    # independent of whether any individual client's own fetch succeeded.
    client_release_floor_configured: bool
    client_release_floor_min_build: Optional[int] = None
