"""DEF507 guard: a desk whose LLM call failed never reads as a live call.

When a desk's call fails, `_fall_back_to_script` swaps in the scripted
standing-guidance turn (CR219 R51 — intended). That text used to stream as an
ordinary `agent_token` with nothing on the wire saying it was scripted, so the
app rendered "BUY MSFT at $498.3. Stop $468.4" as the Execution Desk's own
call. Alpha run 1dec3be0 (CR267 WP-14) had eight such turns; a normal Room with
one failed desk had one.

The guard is structural: `scripted` rides the `agent_token` and `agent_done`
events, the stored transcript entry, the live re-attach replay and the
finished-run replay. Healthy turns carry nothing (the key is absent), so a
client that predates the field is unaffected.

Test our logic: which turns are marked is whatever `ctx.scripted_turns` says
(= `Verdict.scripted_agents`), and every emit path must agree with it.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import get_room_runner
from app.api.room import router as room_router
from app.db import get_session
from app.db.models import RoomRunRow, SimPortfolioRow, User
from app.schemas.agents import AgentId, AgentMessage
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomEvent, RoomRunner

PM_JSON = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, '
    '"narration": "Synthesis defended; the mandate clears at this size."}'
)
PM = AgentId.PORTFOLIO_MANAGER.value


class _FailingDesksGateway:
    """Answers the CIO, starves the first `fail_n` other desks (empty stream)."""

    def __init__(self, fail_n: int):
        self.fail_n = fail_n
        self.failed = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            yield PM_JSON
            return
        if self.failed < self.fail_n:
            self.failed += 1
            return
        yield "AMI agent live reply with a real contribution."


def _user() -> tuple[UUID, str]:
    u, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, u.id).plan = "trader"
    return u.id, token


async def _convene(fail_n: int, user_id: UUID):
    runner = RoomRunner(llm=_FailingDesksGateway(fail_n))  # type: ignore[arg-type]
    run_id = await runner.start_run(
        user_id=user_id,
        ticker="MSFT",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    )
    events = [ev async for ev in runner.subscribe(run_id)]
    return runner, run_id, events


def _desk_events(events: list[RoomEvent], kind: str) -> list[RoomEvent]:
    return [e for e in events if e.kind == kind and e.agent_id and e.agent_id.value != PM]


def test_failed_desks_stream_marked_and_live_desks_do_not():
    user_id, _ = _user()
    runner, run_id, events = asyncio.run(_convene(2, user_id))
    run = runner.get_run(run_id)
    scripted = {a for a in run.verdict.scripted_agents}
    assert len(scripted) == 2, "the fixture must actually script two desks"

    tokens = _desk_events(events, "agent_token")
    done = _desk_events(events, "agent_done")
    assert {e.agent_id.value for e in tokens if e.scripted} == scripted
    assert {e.agent_id.value for e in done if e.scripted} == scripted
    assert all(not e.scripted for e in tokens if e.agent_id.value not in scripted)
    assert all(not e.scripted for e in done if e.agent_id.value not in scripted)
    assert any(not e.scripted for e in tokens), "live desks must stay unmarked"

    stored = {
        m.agent_id.value: m.scripted
        for m in run.transcript
        if m.agent_id.value != PM
    }
    assert {a for a, flag in stored.items() if flag} == scripted
    assert not any(m.scripted for m in run.transcript if m.agent_id.value not in scripted)


def test_all_desks_down_marks_every_desk_turn():
    user_id, _ = _user()
    runner, run_id, events = asyncio.run(_convene(99, user_id))
    desks = _desk_events(events, "agent_done")
    assert desks and all(e.scripted for e in desks)
    run = runner.get_run(run_id)
    assert all(m.scripted for m in run.transcript if m.agent_id.value != PM)


def test_live_reattach_replay_keeps_the_mark():
    """DEF500's replay hands a reattached client the run's events from the first
    desk; the mark must survive that hop."""

    async def _go():
        user_id, _ = _user()
        runner = RoomRunner(llm=_FailingDesksGateway(99))  # type: ignore[arg-type]
        run_id = await runner.start_run(
            user_id=user_id,
            ticker="MSFT",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        seen = 0
        async for _ev in runner.subscribe(run_id):
            seen += 1
            if seen >= 40:
                break
        assert runner.is_active(run_id), "run finished before the reattach; test is vacuous"
        return [ev async for ev in runner.subscribe(run_id)]

    replay = asyncio.run(_go())
    assert replay[0].kind == "reattached"
    tokens = _desk_events(replay, "agent_token")
    assert tokens and all(e.scripted for e in tokens)


def _lines(body: str, event: str) -> list[dict]:
    out, ls = [], body.splitlines()
    for i, line in enumerate(ls):
        if line == f"event: {event}":
            out.append(json.loads(ls[i + 1][len("data: "):]))
    return out


def _client(runner) -> TestClient:
    app = FastAPI()
    app.include_router(room_router)
    app.dependency_overrides[get_room_runner] = lambda: runner
    return TestClient(app)


def test_live_sse_route_carries_scripted_only_when_true():
    from app.api.dependencies import get_current_user

    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)

    class _Fake:
        run_id = uuid4()

        async def start_run(self, **kw):
            return self.run_id

        def is_active(self, run_id):
            return True

        async def subscribe(self, run_id):
            a = AgentId.TRADER
            b = AgentId.MARKET_ANALYST
            yield RoomEvent(kind="agent_token", agent_id=a, text="S", scripted=True)
            yield RoomEvent(kind="agent_done", agent_id=a, scripted=True)
            yield RoomEvent(kind="agent_token", agent_id=b, text="L")
            yield RoomEvent(kind="agent_done", agent_id=b)

        def get_run(self, run_id):
            return None

    app = FastAPI()
    app.include_router(room_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_room_runner] = lambda: _Fake()
    r = TestClient(app, raise_server_exceptions=False).post(
        "/v1/room/stream", json={"user_id": str(user.id), "ticker": "MSFT"}
    )
    assert r.status_code == 200, r.text
    toks = _lines(r.text, "agent_token")
    dones = _lines(r.text, "agent_done")
    assert toks[0].get("scripted") is True and dones[0].get("scripted") is True
    assert "scripted" not in toks[1] and "scripted" not in dones[1]


def test_finished_run_replay_carries_the_mark():
    """The cached-run replay (POST /v1/room/stream dedup onto a COMPLETED run)
    rebuilds events from the stored transcript."""
    user_id, token = _user()
    runner, run_id, _events = asyncio.run(_convene(2, user_id))
    scripted = set(runner.get_run(run_id).verdict.scripted_agents)
    assert len(scripted) == 2

    r = _client(runner).post(
        "/v1/room/stream",
        json={"user_id": str(user_id), "ticker": "MSFT", "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    toks = _lines(r.text, "agent_token")
    dones = _lines(r.text, "agent_done")
    assert {t["agent_id"] for t in toks if t.get("scripted")} == scripted
    assert {d["agent_id"] for d in dones if d.get("scripted")} == scripted
    assert any("scripted" not in t for t in toks), "live desks stay unmarked on replay"


def test_stored_run_without_the_field_reads_false_and_replays_unmarked():
    """Rows persisted before DEF507 have no `scripted` key: they load as False
    and replay with no key, so nothing old changes shape."""
    user_id, token = _user()
    rid = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=uuid4(), user_id=user_id, name="Main",
            starting_capital=10_000.0, current_cash=10_000.0,
        ))
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker="AAPL",
            triggered_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            mandate_version=1, model_tier="mid", rounds=1,
            transcript=[{
                "agent_id": "fundamentals_analyst",
                "content": "Solid.",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
            }],
            verdict={"action": "APPROVE", "reason": "x", "violations": [],
                     "opinions_not_included": []},
            credit_cost=0, status="completed",
        ))
    assert AgentMessage.model_validate({
        "agent_id": "fundamentals_analyst", "content": "x",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).scripted is False
    runner = RoomRunner()
    r = _client(runner).post(
        "/v1/room/stream",
        json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert not any("scripted" in d for d in _lines(r.text, "agent_token"))
    assert not any("scripted" in d for d in _lines(r.text, "agent_done"))


@pytest.mark.parametrize("flag", [True, False])
def test_agent_message_round_trips_the_flag(flag):
    m = AgentMessage(
        agent_id=AgentId.TRADER, content="x",
        timestamp=datetime.now(timezone.utc), scripted=flag,
    )
    assert AgentMessage.model_validate(m.model_dump(mode="json")).scripted is flag


def test_journal_snapshot_freezes_the_mark():
    """The Journal replays from the payload frozen at write time, so the mark
    has to be in it or a scripted turn reads as live the moment it is filed."""
    from app.services.room_runner import build_journal_entry_for_run

    user_id, _ = _user()
    runner, run_id, _events = asyncio.run(_convene(2, user_id))
    run = runner.get_run(run_id)
    scripted = set(run.verdict.scripted_agents)
    rows = build_journal_entry_for_run(run, user_id).payload["transcript"]
    assert {r["agent_id"] for r in rows if r["scripted"]} == scripted
    assert any(r["scripted"] is False for r in rows)
