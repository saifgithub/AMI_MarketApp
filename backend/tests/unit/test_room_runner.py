"""Tests for the Convene the Room orchestrator."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.schemas import AgentId, Compliance
from app.schemas.mandate import Plan
from app.schemas.room import RoomStatus, VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner


def _collect(coro_gen) -> list:
    async def run():
        events = []
        async for ev in coro_gen:
            events.append(ev)
        return events
    return asyncio.run(run())


def test_room_streams_all_phases_and_lands_a_verdict():
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=mandate,
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))

    # Every phase fires
    phases = [e.phase for e in events if e.kind == "phase"]
    assert phases == ["ANALYSTS", "RESEARCHERS", "SYNTHESIS", "EXECUTION", "RISK", "VERDICT"]

    # Every one of the 12 agents speaks
    spoke = {e.agent_id for e in events if e.kind == "agent_done"}
    expected = {a for a in AgentId if a != AgentId.CONCIERGE}
    assert spoke == expected

    # Verdict emitted last (or near last)
    verdicts = [e for e in events if e.kind == "verdict"]
    assert len(verdicts) == 1
    v = verdicts[0].verdict
    assert v is not None
    # Default ticker should pass the demo halal universe (AAPL is in it)
    assert v.action == VerdictAction.APPROVE.value


def test_room_safety_floor_overrides_when_halal_ticker_fails():
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "risk_score": 3,
        "compliance": {"halal": True, "no_tobacco_alcohol_gambling": True},
    })
    # NEVR is not in the demo halal universe → must reject
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="NEVR",
        mandate=mandate,
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    verdicts = [e for e in events if e.kind == "verdict"]
    assert len(verdicts) == 1
    v = verdicts[0].verdict
    assert v.action == VerdictAction.REJECT.value
    assert v.overridden_from_llm is True
    assert any("Sharia" in vio or "halal" in vio for vio in v.violations)


def test_room_safety_floor_blocks_on_blocklist():
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "compliance": {"ticker_blocklist": ["AAPL"]},
    })
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=mandate,
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.REJECT.value
    assert any("blocklist" in vio for vio in v.violations)


def test_run_persists_to_runner_with_transcript():
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = uuid4()
    events = _collect(runner.run(
        user_id=user_id, ticker="MSFT", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    run_id = events[0].run_id
    assert run_id is not None
    run = runner.get_run(run_id)
    assert run is not None
    assert run.status == RoomStatus.COMPLETED.value
    # All 12 agents are in the transcript
    agents_in_transcript = {m.agent_id for m in run.transcript}
    expected = {a.value for a in AgentId if a != AgentId.CONCIERGE}
    assert agents_in_transcript == expected
    # Listed by user
    user_runs = runner.list_runs_for_user(user_id)
    assert any(r.id == run_id for r in user_runs)


def test_risk_score_5_sizes_up_aggressively_vs_risk_1():
    runner = RoomRunner()
    big = hydrate_coach_mandate({"plan": "trader", "risk_score": 5})
    small = hydrate_coach_mandate({"plan": "trader", "risk_score": 1})

    events_big = _collect(runner.run(
        user_id=uuid4(), ticker="GOOGL", mandate=big,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    events_small = _collect(runner.run(
        user_id=uuid4(), ticker="GOOGL", mandate=small,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v_big = next(e.verdict for e in events_big if e.kind == "verdict")
    v_small = next(e.verdict for e in events_small if e.kind == "verdict")
    assert v_big.size_pct is not None and v_small.size_pct is not None
    assert v_big.size_pct > v_small.size_pct
