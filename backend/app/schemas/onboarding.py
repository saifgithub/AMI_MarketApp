"""Onboarding conversation — session state, questions, answers, readback.

The session is anonymous-first: no user_id until claim. Until then the session is
keyed by a server-generated session_id and lives in the in-memory store (Week 2)
or Postgres + Redis (Week 3+).

See docs/initial_specs/03_onboarding/mandate_conversation.md for the conversation script.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import now_utc


class ConversationStep(str, Enum):
    """The 8 ordered steps of the Express path."""

    WELCOME = "welcome"
    Q1_GOAL = "q1_goal"
    Q2_HORIZON = "q2_horizon"
    Q3_SCENARIO_DRAWDOWN = "q3_scenario_drawdown"
    Q4_SCENARIO_REGRET = "q4_scenario_regret"
    Q5_SCENARIO_CONCENTRATION = "q5_scenario_concentration"
    Q6_MAX_DRAWDOWN = "q6_max_drawdown"
    Q7_CONSTRAINTS = "q7_constraints"
    Q8_BRIEFING = "q8_briefing"
    READBACK = "readback"
    COMPLETE = "complete"


class Author(str, Enum):
    CONCIERGE = "concierge"
    USER = "user"


class Message(BaseModel):
    """One turn in the onboarding conversation."""

    author: Author
    content: str
    step: ConversationStep
    timestamp: datetime = Field(default_factory=now_utc)
    chips: list[str] = Field(default_factory=list)


class OnboardingSession(BaseModel):
    """Anonymous onboarding session. Persists 24h or until claimed."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    locale: str = "en"
    timezone: str = "UTC"
    detected_display_name: str | None = None

    current_step: ConversationStep = ConversationStep.WELCOME
    messages: list[Message] = Field(default_factory=list)
    answers: dict[str, Any] = Field(default_factory=dict)

    # Computed as we go
    risk_components_partial: dict[str, int] = Field(default_factory=dict)

    completed: bool = False
    claimed_user_id: UUID | None = None


# ── API request/response models ─────────────────────────────────────────────


class StartOnboardingRequest(BaseModel):
    locale: str = "en"
    timezone: str = "UTC"


class StartOnboardingResponse(BaseModel):
    session_id: UUID
    welcome_message: Message
    first_question: Message


class AnswerRequest(BaseModel):
    session_id: UUID
    step: ConversationStep
    answer: str  # raw user text — even chip selections submitted as text


class AnswerResponse(BaseModel):
    """Server's reply to a user's answer. Contains the next question OR the readback."""

    next_step: ConversationStep
    concierge_reply: Message
    # If readback: includes a structured summary the user can confirm/edit
    readback_summary: dict[str, Any] | None = None


class ReadbackConfirmRequest(BaseModel):
    session_id: UUID
    confirm: Literal["confirm", "edit"]
    edits: dict[str, Any] = Field(default_factory=dict)


class ReadbackConfirmResponse(BaseModel):
    completed: bool
    final_step: ConversationStep
    mandate_preview: dict[str, Any]
    follow_up_message: Message
