"""CR200-R002 — admin Room LLM call viewer + resend routes.

Covers: every route 403s without admin auth; `/runs`, `/runs/{id}`,
`/runs/{id}/llm-calls` return real data behind auth; a resend is an
ISOLATED raw LLM call — it returns a response and writes its own
`llm_audit` row (`admin_prompt_replay`) and an `admin_audit` row, but never
creates/mutates a `room_runs` row, never moves `User.credit_balance`, and
never writes a `journal_entries` row. An edited `system_prompt` changes the
routed response (proves the edit actually reached the gateway call, not
just the original captured prompt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.admin_room import router as admin_room_router
from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import AdminAuditRow, JournalEntryRow, LLMAuditRow, RoomRunRow, User
from app.services.llm_gateway import MockProvider, get_llm_gateway
from app.services.room_llm_calls import REPLAY_FLOW

_SECRET = "test-admin-secret-room-calls"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture(autouse=True)
def _force_mock_provider() -> None:
    """Same technique as test_brief_engine.py — pin the gateway to the real
    MockProvider so a resend's response is deterministic and no test ever
    reaches a real network call regardless of the environment's keys."""
    gw = get_llm_gateway()
    gw._providers = {"mock": MockProvider()}  # type: ignore[attr-defined]


def _app() -> TestClient:
    init_schema()
    app = FastAPI()
    app.include_router(admin_room_router)
    return TestClient(app, raise_server_exceptions=False)


def _mk_user() -> "uuid4":
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            created_at=datetime.now(timezone.utc),
        ))
    return uid


def _mk_run(user_id, ticker: str = "AAPL", status: str = "completed") -> "uuid4":
    run_id = uuid4()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id, user_id=user_id, ticker=ticker,
            triggered_at=now, finished_at=now, mandate_version=1,
            model_tier="mid", status=status, credit_cost=8,
        ))
    return run_id


def _mk_call(user_id, agent_id: str = "trader", system_prompt: str = "You are the Trader.") -> "uuid4":
    call_id = uuid4()
    with get_session() as s:
        s.add(LLMAuditRow(
            id=call_id, user_id=user_id, agent_id=agent_id, flow="room",
            tier="mid", provider="mock", locale="en",
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": "Convene on AAPL."}],
            response_text="original response",
            latency_ms=50,
        ))
    return call_id


def test_routes_403_without_admin_auth() -> None:
    client = _app()
    run_id = uuid4()
    call_id = uuid4()
    assert client.get("/v1/admin/room/runs").status_code == 403
    assert client.get(f"/v1/admin/room/runs/{run_id}").status_code == 403
    assert client.get(f"/v1/admin/room/runs/{run_id}/llm-calls").status_code == 403
    assert client.post(f"/v1/admin/room/llm-calls/{call_id}/resend", json={}).status_code == 403


def test_list_runs_and_run_detail() -> None:
    client = _app()
    uid = _mk_user()
    run_id = _mk_run(uid)

    r = client.get("/v1/admin/room/runs", headers=_HDR)
    assert r.status_code == 200
    assert any(row["id"] == str(run_id) for row in r.json()["runs"])

    r = client.get(f"/v1/admin/room/runs/{run_id}", headers=_HDR)
    assert r.status_code == 200
    assert r.json()["id"] == str(run_id)

    missing = uuid4()
    assert client.get(f"/v1/admin/room/runs/{missing}", headers=_HDR).status_code == 404


def test_run_llm_calls_returns_captured_request_and_response() -> None:
    client = _app()
    uid = _mk_user()
    run_id = _mk_run(uid)
    _mk_call(uid)

    r = client.get(f"/v1/admin/room/runs/{run_id}/llm-calls", headers=_HDR)
    assert r.status_code == 200
    body = r.json()
    assert len(body["calls"]) == 1
    call = body["calls"][0]
    assert call["system_prompt"] == "You are the Trader."
    assert call["messages"] == [{"role": "user", "content": "Convene on AAPL."}]
    assert call["response_text"] == "original response"


def test_resend_is_isolated_no_side_effects() -> None:
    client = _app()
    uid = _mk_user()
    _mk_run(uid)
    call_id = _mk_call(uid)

    with get_session() as s:
        room_runs_before = s.execute(select(func.count()).select_from(RoomRunRow)).scalar_one()
        journal_before = s.execute(select(func.count()).select_from(JournalEntryRow)).scalar_one()
        credit_before = s.execute(
            select(User.credit_balance).where(User.id == uid)
        ).scalar_one()

    r = client.post(
        f"/v1/admin/room/llm-calls/{call_id}/resend", headers=_HDR, json={},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["response_text"]
    assert body["provider"] == "mock"

    with get_session() as s:
        room_runs_after = s.execute(select(func.count()).select_from(RoomRunRow)).scalar_one()
        journal_after = s.execute(select(func.count()).select_from(JournalEntryRow)).scalar_one()
        credit_after = s.execute(
            select(User.credit_balance).where(User.id == uid)
        ).scalar_one()
        admin_audit_rows = s.execute(
            select(func.count()).select_from(AdminAuditRow)
            .where(AdminAuditRow.action == "room_llm_call_resent")
        ).scalar_one()
        replay_rows = s.execute(
            select(func.count()).select_from(LLMAuditRow)
            .where(LLMAuditRow.flow == REPLAY_FLOW)
        ).scalar_one()

    assert room_runs_after == room_runs_before
    assert journal_after == journal_before
    assert credit_after == credit_before
    assert admin_audit_rows == 1
    assert replay_rows == 1


def test_resend_with_edited_system_prompt_changes_routed_response() -> None:
    """MockProvider routes by matching agent-id substrings in the (lowercased)
    system prompt (test_cr056_no_assumed_data.py's own framing) — editing the
    prompt to name a different agent must change which canned reply comes
    back, proving the edit reached the gateway call and wasn't silently
    dropped in favor of the original captured prompt."""
    client = _app()
    uid = _mk_user()
    _mk_run(uid)
    call_id = _mk_call(uid, agent_id="trader", system_prompt="You are AMI's Trader.")

    r = client.post(
        f"/v1/admin/room/llm-calls/{call_id}/resend", headers=_HDR,
        json={"system_prompt": "You are AMI's Fundamentals Analyst."},
    )
    assert r.status_code == 200
    assert "Fundamentals Analyst" in r.json()["response_text"]


def test_resend_missing_call_404s() -> None:
    client = _app()
    missing = uuid4()
    r = client.post(
        f"/v1/admin/room/llm-calls/{missing}/resend", headers=_HDR, json={},
    )
    assert r.status_code == 404
