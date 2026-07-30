"""1-on-1 chat schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import now_utc
from app.schemas.agents import AgentId


class ChatMsg(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=now_utc)


class OneOnOneStartRequest(BaseModel):
    """Open a 1-on-1 session with an agent. The mandate comes from the user's
    current mandate (we re-read it each session)."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: AgentId
    # For W3 dev: the user can pass a one-shot mandate inline so we don't need
    # a real auth/mandate-store yet. V1 reads from the user's stored mandate.
    mandate_override: dict | None = None
    locale: str = "en"
    # NOTE: `user_id` removed L-1 (AT:R32 audit-residual). The route now
    # sources the user from the Bearer token (`current_user.id`) — matches
    # the magic-link / Apple-claim hardening from audit A3. Extra `user_id`
    # in the body is silently ignored (Pydantic default).


class OneOnOneMessageRequest(BaseModel):
    """Send a message and get a streamed response (SSE)."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: UUID
    # DEF186 (security review H6): unbounded — a client could pass a
    # megabyte-scale user_message/history straight through to the LLM.
    # 8,000 chars is comfortably above any real chat turn (~1-2k tokens)
    # and history caps at 100 turns (a long real conversation, not an
    # attacker-supplied wall of scripted turns).
    user_message: str = Field(max_length=8_000)
    history: list[ChatMsg] = Field(default_factory=list, max_length=100)


class OneOnOneSession(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    agent_id: AgentId
    started_at: datetime
    mandate_used: dict  # snapshot of the mandate at session start
    locale: str = "en"
    user_id: UUID | None = None
