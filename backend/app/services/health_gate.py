"""CR136 Portfolio Health access gate — config-driven trial/plan/daily-cap gating for Finding generation; journal rows are the counter, no new table.

Tiles are free in every mode. Only full Finding generation — the one LLM call —
is gated, and the gate is composed from three independent facts: whether the
CR136 Finding trial is still open (window OR budget, whichever exhausts first),
whether the user's effective plan is entitled, and whether today's per-portfolio
cap is spent. The daily cap applies in every mode, including `open`.

The counters are journal rows rather than a new table, which means they are the
same rows the user can see and delete. Both counting reads therefore include
soft-deleted entries (`JournalStore.portfolio_health_stats`): a counter that
skipped them would hand out unlimited Findings to anyone who deletes yesterday's
before asking for today's.

`evaluate_gate` never raises — it reports. `enforce_gate` is the only place a
402/429 is produced, so the GET tiles route can call the first and not the
second and be structurally incapable of gating a free surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.entitlements import effective_plan_for_user
# The wire value comes from M04's constants module — the one place it is
# declared. This module still never imports the schema enum, so it keeps its
# build-order independence from M08, but a second hardcoded copy of the same
# string is the scattered-literal the binding conventions forbid.
from app.services.portfolio_health_constants import PORTFOLIO_HEALTH_ENTRY_TYPE  # noqa: F401
from app.services.journal_store import JournalStore, get_journal_store

GATE_CLOSED_CODE = "portfolio_health_gate_closed"
DAILY_CAP_CODE = "portfolio_health_daily_cap_reached"
CADENCE_CODE = "portfolio_health_cadence_not_elapsed"

MODE_OPEN = "open"
MODE_TRIAL = "trial"
MODE_PLAN = "plan"


@dataclass(frozen=True)
class GateStatus:
    mode: str
    trial_active: bool
    trial_findings_used: int
    trial_findings_budget: int
    trial_days_left: int
    daily_used: int
    daily_cap: int
    plan_has_access: bool
    # CR140. `next_eligible_at` is an ISO string, never a datetime: this dict
    # is embedded in HTTPException detail, which Starlette feeds to a plain
    # JSONResponse — a datetime there is a 500 on the refusal path itself.
    cadence_days: int
    cadence_blocked: bool
    next_eligible_at: str | None

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def has_access(self) -> bool:
        if self.mode == MODE_OPEN:
            return True
        if self.mode == MODE_TRIAL:
            return self.trial_active or self.plan_has_access
        return self.plan_has_access

    @property
    def daily_cap_reached(self) -> bool:
        return self.daily_used >= self.daily_cap


def _entitled_plans() -> set[str]:
    """Rev 4 spells the plans `TRADER,FLOOR_MANAGER`; the `Plan` enum values are
    lowercase. Normalising on read means either spelling in the env works, and
    an operator who copies the spec verbatim does not silently hard-close the
    gate."""
    return {p.strip().lower() for p in settings.portfolio_health_plans if p.strip()}


def evaluate_gate(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    now: datetime | None = None,
    store: JournalStore | None = None,
) -> GateStatus:
    """Report the gate. Never raises, never writes."""
    now = now or datetime.now(timezone.utc)
    store = store or get_journal_store()

    used, first_at, daily_used = store.portfolio_health_stats(
        user_id, portfolio_id, now=now,
    )

    trial_days = settings.portfolio_health_trial_days
    budget = settings.portfolio_health_trial_findings

    if first_at is None:
        days_elapsed = 0
        days_left = trial_days
    else:
        days_elapsed = (now - first_at).days
        days_left = max(0, trial_days - days_elapsed)

    # DEF219: the trial is counted in FINDINGS, not days. Saiful's cadence for
    # portfolio-level evaluation is monthly, and a 14-day clock at that cadence
    # admits exactly ONE Finding — six of the seven were unreachable and the
    # user never got a second reading. The product is the CHANGE between
    # readings, so a trial that can only ever show one snapshot does not
    # demonstrate it.
    #
    # Dropping the clock does not make the trial unbounded: `dedupe_key` is
    # `<portfolio_id>:<date>`, so a single-portfolio user can take at most one
    # Finding per day and the budget is the only other limit. A trialist can
    # pull one today, one after they next trade, one a week later — and see a
    # delta, which is the thing being sold.
    #
    # `trial_days_left` is still reported (clients render it, and `plan` mode
    # is unaffected) but it no longer GATES. Deliberately kept rather than
    # removed: the field is part of a shipped API surface, and a client reading
    # it as advisory is correct.
    trial_active = used < budget

    # `effective_plan_for_user` is trial-expiry aware, so an expired
    # TRIAL_TRADER resolves to FLOOR_PASS here. The two "trials" are distinct
    # and deliberately so: the ACCOUNT trial (users.trial_expires_at) feeds
    # plan_has_access, while the CR136 Finding trial is this journal-counted
    # window. Consequence of the pinned default plan list: an active
    # TRIAL_TRADER has no *plan* access, and in `trial` mode the Finding trial
    # is what serves them.
    plan_has_access = effective_plan_for_user(user_id).value in _entitled_plans()

    # CR140 — the rolling cadence, and who it does NOT apply to. A user being
    # served by the trial BUDGET is exempt (DEF219: the trial is bounded by
    # budget only — a cadence on a 3-Finding trial would stretch it to 90 days
    # and re-create the one-snapshot trial DEF219 removed). `open` mode is
    # exempt because it is an operator override, not a user-facing product
    # mode. Everyone else — plan-served access in `trial` or `plan` mode —
    # waits `cadence_days` from their last Finding, counting soft-deleted rows
    # and counting per USER (see `last_portfolio_health_finding_at`).
    cadence_days = settings.portfolio_health_cadence_days
    mode = settings.portfolio_health_gate_mode
    cadence_exempt = mode == MODE_OPEN or (mode == MODE_TRIAL and trial_active)
    cadence_blocked = False
    next_eligible_at: str | None = None
    if cadence_days > 0 and not cadence_exempt:
        last_at = store.last_portfolio_health_finding_at(user_id)
        if last_at is not None:
            next_eligible = last_at + timedelta(days=cadence_days)
            next_eligible_at = next_eligible.isoformat()
            cadence_blocked = now < next_eligible

    return GateStatus(
        mode=mode,
        trial_active=trial_active,
        trial_findings_used=used,
        trial_findings_budget=budget,
        trial_days_left=days_left,
        daily_used=daily_used,
        daily_cap=settings.portfolio_health_daily_cap,
        plan_has_access=plan_has_access,
        cadence_days=cadence_days,
        cadence_blocked=cadence_blocked,
        next_eligible_at=next_eligible_at,
    )


def enforce_gate(status_: GateStatus) -> None:
    """402 for "not entitled", 429 for "entitled but not yet".

    Order is load-bearing twice over: a user with no access at all should be
    told to upgrade, not told to come back tomorrow — and when both time
    limits would fire, the cadence refusal wins because it is the honest one.
    "Come back tomorrow" is false when the next reading is 30 days out
    (CR140 scope item 3: the refusal says WHEN, not just no).
    """
    if not status_.has_access:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": GATE_CLOSED_CODE, "gate": status_.as_dict()},
        )
    if status_.cadence_blocked:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": CADENCE_CODE,
                "next_eligible_at": status_.next_eligible_at,
                "gate": status_.as_dict(),
            },
        )
    if status_.daily_cap_reached:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": DAILY_CAP_CODE, "gate": status_.as_dict()},
        )
