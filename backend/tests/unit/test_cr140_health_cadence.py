"""CR140 — the Portfolio Health cadence: rolling days since the last Finding.

Saiful's cadence ruling is monthly (2026-08-05); the shape built is the CR's
own recommendation (b), rolling `cadence_days` from the LAST Finding. What
these tests pin, in order of what would hurt most if lost:

- the cadence binds a plan-served user and the refusal carries the NEXT
  ELIGIBLE DATE (scope item 3 — a refusal that says when, not just no);
- a trial-budget-served user is exempt (DEF219: the trial is bounded by
  budget only — this is the conflation of a clock and a budget happening a
  second time if it regresses);
- `cadence_days=0` restores the pre-CR140 behaviour exactly (acceptance 4);
- the clock is per USER and counts soft-deleted rows, so neither a book
  reset nor deleting yesterday's Finding brings the next one forward — the
  same two loopholes the daily counter already closed (CR136-M07 MINOR m1);
- the tiles stay free in every cadence state (acceptance 5).

Same seeding idiom as test_cr136_health_gate.py: real `JournalEntryRow`s,
backdated, because the thing being timed is the thing the user can see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.portfolio import router as portfolio_router
from app.core.config import settings
from app.db import get_session
from app.db.models import JournalEntryRow, User
from app.schemas import Plan
from app.schemas.journal import EntryType
from app.services import portfolio_finding
from app.services.health_gate import (
    CADENCE_CODE,
    DAILY_CAP_CODE,
    enforce_gate,
    evaluate_gate,
)
from app.services.journal_store import get_journal_store
from app.services.rate_limit import portfolio_health_finding_rate_limit
from app.services.sim_engine import SimEngine, get_sim_engine


@dataclass
class _U:
    id: UUID


class _Portfolio:
    def __init__(self, portfolio_id: UUID) -> None:
        self.id = portfolio_id


class _Sim:
    def __init__(self, portfolio_id: UUID) -> None:
        self._p = _Portfolio(portfolio_id)

    def ensure_portfolio(self, user_id: UUID):
        return self._p


_OK_CONTEXT = {
    "status": "ok",
    "as_of": "2026-08-02",
    "generated_at": "2026-08-02T09:00:00+00:00",
    "engine_version": "cr136.v1",
    "blocks": {"portfolio_volatility": {"metric": "portfolio_volatility",
                                        "sufficient": True, "value": 0.19}},
    "holdings": [],
    "cash_fraction": 0.0,
    "contains_etfs": False,
    "context": {"correlation_pairs": []},
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    get_journal_store().clear()
    portfolio_health_finding_rate_limit.reset()
    # Plan mode by default: cadence semantics are about plan-served access,
    # and the trial exemption gets trial mode set explicitly in its own tests.
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "plan")
    monkeypatch.setattr(settings, "portfolio_health_trial_days", 14)
    monkeypatch.setattr(settings, "portfolio_health_trial_findings", 3)
    monkeypatch.setattr(settings, "portfolio_health_daily_cap", 2)
    monkeypatch.setattr(settings, "portfolio_health_plans", ["trader", "floor_manager"])
    monkeypatch.setattr(settings, "portfolio_health_cadence_days", 30)
    yield
    get_journal_store().clear()


def _seed_user(plan: Plan = Plan.TRADER) -> UUID:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(id=user_id, plan=plan.value))
    return user_id


def _seed_finding(
    user_id: UUID, portfolio_id: UUID, *, days_ago: int, deleted: bool = False,
) -> datetime:
    """Insert a Finding row `days_ago` days back and return its timestamp."""
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with get_session() as s:
        s.add(JournalEntryRow(
            id=uuid4(),
            user_id=user_id,
            entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS.value,
            reference_id=portfolio_id,
            title="Portfolio Health — Finding",
            # as_of is a sentinel that can never equal _OK_CONTEXT's, so the
            # route's same-day idempotency return never short-circuits a test
            # that means to reach the gate. `created_at.date()` would collide
            # with the context's fixed as_of on specific calendar days — a
            # flake that fires a few days a year.
            payload={"as_of": "1970-01-01",
                     "portfolio_id": str(portfolio_id),
                     "sections": {"head": "h"}, "rule_states": {}},
            created_at=created_at,
            deleted_at=created_at if deleted else None,
        ))
    return created_at


def _wire(monkeypatch: pytest.MonkeyPatch, user_id: UUID, portfolio_id: UUID):
    monkeypatch.setattr(
        "app.api.portfolio.build_health_context", lambda uid: dict(_OK_CONTEXT),
    )
    monkeypatch.setattr(
        "app.api.portfolio.evaluate_rules_for_context",
        lambda context, mandate, prior_states: ([], {}),
    )

    async def _fake_generate(**kwargs):
        _seed_finding(kwargs["user_id"], kwargs["portfolio_id"], days_ago=0)
        entry = get_journal_store().latest_portfolio_health_entry(
            kwargs["user_id"], kwargs["portfolio_id"],
        )
        assert entry is not None
        return portfolio_finding.FindingResult(
            entry=entry, created=True, llm_used=False, llm_rejected_reason=None,
        )

    monkeypatch.setattr(
        "app.api.portfolio.generate_and_persist_finding", _fake_generate,
    )
    monkeypatch.setattr("app.api.portfolio.resolve_mandate", lambda uid, v: None,
                        raising=False)
    app = FastAPI()
    app.include_router(portfolio_router)
    app.dependency_overrides[get_sim_engine] = lambda: _Sim(portfolio_id)
    app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)
    return TestClient(app, raise_server_exceptions=False)


# ── The cadence binds, and the refusal says when ────────────────────────────


def test_a_second_finding_inside_the_window_is_refused_with_the_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user()
    portfolio_id = uuid4()
    last_at = _seed_finding(user_id, portfolio_id, days_ago=10)
    client = _wire(monkeypatch, user_id, portfolio_id)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 429
    detail = r.json()["detail"]
    assert detail["code"] == CADENCE_CODE
    # Scope item 3 — the refusal carries the next eligible date, top-level,
    # so a client renders "your next reading is due …" and not a bare no.
    expected = (last_at + timedelta(days=30)).isoformat()
    assert detail["next_eligible_at"] == expected
    assert detail["gate"]["next_eligible_at"] == expected
    assert detail["gate"]["cadence_blocked"] is True


def test_a_finding_after_the_window_elapses_is_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user()
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, days_ago=31)
    client = _wire(monkeypatch, user_id, portfolio_id)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200
    assert r.json()["created"] is True


def test_the_first_finding_ever_is_never_cadence_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user()
    portfolio_id = uuid4()
    client = _wire(monkeypatch, user_id, portfolio_id)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200
    gate = r.json()["gate"]
    # The row just written starts the clock — reported, not yet blocking
    # anything the user is asking for right now.
    assert gate["cadence_days"] == 30
    assert gate["next_eligible_at"] is not None


def test_the_cadence_refusal_outranks_come_back_tomorrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the daily cap AND the cadence would both refuse, the cadence
    message wins: "come back tomorrow" is false when the next reading is a
    month out."""
    user_id = _seed_user()
    portfolio_id = uuid4()
    # Two findings today (a pre-cadence multi-portfolio day): cap reached,
    # and the cadence window is also open.
    _seed_finding(user_id, portfolio_id, days_ago=0)
    _seed_finding(user_id, uuid4(), days_ago=0)
    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.daily_cap_reached is True and gate.cadence_blocked is True

    with pytest.raises(HTTPException) as exc:
        enforce_gate(gate)
    assert exc.value.detail["code"] == CADENCE_CODE
    assert exc.value.detail["code"] != DAILY_CAP_CODE


# ── Who the cadence does NOT bind ───────────────────────────────────────────


def test_a_trial_budget_served_user_is_bounded_by_budget_not_cadence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF219's fix survives: while the trial budget serves the user, the
    cadence never blocks — otherwise a 3-Finding trial becomes a 90-day one
    and the trial can only ever show one snapshot again."""
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "trial")
    user_id = _seed_user(plan=Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    # One finding yesterday: well inside the 30-day window, budget 1 of 3.
    _seed_finding(user_id, portfolio_id, days_ago=1)

    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.trial_active is True
    assert gate.cadence_blocked is False, (
        "the trial is bounded by budget only (DEF219) — a cadence block here "
        "re-creates the one-snapshot trial"
    )

    client = _wire(monkeypatch, user_id, portfolio_id)
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200


def test_the_cadence_takes_over_when_the_trial_budget_exhausts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handoff: budget spent → access flows via plan → cadence binds."""
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "trial")
    user_id = _seed_user(plan=Plan.TRADER)
    portfolio_id = uuid4()
    for days_ago in (6, 4, 2):  # budget of 3, all inside the window
        _seed_finding(user_id, portfolio_id, days_ago=days_ago)

    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.trial_active is False, "budget spent"
    assert gate.plan_has_access is True, "plan now serves the access"
    assert gate.cadence_blocked is True, "and the cadence binds it"


def test_open_mode_is_cadence_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """`open` is an operator override, not a user-facing product mode — it
    keeps the daily cap (GPU protection) but takes no cadence."""
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "open")
    user_id = _seed_user(plan=Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, days_ago=1)

    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.cadence_blocked is False
    assert gate.next_eligible_at is None


# ── Acceptance 4: zero restores today's behaviour exactly ───────────────────


def test_cadence_zero_restores_the_pre_cr140_behaviour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "portfolio_health_cadence_days", 0)
    user_id = _seed_user()
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, days_ago=1)

    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.cadence_blocked is False
    assert gate.next_eligible_at is None
    assert gate.cadence_days == 0

    client = _wire(monkeypatch, user_id, portfolio_id)
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, "one per day, forever — today's behaviour"


# ── The two loopholes the daily counter already closed ──────────────────────


def test_a_book_reset_does_not_reset_the_cadence_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The clock is per USER: `reset_portfolio` mints a fresh uuid4, so a
    per-portfolio clock restarts on every reset — the exact loophole the
    daily counter closed (CR136-M07 MINOR m1)."""
    user_id = _seed_user()
    old_portfolio, new_portfolio = uuid4(), uuid4()
    _seed_finding(user_id, old_portfolio, days_ago=5)

    gate = evaluate_gate(user_id, new_portfolio)
    assert gate.cadence_blocked is True


def test_deleting_the_last_finding_does_not_bring_the_next_forward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user()
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, days_ago=5, deleted=True)

    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.cadence_blocked is True, (
        "soft-deleted rows hold the clock — a counter that skipped them would "
        "hand out off-cadence Findings to anyone who deletes yesterday's"
    )


# ── Acceptance 5: tiles stay free in every cadence state ────────────────────


def test_tiles_are_free_while_the_finding_is_cadence_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user()
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, days_ago=10)
    client = _wire(monkeypatch, user_id, portfolio_id)

    tiles = client.get(f"/v1/portfolio/health/{user_id}")
    assert tiles.status_code == 200
    assert tiles.json()["gate"]["cadence_blocked"] is True, (
        "reported so the card can render its CTA state — never applied"
    )
