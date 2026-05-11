"""1-on-1 chat schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import AgentId


class ChatMsg(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OneOnOneStartRequest(BaseModel):
    """Open a 1-on-1 session with an agent. The mandate comes from the user's
    current mandate (we re-read it each session)."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: AgentId
    # For W3 dev: the user can pass a one-shot mandate inline so we don't need
    # a real auth/mandate-store yet. V1 reads from the user's stored mandate.
    mandate_override: dict | None = None
    locale: str = "en"


class OneOnOneMessageRequest(BaseModel):
    """Send a message and get a streamed response (SSE)."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: UUID
    user_message: str
    history: list[ChatMsg] = Field(default_factory=list)


class OneOnOneSession(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    agent_id: AgentId
    started_at: datetime
    mandate_used: dict  # snapshot of the mandate at session start
    locale: str = "en"
