"""CR181 — wire schemas for persona telemetry ingest + the segment counts read.

TELEMETRY_EVENT_TYPES is the canonical vocabulary (NOTIFICATION_TYPES
pattern, CR135): an unknown `event_type` is a 422 that names the allowed
set, never a row that silently means nothing. The mobile emitter's Dart
constant list must stay in lockstep with this tuple; its parity test
anchors here. `client_drop` is the emitter's own failure accounting — one
marker row whose `count` says how many events were discarded since the
last successful flush, so a drop is countable (CR040) without pretending
the events survived.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Vocabulary, by the segment predicate it feeds (services/persona_telemetry.py):
#   app_open                          -> bounce denominator ("opened")
#   room_convene                      -> convene; core action
#   one_on_one_open | firm_open |
#     lesson_open                     -> depth (one_on_one/lesson also core)
#   trade_place | challenge_attempt |
#     brief_edit                      -> core actions (kill bounce)
#   client_drop                       -> drop accounting only, never a segment
TELEMETRY_EVENT_TYPES: tuple[str, ...] = (
    "app_open",
    "room_convene",
    "one_on_one_open",
    "firm_open",
    "lesson_open",
    "trade_place",
    "challenge_attempt",
    "brief_edit",
    "client_drop",
)


class TelemetryEventIn(BaseModel):
    event_id: UUID
    event_type: str
    occurred_at: datetime
    locale: Optional[str] = Field(default=None, max_length=16)
    count: int = Field(default=1, ge=1, le=100_000)

    @field_validator("event_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in TELEMETRY_EVENT_TYPES:
            raise ValueError(
                f"unknown event_type {v!r}; allowed: "
                + ", ".join(TELEMETRY_EVENT_TYPES)
            )
        return v


class TelemetryBatchIn(BaseModel):
    events: list[TelemetryEventIn] = Field(min_length=1, max_length=500)


class TelemetryIngestResponse(BaseModel):
    accepted: int
    duplicates: int


class SegmentCountsResponse(BaseModel):
    """The CR181 §2 answering read: run once per window (pre / post Floor
    v0.2) and compare — cohort counts, not a relayed quote."""

    since: datetime
    until: datetime
    users: int
    bounce: int
    convene: int
    depth: int
    locales: dict[str, int]
    dropped_events: int
