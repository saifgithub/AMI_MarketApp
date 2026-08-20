"""Decision Journal schemas.

Unified table — polymorphic via `entry_type`. Covers Room runs, 1-on-1s, sim
trades, mandate edits, and Coach proposals.

Floor Pass users get 30-day retention; paid tiers are unlimited (enforced
client-side in the list query for now; server-side cleanup job runs later).

Spec: docs/initial_specs/08_tech/data_model.md (journal_entries),
      docs/initial_specs/01_product/core_loop_and_features.md (Sim & Decision Journal).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EntryType(str, Enum):
    ROOM_RUN = "room_run"
    ONE_ON_ONE = "one_on_one"
    SIM_TRADE = "sim_trade"
    MANDATE_EDIT = "mandate_edit"
    AGENT_COACH = "agent_coach"
    DRIFT_ALERT = "drift_alert"
    LESSON_COMPLETE = "lesson_complete"
    AGENT_UNLOCK = "agent_unlock"
    DAILY_CHALLENGE = "daily_challenge"
    PORTFOLIO_HEALTH_ANALYSIS = "portfolio_health_analysis"
    # CR177 — the safety floor refused a trade. Deliberately NOT a SIM_TRADE
    # (nothing filled, no outcome — reusing it would silently inflate the
    # denominator of CR133's "how your trades ended" card) and deliberately
    # not the dead DRIFT_ALERT, which names a different event CR133 already
    # has plans for. Clients that predate this value render it as the DEF210
    # "unknown type" badge — inert by design.
    COMPLIANCE_BLOCK = "compliance_block"


class Outcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    PENDING = "pending"


class JournalEntry(BaseModel):
    """A single entry in the user's Decision Journal."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    entry_type: EntryType
    reference_id: UUID | None = None  # FK to the underlying object
    title: str
    summary: str | None = None
    ticker: str | None = None
    agents_involved: list[str] = Field(default_factory=list)
    mandate_version: int = 1
    tags: list[str] = Field(default_factory=list)
    user_note: str | None = None
    outcome: Outcome | None = None
    payload: dict = Field(default_factory=dict)  # full snapshot for replay
    created_at: datetime = Field(default_factory=_utcnow)
    deleted_at: datetime | None = None  # set on soft-delete; null on live entries
    # CR184 — did the user execute this Room verdict as a sim trade? Computed
    # on read (list_for_user) from the sim_trades.verdict_ref join, training
    # ledger only. Bool for ROOM_RUN entries that carry a verdict; None
    # everywhere else — None means not-applicable, never False. A manual
    # same-ticker trade (verdict_ref NULL) does NOT count as actioned.
    actioned: bool | None = None


class JournalListResponse(BaseModel):
    entries: list[JournalEntry]
    total: int
    retention_days: int | None  # None = unlimited


class JournalNoteRequest(BaseModel):
    entry_id: UUID
    note: str
    tags: list[str] = Field(default_factory=list)


class JournalEntryCreate(BaseModel):
    """Used by the internal capture hook (1-on-1 finish, Coach accept, etc.)
    and by clients writing their own free-form notes."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    entry_type: EntryType
    reference_id: UUID | None = None
    title: str
    summary: str | None = None
    ticker: str | None = None
    agents_involved: list[str] = Field(default_factory=list)
    mandate_version: int = 1
    tags: list[str] = Field(default_factory=list)
    user_note: str | None = None
    outcome: Outcome | None = None
    payload: dict = Field(default_factory=dict)
    # CR136: opaque per-entry-type uniqueness key, NULL for every writer that
    # does not need one. `<portfolio_id>:<as_of>` for a Portfolio Health
    # Finding — what makes a concurrent double-write a DB conflict instead of
    # two Findings and two LLM bills.
    dedupe_key: str | None = None
