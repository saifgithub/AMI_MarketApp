"""DEF455 — an exception raised in `run()`'s setup, before its main try, must
not strand the run.

DEF454 (AIXI, 2026-10-18): the profile build raised KeyError above `run()`'s
try. The pump only enqueued an SSE `error` — no log, the row stayed `running`,
the 27 credits stayed spent, and dedup tier 1 attached every re-convene to the
dead run until the next boot's sweep. These pin the pump-level backstop.
"""

from __future__ import annotations

import asyncio

import pytest
import structlog

from app.db import get_session
from app.db.models import RoomRunRow
from app.services import room_runner as room_runner_mod
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for
from app.services.room_runner import RoomRunner


def _boom(*_args, **_kwargs):
    raise KeyError("current")


async def _convene(runner: RoomRunner, user_id, ticker: str = "AIXI"):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    run_id = await runner.start_run(
        user_id=user_id, ticker=ticker, mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    )
    events = [ev async for ev in runner.subscribe(run_id)]
    return run_id, events


def _user():
    u, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    return u.id


@pytest.fixture
def setup_crash(monkeypatch):
    monkeypatch.setattr(room_runner_mod, "_profile_for_ticker", _boom)


def test_setup_crash_marks_the_row_failed_refunds_and_logs(setup_crash):
    user_id = _user()
    before = balance_for(user_id)[0]

    with structlog.testing.capture_logs() as captured:
        run_id, events = asyncio.run(_convene(RoomRunner(), user_id))

    assert [e.kind for e in events][-1] == "error"
    with get_session() as s:
        row = s.get(RoomRunRow, run_id)
        assert row.status == "failed"
        assert "crashed" in (row.error_message or "")
        assert row.refund_recorded is True
    assert balance_for(user_id)[0] == before, "a crashed run must not bill"
    crashed = [e for e in captured if e["event"] == "room_run_crashed"]
    assert crashed and crashed[0]["run_id"] == str(run_id)


def test_a_reconvene_after_a_setup_crash_is_a_fresh_run(setup_crash):
    user_id = _user()

    async def _twice():
        runner = RoomRunner()
        first, _ = await _convene(runner, user_id)
        second, _ = await _convene(runner, user_id)
        return first, second

    first, second = asyncio.run(_twice())
    assert first != second, "dedup must not attach a re-convene to the dead run"


def test_never_a_second_refund_once_run_already_failed_the_row(setup_crash):
    """The backstop is idempotent on the row: a second call (or a row `run()`
    already moved off `running`) never refunds again (CR237 round 3)."""
    user_id = _user()
    runner = RoomRunner()
    run_id, _ = asyncio.run(_convene(runner, user_id))
    after_first = balance_for(user_id)[0]

    runner._fail_stranded_run(run_id, RuntimeError("again"))

    assert balance_for(user_id)[0] == after_first
