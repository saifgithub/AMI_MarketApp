"""DEF515 — a Finding written but never delivered must stay reachable from the tiles.

AMI-DL-9b (2026-11-21): the phone gave up on the Finding POST at 30 s while the
server was still writing it (44 s). The row landed, the trial counter (journal
rows) went 2 -> 3, the response went to nobody, and the card then said the trial
was spent with no way to open what it had spent. The tiles now carry a pointer
to today's stored Finding, under exactly the condition the POST's same-day
replay uses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import JournalEntryRow
from app.schemas import Plan
from app.schemas.journal import EntryType
from app.services.journal_store import get_journal_store
from app.services.rate_limit import portfolio_health_finding_rate_limit

from tests.unit.test_cr140_health_cadence import (
    _OK_CONTEXT,
    _seed_user,
    _wire,
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    get_journal_store().clear()
    portfolio_health_finding_rate_limit.reset()
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "trial")
    monkeypatch.setattr(settings, "portfolio_health_trial_findings", 3)
    monkeypatch.setattr(settings, "portfolio_health_daily_cap", 2)
    monkeypatch.setattr(settings, "portfolio_health_plans", ["trader", "floor_manager"])
    monkeypatch.setattr(settings, "portfolio_health_cadence_days", 30)
    yield
    get_journal_store().clear()


def _seed(user_id: UUID, portfolio_id: UUID, *, as_of: str, deleted: bool = False) -> UUID:
    now = datetime.now(timezone.utc)
    entry_id = uuid4()
    with get_session() as s:
        s.add(JournalEntryRow(
            id=entry_id,
            user_id=user_id,
            entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS.value,
            reference_id=portfolio_id,
            title="Portfolio Health — Finding",
            payload={"as_of": as_of, "portfolio_id": str(portfolio_id),
                     "sections": {"head": "h"}, "rule_states": {}},
            created_at=now,
            deleted_at=now if deleted else None,
        ))
    return entry_id


def test_tiles_point_at_todays_stored_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = _seed_user(Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    entry_id = _seed(user_id, portfolio_id, as_of=_OK_CONTEXT["as_of"])
    client = _wire(monkeypatch, user_id, portfolio_id)

    body = client.get(f"/v1/portfolio/health/{user_id}").json()
    assert body["todays_finding"] == {
        "journal_entry_id": str(entry_id), "as_of": _OK_CONTEXT["as_of"],
    }


def test_no_pointer_when_the_stored_finding_is_from_another_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = _seed_user(Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    _seed(user_id, portfolio_id, as_of="1970-01-01")
    client = _wire(monkeypatch, user_id, portfolio_id)

    assert client.get(f"/v1/portfolio/health/{user_id}").json()["todays_finding"] is None


def test_no_pointer_to_a_deleted_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = _seed_user(Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    _seed(user_id, portfolio_id, as_of=_OK_CONTEXT["as_of"], deleted=True)
    client = _wire(monkeypatch, user_id, portfolio_id)

    assert client.get(f"/v1/portfolio/health/{user_id}").json()["todays_finding"] is None


def test_a_spent_trial_user_can_still_replay_the_pointed_at_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pointer is only honest if the POST it sends the user to serves it —
    even with the trial spent and no plan access (the AMI-DL-9b state)."""
    user_id = _seed_user(Plan.FLOOR_PASS)
    portfolio_id = uuid4()
    _seed(user_id, portfolio_id, as_of="1970-01-01")
    _seed(user_id, portfolio_id, as_of="1970-01-02")
    entry_id = _seed(user_id, portfolio_id, as_of=_OK_CONTEXT["as_of"])
    client = _wire(monkeypatch, user_id, portfolio_id)

    tiles = client.get(f"/v1/portfolio/health/{user_id}").json()
    assert tiles["gate"]["trial_active"] is False
    assert tiles["gate"]["trial_findings_used"] == 3
    assert tiles["todays_finding"]["journal_entry_id"] == str(entry_id)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200
    assert r.json()["created"] is False
    assert r.json()["journal_entry_id"] == str(entry_id)
