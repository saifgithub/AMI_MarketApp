"""Convene the Room — RoomRun, Verdict, transcript."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import AgentMessage
from app.schemas.options import CostedStructure


class VerdictAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    PASS = "PASS"  # Research Manager: nothing fits mandate today
    # CR098 Amendment 2 — Market analyst withheld (tenure pull-back): the PM
    # declines to issue any position because the run had no market read.
    # Built in code (room_runner._assemble_no_verdict), never LLM-parsed —
    # see the NO_VERDICT construction site for why.
    NO_VERDICT = "NO_VERDICT"


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
    # CR098 — analysts withheld this run (tenure pull-back), by AgentId value
    # e.g. "social_media_analyst". Populated deterministically from
    # `ctx.withheld` in code (never LLM-derived, per CR038) so the client's
    # closing disclosure is always accurate even when the model says nothing.
    opinions_not_included: list[str] = Field(default_factory=list)

    # CR106 B1 — where each price on this verdict actually came from.
    #
    #   "pm"          the Portfolio Manager stated this price
    #   "trader"      the PM left it out and the Trader's number was substituted
    #   "ami_default" nobody stated it; AMI minted a protective level from entry
    #
    # `room_runner` mints a missing stop at `entry * 0.94` and a missing target
    # at `entry * 1.13`, and until now disclosed that ONLY by appending a
    # sentence to `reason`. Prose survives being read; a to-scale risk/reward
    # ribbon does not — it draws a minted price at the same weight as a stated
    # one and computes a ratio from it. So the ribbon is gated on this field
    # (CR106 T-PROV: no provenance → no ribbon, fall back to the metric list),
    # and a derived level renders hollow-capped rather than solid.
    #
    # `None` means "this run predates the field", NOT "everything came from the
    # PM" — an absent value is never backfilled or inferred (T-BACKFILL). Only
    # an APPROVE carries prices at all, so only an APPROVE carries this.
    level_provenance: dict[str, Literal["pm", "trader", "ami_default"]] | None = None

    # CR172 §10 step 2 — the option structure attached to this verdict, if the
    # PM chose one.
    #
    # `None` means "this run carried no structure" — an equity verdict, a run
    # whose mandate does not permit derivatives, or a run that predates the
    # field. It never means "a structure with no legs": a candidate that could
    # not be costed is not emitted at all (`option_strategist`), so there is no
    # empty-legged structure to represent. Read it the way `level_provenance`
    # above is read — absence is absence, never backfilled or inferred.
    #
    # **This carried `strategy: str` + `legs: list[VerdictLeg]` until the mobile
    # wiring landed, and the pair could not answer the question the user is
    # actually being asked.** Legs and a name describe what would be bought;
    # consent needs what it costs, what it can lose, where it breaks even, and
    # whether the floor cleared it — and a client that derives those from legs
    # is a client computing a max loss, which is the one figure CR172's ticket
    # exists to never compute (DEF059). So the verdict now carries the whole
    # costed candidate, in the identical shape `/propose` and `/reprice` use, so
    # the ticket parses one thing however it was reached. Nothing was migrated:
    # zero of 2,555 persisted verdicts carried the old pair (measured on Alpha,
    # 2026-08-23), because the menu is gated on `derivatives_allowed`.
    structure: CostedStructure | None = None


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
