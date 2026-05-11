"""Convene the Room — RoomRun, Verdict, transcript."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import AgentMessage


class VerdictAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    PASS = "PASS"  # Research Manager: nothing fits mandate today


class RoomStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Verdict(BaseModel):
    """The Portfolio Manager's final verdict on a Room run."""

    model_config = ConfigDict(use_enum_values=True)

    action: VerdictAction
    size_pct: float | None = None
    entry: float | None = None
    target: float | None = None
    stop: float | None = None
    time_horizon_days: int | None = None
    reason: str
    violations: list[str] = Field(default_factory=list)
    overridden_from_llm: bool = False


class RoomRun(BaseModel):
    """A single Convene the Room session."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    user_id: UUID

    ticker: str
    triggered_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    mandate_version: int
    model_tier: Literal["cheap", "mid", "premium"]
    rounds: int = 1

    transcript: list[AgentMessage] = Field(default_factory=list)
    verdict: Verdict | None = None

    credit_cost: int
    status: RoomStatus = RoomStatus.QUEUED

    error_message: str | None = None
    duration_ms: int | None = None
