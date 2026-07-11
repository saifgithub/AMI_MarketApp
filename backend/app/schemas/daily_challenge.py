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


class DailyChallengePublic(BaseModel):
    """The pre-attempt public shape of a challenge — `DailyChallenge` minus
    `answer` AND `explanation` (DEF042: `/today` returned both, so an
    API-direct user could either read `answer` outright or match the
    always-correct-restating `explanation` text against the options —
    either way the correct choice was derivable before attempting, which
    is farmable for the `challenge_correct` streak/credit milestone).
    Server-side grading still uses the full `DailyChallenge`; only the
    response-facing views built from this class drop the giveaway fields.
    """

    id: str
    type: str
    difficulty: int = Field(ge=1, le=5)
    locale: str = "en"
    scenario: str
    question: str
    options: list[str]
    related_lesson: str | None = None
    related_agent: str | None = None
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_challenge(cls, ch: DailyChallenge) -> "DailyChallengePublic":
        return cls(**ch.model_dump(exclude={"answer", "explanation"}))


class MyAttempt(BaseModel):
    """The caller's stored answer for a challenge (CR004 — server truth;
    lets the mobile card render the answered state after a restart).
    Carries `correct_option` + `explanation` too (DEF042) — safe here
    because this only ever populates for a challenge the caller has
    already attempted."""

    selected_option: int
    correct: bool
    correct_option: int
    explanation: str
    attempted_at: str  # ISO 8601


class DailyChallengeResponse(BaseModel):
    challenge: DailyChallengePublic
    date: str  # YYYY-MM-DD
    my_attempt: MyAttempt | None = None


class DailyChallengeListResponse(BaseModel):
    items: list[DailyChallengePublic]
    total: int
