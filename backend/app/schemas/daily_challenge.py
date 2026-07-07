"""Daily-challenge schemas.

One JSON file per month at `content/daily_challenges/YYYY_MM.json` — a flat
list of challenge objects. The id format is `dc_YYYY_MM_DD_<slug>`, so the
day number is encoded in the id. Server-side "today" selection reads the
canonical Asia/Kuala_Lumpur date and matches the prefix.

Each challenge is a single-question multiple-choice prompt with one correct
answer index, plus an explanation that surfaces after the user submits.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailyChallenge(BaseModel):
    id: str
    type: str
    difficulty: int = Field(ge=1, le=5)
    locale: str = "en"
    scenario: str
    question: str
    options: list[str]
    answer: int = Field(ge=0)
    explanation: str
    related_lesson: str | None = None
    related_agent: str | None = None
    tags: list[str] = Field(default_factory=list)


class MyAttempt(BaseModel):
    """The caller's stored answer for a challenge (CR004 — server truth;
    lets the mobile card render the answered state after a restart)."""

    selected_option: int
    correct: bool
    attempted_at: str  # ISO 8601


class DailyChallengeResponse(BaseModel):
    challenge: DailyChallenge
    date: str  # YYYY-MM-DD
    my_attempt: MyAttempt | None = None


class DailyChallengeListResponse(BaseModel):
    items: list[DailyChallenge]
    total: int
