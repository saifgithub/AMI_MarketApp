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


# ── Live LLM-path tests (via a fake gateway) ─────────────────────────────


class _FakeGateway:
    """Stand-in for LLMGateway. Records every call and returns a programmed
    per-agent line so we can assert transcript growth + prompt routing.
    """

    def __init__(self, replies: dict[str, str] | None = None):
        self._replies = replies or {}
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        # Pick a reply based on agent_id sniffed from the system prompt.
        agent_key = "default"
        for k in self._replies:
            if f"agent_id: {k}" in system_prompt.lower() or k.replace("_", " ") in system_prompt.lower():
                agent_key = k
                break
        text = self._replies.get(agent_key, "AMI agent live reply.")
        self.calls.append({
            "system_prompt_len": len(system_prompt),
            "tier": model_tier,
            "matched_agent": agent_key,
        })
        # Yield in two chunks to exercise the streaming path
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def test_room_uses_gateway_for_every_agent_when_live():
    """With a fake live gateway, every non-PM agent emits LLM text into the
    transcript; PM also calls the gateway (for rationale) but the verdict
    action still comes from the deterministic safety floor.
    """
    fake = _FakeGateway(replies={
        "fundamentals_analyst": "FA: P/E reasonable, growth steady.",
        "market_analyst": "MA: trend up, RSI 58.",
        "news_analyst": "NA: Fed dovish, sector tailwinds.",
        "social_media_analyst": "SMA: bullish chatter.",
        "bull_researcher": "Bull: thesis defended, 4% size.",
        "bear_researcher": "Bear: multiple-compression risk capped at 2%.",
        "research_manager": "RM: lean constructive, 3% start.",
        "trader": "Trader: BUY 3% at $150, stop $141, target $172.",
        "aggressive_debator": "Push to 4.5%.",
        "conservative_debator": "Cap at 2%.",
        "neutral_debator": "Hold at 3%.",
        "portfolio_manager": "PM: APPROVE; synthesis defended; mandate clears.",
    })
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))

    # Gateway invoked once per agent (12 total).
    assert len(fake.calls) == 12

    # Transcript contains 12 agent messages, all from the fake replies.
    spoke = {e.agent_id for e in events if e.kind == "agent_done"}
    assert len(spoke) == 12

    # Verdict still APPROVE (deterministic, AAPL is in the demo halal universe).
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.APPROVE.value


def test_room_safety_floor_still_fires_under_live_gateway():
    """LLM might say APPROVE; deterministic safety floor flips to REJECT for
    a halal user on a non-halal ticker. overridden_from_llm gets set.
    """
    # Liberal LLM reply — would APPROVE everything if it could.
    fake = _FakeGateway(replies={
        "portfolio_manager": "PM: APPROVE; all good.",
    })
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "risk_score": 3,
        "compliance": {"halal": True, "no_tobacco_alcohol_gambling": True},
    })
    # FAKE_TICKER is not in the demo halal universe → must be rejected.
    events = _collect(runner.run(
        user_id=uuid4(), ticker="FAKE_TICKER", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.REJECT.value
    assert v.overridden_from_llm is True


def test_room_transcript_grows_for_subsequent_agents():
    """Later agents must see earlier agents' contributions in their prompt
    so they can build on the debate, not just speak in isolation.
    """
    captured_prompts: list[str] = []

    class _CaptureGateway:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            captured_prompts.append(system_prompt)
            yield "AMI reply."

    runner = RoomRunner(llm=_CaptureGateway())  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))

    # First agent (Fundamentals) sees an empty transcript marker.
    assert "(You are first to speak.)" in captured_prompts[0]
    # Last agent (PM) sees every earlier agent's contribution in the
    # transcript section — at least the Trader's line should be present.
    assert "trader" in captured_prompts[-1].lower()
    assert "AMI reply." in captured_prompts[-1]
