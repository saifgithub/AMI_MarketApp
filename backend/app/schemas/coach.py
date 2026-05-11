"""Coach Your Agent schemas.

A Coach session is a conversational editor for the user_overlay block of an
agent's prompt. The user chats with the agent (in coaching mode); when both
sides agree on a change, the agent produces a structured CoachProposal — a
plain-English summary plus a markdown overlay-addition. The user Accepts,
Refines, or Rejects.

Accepted proposals become a new UserOverlay version. Rollback is one tap.

Spec: docs/02_agents/coach_your_agent.md.
Safety floor: docs/02_agents/safety_floor.md (PM mandate enforcement is
uncoachable; see CoachRefusal in coach_engine.py).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import AgentId
from app.schemas.one_on_one import ChatMsg


class CoachMode(str, Enum):
    FROM_SCRATCH = "from_scratch"
    FROM_PAST_CALLS = "from_past_calls"
    RAW = "raw"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserOverlay(BaseModel):
    """A versioned overlay block for a single (user, agent) pair.

    `content` is the markdown that gets injected into the prompt between the
    mandate overlay and the safety floor (PM only).

    `plain_english` is the human-facing description shown in the history list.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    agent_id: AgentId
    version: int = Field(..., ge=0)
    content: str
    plain_english: str
    created_at: datetime = Field(default_factory=_utcnow)
    based_on_session: UUID | None = None


class CoachProposal(BaseModel):
    """A pending proposal from the agent. Generated when user signals agreement.

    The user can Accept / Refine / Reject. Accept turns this into a new
    UserOverlay version.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    plain_english: str
    overlay_addition: str
    full_overlay_preview: str
    proposed_at: datetime = Field(default_factory=_utcnow)
    refused: bool = False
    refusal_reason: str | None = None


class CoachSession(BaseModel):
    """A live Coach conversation."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    agent_id: AgentId
    mode: CoachMode
    mandate_used: dict
    locale: str = "en"
    base_overlay_version: int = 0
    pending_proposal: CoachProposal | None = None
    started_at: datetime = Field(default_factory=_utcnow)


# ── Request / response payloads ────────────────────────────────────────────


class CoachStartRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_id: AgentId
    user_id: UUID
    mode: CoachMode = CoachMode.FROM_SCRATCH
    mandate_override: dict | None = None
    locale: str = "en"


class CoachStartResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    session: CoachSession
    current_overlay: UserOverlay | None
    opening_message: str


class CoachMessageRequest(BaseModel):
    session_id: UUID
    user_message: str
    history: list[ChatMsg] = Field(default_factory=list)


class CoachProposeRequest(BaseModel):
    """Ask the agent to crystallise the conversation into a structured proposal."""

    session_id: UUID
    history: list[ChatMsg] = Field(default_factory=list)


class CoachAcceptRequest(BaseModel):
    session_id: UUID
    proposal_id: UUID


class CoachRejectRequest(BaseModel):
    session_id: UUID
    proposal_id: UUID


class CoachRollbackRequest(BaseModel):
    user_id: UUID
    agent_id: AgentId
    to_version: int


class CoachHistoryResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_id: AgentId
    user_id: UUID
    versions: list[UserOverlay]
    active_version: int
    edit_count: int
    edits_remaining: int | None  # None = unlimited


class CoachRefusal(BaseModel):
    """Returned when Coach refuses a proposal (e.g. PM safety-floor violation,
    mandate compliance, off-role)."""

    reason: Literal[
        "safety_floor",
        "mandate_compliance",
        "off_role",
        "edit_limit_reached",
        "internal_error",
    ]
    message: str
    suggestion: str | None = None
