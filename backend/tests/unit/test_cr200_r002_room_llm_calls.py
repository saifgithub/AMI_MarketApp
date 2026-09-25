"""CR200-R002 — Room LLM call viewer: the time-window join between a Room
run and its captured `llm_audit` rows.

Covers: rows inside a run's [triggered_at, finished_at] window (+ grace) are
returned in order; rows for a different user or outside the window are
excluded; `admin_prompt_replay` rows are always excluded from a run's own
call list; an in-progress run (`finished_at is None`) windows to "now" and
reports `window_open=True` rather than silently returning nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db import get_session, init_schema
from app.db.models import LLMAuditRow
from app.services.room_llm_calls import (
    REPLAY_FLOW,
    find_replay_row,
    get_call,
    list_calls_for_run,
    list_recent_runs,
)


def _mk_audit_row(
    *, user_id, agent_id: str, created_at: datetime, flow: str = "room",
) -> None:
    init_schema()
    with get_session() as s:
        s.add(LLMAuditRow(
            user_id=user_id,
            agent_id=agent_id,
            flow=flow,
            tier="mid",
            provider="mock",
            locale="en",
            system_prompt=f"system prompt for {agent_id}",
            messages=[{"role": "user", "content": "hello"}],
            response_text=f"response from {agent_id}",
            latency_ms=100,
            error=None,
            created_at=created_at,
        ))


def test_list_calls_for_run_windows_by_user_and_time() -> None:
    init_schema()
    uid = uuid4()
    other_uid = uuid4()
    triggered_at = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    finished_at = triggered_at + timedelta(minutes=5)

    _mk_audit_row(user_id=uid, agent_id="fundamentals_analyst", created_at=triggered_at + timedelta(seconds=10))
    _mk_audit_row(user_id=uid, agent_id="portfolio_manager", created_at=finished_at - timedelta(seconds=10))
    # Before the run started — excluded.
    _mk_audit_row(user_id=uid, agent_id="market_analyst", created_at=triggered_at - timedelta(minutes=10))
    # After the run finished (+ past the grace window) — excluded.
    _mk_audit_row(user_id=uid, agent_id="trader", created_at=finished_at + timedelta(minutes=5))
    # Same window, different user — excluded.
    _mk_audit_row(user_id=other_uid, agent_id="fundamentals_analyst", created_at=triggered_at + timedelta(seconds=20))

    with get_session() as s:
        result = list_calls_for_run(
            s=s, user_id=uid, triggered_at=triggered_at, finished_at=finished_at,
        )

    assert result["window_open"] is False
    agent_ids = [c["agent_id"] for c in result["calls"]]
    assert agent_ids == ["fundamentals_analyst", "portfolio_manager"]


def test_list_calls_for_run_excludes_replay_rows() -> None:
    init_schema()
    uid = uuid4()
    triggered_at = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    finished_at = triggered_at + timedelta(minutes=5)

    _mk_audit_row(user_id=uid, agent_id="trader", created_at=triggered_at + timedelta(seconds=10))
    _mk_audit_row(
        user_id=uid, agent_id="trader",
        created_at=triggered_at + timedelta(seconds=20), flow=REPLAY_FLOW,
    )

    with get_session() as s:
        result = list_calls_for_run(
            s=s, user_id=uid, triggered_at=triggered_at, finished_at=finished_at,
        )

    assert len(result["calls"]) == 1
    assert result["calls"][0]["flow"] == "room"


def test_list_calls_for_run_open_window_when_run_still_running() -> None:
    init_schema()
    uid = uuid4()
    triggered_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    _mk_audit_row(user_id=uid, agent_id="fundamentals_analyst", created_at=triggered_at + timedelta(seconds=5))

    with get_session() as s:
        result = list_calls_for_run(
            s=s, user_id=uid, triggered_at=triggered_at, finished_at=None,
        )

    assert result["window_open"] is True
    assert len(result["calls"]) == 1


def test_get_call_returns_full_request_and_response() -> None:
    init_schema()
    uid = uuid4()
    created_at = datetime.now(timezone.utc)
    _mk_audit_row(user_id=uid, agent_id="bull_researcher", created_at=created_at)

    with get_session() as s:
        result = list_calls_for_run(
            s=s, user_id=uid,
            triggered_at=created_at - timedelta(seconds=1),
            finished_at=created_at + timedelta(seconds=1),
        )
    call_id = result["calls"][0]["id"]

    with get_session() as s:
        row = get_call(s=s, call_id=call_id)
        assert row is not None
        assert row.system_prompt == "system prompt for bull_researcher"
        assert row.response_text == "response from bull_researcher"
        assert row.messages == [{"role": "user", "content": "hello"}]


def test_find_replay_row_matches_agent_and_recency() -> None:
    init_schema()
    uid = uuid4()
    since = datetime.now(timezone.utc) - timedelta(seconds=1)
    _mk_audit_row(user_id=uid, agent_id="trader", created_at=since + timedelta(seconds=0.1), flow=REPLAY_FLOW)
    # A replay for a different agent in the same window must not match.
    _mk_audit_row(user_id=uid, agent_id="portfolio_manager", created_at=since + timedelta(seconds=0.2), flow=REPLAY_FLOW)

    with get_session() as s:
        found = find_replay_row(s=s, agent_id="trader", since=since)
        assert found is not None
        assert found.agent_id == "trader"
        assert found.flow == REPLAY_FLOW

    with get_session() as s:
        # Nothing matches before any replay was written.
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        assert find_replay_row(s=s, agent_id="trader", since=future) is None


def test_list_recent_runs_filters_by_ticker_and_user() -> None:
    from app.db.models import RoomRunRow

    init_schema()
    uid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=uuid4(), user_id=uid, ticker="AAPL",
            triggered_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed", credit_cost=2,
        ))
        s.add(RoomRunRow(
            id=uuid4(), user_id=uid, ticker="MSFT",
            triggered_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed", credit_cost=2,
        ))

    with get_session() as s:
        runs = list_recent_runs(s=s, ticker="AAPL", days=1, limit=10)
    assert len(runs) == 1
    assert runs[0]["ticker"] == "AAPL"

    with get_session() as s:
        runs = list_recent_runs(s=s, user_id=uid, days=1, limit=10)
    assert len(runs) == 2
