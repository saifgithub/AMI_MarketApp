"""Feedback schemas — bug report request/response.

Category and status are plain strings (not Postgres enums) to keep
migrations simple and make it trivial to add values without a DDL change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

BugCategory = Literal[
    "ui_glitch",
    "wrong_data",
    "crash",
    "performance",
    "feature_request",
    "other",
]

# CR043 (minimal half of CR002): the canonical lifecycle, matching what
# `/fix-bugs` and Saiful actually write. The previous Literal carried
# `triaged`/`fixed` — never written by anything — and lacked `resolved`,
# of which the Alpha DB held 35 rows. That mismatch was harmless only
# while this schema was write-only; `GET /updates` serialises resolved
# rows, so it would have raised ValidationError on every one of them.
BugStatus = Literal[
    "open",
    "in_progress",
    "pending_review",
    "resolved",
    "wont_fix",
]

_VALID_PLATFORMS = {"ios", "android_gms", "android_hms"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BugReportRequest(BaseModel):
    category: BugCategory
    title: str = Field(..., min_length=1, max_length=200)
    steps: str | None = Field(None, max_length=1000)
    route: str | None = None
    app_version: str
    platform: str
    # Optional photo attachment: relative filename inside
    # settings.bug_attachments_dir + the original Content-Type. Set by
    # the API layer after a successful multipart upload; clients never
    # supply these directly.
    attachment_path: str | None = None
    attachment_mime: str | None = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        if v not in _VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {_VALID_PLATFORMS}")
        return v


class BugReportResponse(BaseModel):
    id: UUID
    status: BugStatus
    created_at: datetime
    attachment_path: str | None = None


class BugResolutionUpdate(BaseModel):
    """A resolved report the reporter hasn't been told about yet.

    `resolution_note` is written by Saiful at the moment he flips the
    status and is shown to the reporter verbatim — it is user-facing
    copy, not an engineering note.
    """

    id: UUID
    title: str
    resolved_at: datetime | None = None
    resolution_note: str | None = None
