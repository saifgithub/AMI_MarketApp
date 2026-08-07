"""CR121 — client version-gate schemas.

`ReleaseFloorResponse` is the shape of the unauthenticated
`GET /v1/client/release-floor` (main.py, sibling of `/v1/health`) — it must
be answerable before a session exists, because a blocked client may be too
old to authenticate. `action` is computed server-side so a policy change
(raise or retract the floor) takes effect with no client release.

`AdminReleaseFloorRequest` / `AdminReleaseFloorOut` back the authenticated
write side, `POST /v1/admin/release-floor` (api/admin.py), behind the
existing ADMIN_SECRET bearer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReleaseFloorResponse(BaseModel):
    min_build: Optional[int] = None
    recommended_build: Optional[int] = None
    action: Literal["block", "nag", "ok"]
    headline: Optional[str] = None
    body: Optional[str] = None
    store_url: Optional[str] = None


class AdminReleaseFloorRequest(BaseModel):
    """POST /v1/admin/release-floor body. A raise is one API call, no
    deploy — which is the whole point of a DB table over an env var."""

    min_build: int = Field(gt=0)
    recommended_build: Optional[int] = Field(default=None, gt=0)
    headline: str = Field(min_length=1)
    body_en: str = Field(min_length=1)
    body_ar: Optional[str] = None
    body_ms: Optional[str] = None
    created_by: Optional[str] = None
    # Operational footgun guard (CR121 spec): refuses a min_build above the
    # highest build the server has ever observed unless explicitly forced.
    # Raising the floor above what TestFlight has approved bricks every iOS
    # tester with nowhere to go — this is the one flag that overrides that
    # refusal, deliberately opt-in.
    force: bool = False


class AdminReleaseFloorOut(BaseModel):
    id: UUID
    min_build: int
    recommended_build: Optional[int]
    headline: str
    body_en: str
    body_ar: Optional[str]
    body_ms: Optional[str]
    created_at: datetime
    created_by: Optional[str]
    active: bool
    # Echoed back so the operator can see the number the footgun guard
    # compared against, whether or not `force` was needed this time.
    highest_observed_build: int
