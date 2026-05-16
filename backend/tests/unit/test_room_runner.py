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


def test_profile_synthetic_when_real_market_data_disabled(monkeypatch):
    """Default test config (use_real_market_data=False) → synthetic profile."""
    from app.core.config import settings
    from app.services.room_runner import _profile_for_ticker

    monkeypatch.setattr(settings, "use_real_market_data", False)
    profile = _profile_for_ticker("AAPL")
    assert profile["data_source"] == "synthetic"
    assert profile["ticker"] == "AAPL"
    # Same ticker → same profile (deterministic).
    assert _profile_for_ticker("AAPL")["pe"] == profile["pe"]


def test_profile_overlays_live_fundamentals_when_enabled(monkeypatch):
    """When use_real_market_data is on and yfinance returns, numeric fields
    are overlaid and narrative strings derive from the real numbers."""
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    # Stub the live fetch to return a known shape, no network.
    monkeypatch.setattr(
        room_runner, "fetch_live_fundamentals",
        lambda t: {
            "base_price": 250.50,
            "pe": "35.2",
            "rev_growth": 8,
            "fcf_margin": 25,
            "net_cash": 65_000,
            "low": 165.0,
            "high": 260.0,
        },
    )
    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["data_source"] == "yfinance_live"
    assert profile["pe"] == "35.2"
    assert profile["base_price"] == 250.50
    assert profile["rev_growth"] == 8
    # Narrative strings should reference the LIVE numbers.
    assert "8%" in profile["bull_thesis"]
    assert "25%" in profile["bull_thesis"]
    assert "35x" in profile["bear_risk"]


def test_profile_falls_back_to_synthetic_when_yfinance_fails(monkeypatch):
    """A yfinance failure (network error, unknown ticker) must not break
    the runner — it falls through to the deterministic synthetic profile."""
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["data_source"] == "synthetic"
    # All required keys still present.
    assert "pe" in profile and "bull_thesis" in profile


def test_format_profile_labels_data_source():
    """The profile fact-sheet must declare whether numbers are live."""
    from app.services.room_prompts import _format_profile

    live_block = _format_profile({"data_source": "yfinance_live", "pe": "35.0"})
    assert "LIVE" in live_block

    synth_block = _format_profile({"data_source": "synthetic", "pe": "22.0"})
    assert "alpha simulation scaffolding" in synth_block


# ── Timeout fallback ──────────────────────────────────────────────────────


class _HangingGateway:
    """Gateway whose stream_chat hangs indefinitely — used to test timeout."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, **_):
        await asyncio.sleep(3600)
        yield "never reached"  # pragma: no cover


def test_room_agent_timeout_falls_back_to_scripted():
    """If an agent's LLM call exceeds agent_timeout_s, the runner falls back
    to the scripted template and the run still completes with a verdict."""
    runner = RoomRunner(llm=_HangingGateway())  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=mandate,
        char_delay_min=0.0,
        char_delay_max=0.0,
        agent_timeout_s=0.05,  # 50ms — fast enough for the test suite
    ))

    # All 12 agents must still appear (scripted fallback fires for each).
    spoke = {e.agent_id for e in events if e.kind == "agent_done"}
    assert len(spoke) == 12

    # The run must still produce a verdict.
    verdicts = [e for e in events if e.kind == "verdict"]
    assert len(verdicts) == 1
    assert verdicts[0].verdict is not None


def test_room_cancelled_mid_run_persists_partial_transcript():
    """Regression for bug 0bd88533: disconnected Convene rooms must show
    the conversation that happened.

    When the SSE consumer in room.py is cancelled (client backgrounds the
    app / connection drops), `async for ev in run_iter` tears the iterator
    down via aclose(), sending GeneratorExit into the runner generator at
    its current yield point. The runner used to let it propagate uncaught
    — the generator died before reaching the bottom `_persist_run`, so the
    DB row stayed at status=running with an empty transcript. The detached
    drain task in room.py then finalised a useless journal entry from that
    stale snapshot.

    The fix catches the cancellation, persists the partial transcript with
    status=CANCELLED, then re-raises. This test simulates the disconnect
    by calling `gen.aclose()` after a few agents have spoken and verifies
    the persisted state contains the conversation that actually happened.
    """
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    user_id = uuid4()

    async def run_until_two_agents_then_close():
        gen = runner.run(
            user_id=user_id,
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        agents_done = 0
        try:
            async for ev in gen:
                if ev.kind == "agent_done":
                    agents_done += 1
                    if agents_done >= 2:
                        break
        finally:
            await gen.aclose()
        return agents_done

    agents_done = asyncio.run(run_until_two_agents_then_close())
    assert agents_done == 2  # sanity: we consumed past two agents

    runs = runner.list_runs_for_user(user_id, limit=10)
    assert len(runs) == 1
    run = runs[0]
    assert run.status == RoomStatus.CANCELLED.value
    assert run.finished_at is not None
    assert run.duration_ms is not None
    assert run.error_message and "disconnect" in run.error_message
    # Partial transcript must be persisted — the agents that spoke before
    # the disconnect, not an empty list.
    assert len(run.transcript) >= 2
    # And the journal entry built from this snapshot now carries the
    # conversation through to the user.
    from app.api.room import _build_journal_entry
    entry = _build_journal_entry(run, run.user_id)
    assert "AAPL" in entry.title
    assert "cancelled" in entry.title.lower()
    assert f"{len(run.transcript)} of 12" in entry.summary
    assert len(entry.payload["transcript"]) == len(run.transcript)


# ── Journal entry builder ─────────────────────────────────────────────────


def test_build_journal_entry_completed_run():
    """A run with a verdict gets a title with the action and a full summary."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.api.room import _build_journal_entry
    from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction

    run = RoomRun(
        id=uuid4(),
        user_id=uuid4(),
        ticker="TSLA",
        triggered_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        mandate_version=1,
        model_tier="mid",
        rounds=1,
        transcript=[],
        verdict=Verdict(
            action=VerdictAction.APPROVE,
            reason="Synthesis defended.",
            size_pct=3.0,
            entry=200.0,
            target=226.0,
            stop=188.0,
            time_horizon_days=42,
        ),
        credit_cost=8,
        status=RoomStatus.COMPLETED,
    )
    entry = _build_journal_entry(run, run.user_id)
    assert "TSLA" in entry.title
    assert "APPROVE" in entry.title
    assert "APPROVE" in entry.summary
    assert "Synthesis" in entry.summary


def test_build_journal_entry_failed_run():
    """A run without a verdict gets a descriptive title and meaningful summary."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.api.room import _build_journal_entry
    from app.schemas.room import RoomRun, RoomStatus

    run = RoomRun(
        id=uuid4(),
        user_id=uuid4(),
        ticker="NVDA",
        triggered_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        mandate_version=1,
        model_tier="mid",
        rounds=1,
        transcript=[],
        verdict=None,
        credit_cost=8,
        status=RoomStatus.FAILED,
        error_message="LLM upstream timeout after 90s",
    )
    entry = _build_journal_entry(run, run.user_id)
    assert "NVDA" in entry.title
    # Title must NOT say "incomplete" — it should reflect the actual status.
    assert "incomplete" not in entry.title.lower()
    assert "failed" in entry.title.lower()
    # Summary must explain what happened, not just say "no verdict".
    assert "no verdict" not in entry.summary.lower()
    assert "0 of 12" in entry.summary
    assert "LLM upstream" in entry.summary
