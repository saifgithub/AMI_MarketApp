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
# CR185: `investigating` added for the autonomous bug-report monitor.
# It is distinct from `in_progress` (which pairs with an active /fix-bugs branch
# claim); `investigating` means "triaged, filed a DEF, not yet assigned to coding."
BugStatus = Literal[
    "open",
    "investigating",
    "in_progress",
    "pending_review",
    "resolved",
    "wont_fix",
]

_VALID_PLATFORMS = {"ios", "android_gms", "android_hms"}

MAX_TRACE_IDS = 5


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
    # CR239 / WP-38: the app's most recent request trace ids (comma-separated
    # on the wire, normalised to a list here). Format-validated, never
    # looked up: a report with a bogus id is rejected, not stored.
    trace_ids: list[str] | None = None

    @field_validator("trace_ids", mode="before")
    @classmethod
    def validate_trace_ids(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        parts = v.split(",") if isinstance(v, str) else list(v)  # type: ignore[call-overload]
        out: list[str] = []
        for raw in parts:
            raw = str(raw).strip()
            if not raw:
                continue
            try:
                out.append(str(UUID(raw)))
            except ValueError as exc:
                raise ValueError("trace_ids must be comma-separated UUIDs") from exc
        if len(out) > MAX_TRACE_IDS:
            raise ValueError(f"at most {MAX_TRACE_IDS} trace_ids")
        return out or None

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
