"""CR181 — persona telemetry routes.

POST /v1/telemetry/events   — batched, idempotent ingest for the token's user
GET  /v1/telemetry/segments — admin-only segment counts over [since, until)

The ingest writes only under the authenticated user: `user_id` comes from
the Bearer token, and the payload has nowhere to name one — cross-user
isolation is structural, not validated. Replays are settled by the
(user_id, event_id) constraint and reported back as `duplicates`, so the
client can tell a landed batch from an absorbed one (CR040 — no silent
fallback). The segments read is the CR's §2 answering query behind the
static ADMIN_SECRET bearer (admin back-office pattern); nothing
user-facing renders it, and none of these rows feeds any Room-prompt
surface (DEF098 parity is untouched by design).

Handlers are plain `def` — sync DB work, DEF200 ratchet.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.admin import get_admin
from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.telemetry import (
    SegmentCountsResponse,
    TelemetryBatchIn,
    TelemetryIngestResponse,
)
from app.services import persona_telemetry

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


@router.post("/events", response_model=TelemetryIngestResponse)
def ingest_events(
    batch: TelemetryBatchIn,
    current_user: User = Depends(get_current_user),
) -> TelemetryIngestResponse:
    accepted, duplicates = persona_telemetry.ingest_events(
        current_user.id, batch.events,
    )
    return TelemetryIngestResponse(accepted=accepted, duplicates=duplicates)


@router.get(
    "/segments",
    response_model=SegmentCountsResponse,
    dependencies=[Depends(get_admin)],
)
def segment_counts(
    since: datetime = Query(...),
    until: datetime = Query(...),
) -> SegmentCountsResponse:
    if since >= until:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "since must be before until",
        )
    return SegmentCountsResponse(**persona_telemetry.segment_counts(since, until))
