"""Tests for the Convene the Room orchestrator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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


# ── DEF053: real valuation multiples / sector / dividends / analyst consensus ──


def test_profile_no_longer_carries_fake_sector_pe():
    """DEF053: sector_pe was always rng.uniform(15,25) — dropped entirely,
    not just hidden. A fresh synthetic profile must not have the key."""
    from app.services.room_runner import _profile_for_ticker

    profile = _profile_for_ticker("AAPL")
    assert "sector_pe" not in profile


def test_format_profile_includes_valuation_line_when_live():
    from app.services.room_prompts import _format_profile

    block = _format_profile({
        "data_source": "synthetic", "price_to_sales": "10.3",
        "ev_to_ebitda": "29.1", "peg_ratio": "2.55", "fcf_yield": 2.2,
    })
    assert "Valuation (LIVE): P/S 10.3x, EV/EBITDA 29.1x, PEG 2.55, FCF yield 2.2%" in block


def test_format_profile_omits_valuation_line_when_absent():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "Valuation (LIVE)" not in block


def test_format_profile_includes_sector_line_when_live():
    from app.services.room_prompts import _format_profile

    block = _format_profile({
        "data_source": "synthetic", "sector": "Technology", "industry": "Consumer Electronics",
    })
    assert "Sector/industry (LIVE): Technology / Consumer Electronics" in block


def test_format_profile_omits_sector_line_when_absent():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "Sector/industry (LIVE)" not in block


def test_format_profile_includes_dividend_line_and_disclaims_buybacks():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic", "dividend_yield": 0.34})
    assert "Dividend yield (LIVE): 0.34%" in block
    assert "buybacks/M&A: not available" in block


def test_format_profile_includes_analyst_line_labeled_not_guidance():
    from app.services.room_prompts import _format_profile

    block = _format_profile({
        "data_source": "synthetic", "analyst_rating": "strong buy", "analyst_target_price": 315.57,
    })
    assert "strong buy" in block
    assert "$315.57" in block
    assert "NOT company guidance" in block


def test_format_profile_includes_forward_eps_estimate_when_present():
    from app.services.room_prompts import _format_profile

    block = _format_profile({
        "data_source": "synthetic", "next_earnings_date": "2026-08-01",
        "next_earnings_quarter": "Q3", "next_earnings_eps_estimate": 2.04,
    })
    assert "consensus EPS est. $2.04" in block


# ── DEF054/DEF055: real Decision Journal history for Bull/Bear Researcher ──


def _build_messages(agent_id, mandate, user_id, ticker="AAPL"):
    from app.services.room_prompts import build_room_messages

    return build_room_messages(
        agent_id=agent_id, mandate=mandate, user_id=user_id, ticker=ticker,
        profile={"data_source": "synthetic"}, transcript=[],
    )


def test_bull_researcher_gets_journal_history_when_present(base_mandate):
    from uuid import uuid4
    from app.schemas import AgentId
    from app.schemas.journal import EntryType, JournalEntryCreate
    from app.services.journal_store import get_journal_store

    user_id = uuid4()
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ROOM_RUN,
        title="Room on AAPL — APPROVE", ticker="AAPL",
    ))

    system_prompt, _ = _build_messages(AgentId.BULL_RESEARCHER, base_mandate, user_id)
    assert "DECISION JOURNAL HISTORY — AAPL" in system_prompt
    assert "Room on AAPL — APPROVE" in system_prompt


def test_bear_researcher_gets_journal_history_when_present(base_mandate):
    from uuid import uuid4
    from app.schemas import AgentId
    from app.schemas.journal import EntryType, JournalEntryCreate
    from app.services.journal_store import get_journal_store

    user_id = uuid4()
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ROOM_RUN,
        title="Room on AAPL — REJECT", ticker="AAPL",
    ))

    system_prompt, _ = _build_messages(AgentId.BEAR_RESEARCHER, base_mandate, user_id)
    assert "DECISION JOURNAL HISTORY — AAPL" in system_prompt
    assert "Room on AAPL — REJECT" in system_prompt


def test_journal_history_absent_when_none_exists(base_mandate):
    from uuid import uuid4
    from app.schemas import AgentId

    system_prompt, _ = _build_messages(AgentId.BULL_RESEARCHER, base_mandate, uuid4())
    assert "DECISION JOURNAL HISTORY" not in system_prompt


def test_journal_history_not_injected_for_other_agents(base_mandate):
    """The Bull/Bear-only gate — journal history must not leak into every
    agent's Room prompt (unlike the shared fundamentals/technicals block)."""
    from uuid import uuid4
    from app.schemas import AgentId
    from app.schemas.journal import EntryType, JournalEntryCreate
    from app.services.journal_store import get_journal_store

    user_id = uuid4()
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ROOM_RUN,
        title="Room on AAPL — APPROVE", ticker="AAPL",
    ))

    system_prompt, _ = _build_messages(AgentId.MARKET_ANALYST, base_mandate, user_id)
    assert "DECISION JOURNAL HISTORY" not in system_prompt


def test_journal_history_absent_for_anonymous_user(base_mandate):
    from app.schemas import AgentId

    system_prompt, _ = _build_messages(AgentId.BULL_RESEARCHER, base_mandate, None)
    assert "DECISION JOURNAL HISTORY" not in system_prompt


# ── Live technicals overlay (DEF052, AT:R58) ──────────────────────────────


def test_profile_overlays_live_technicals_when_enabled(monkeypatch):
    """When use_real_market_data is on and compute_technicals succeeds, the
    fabricated rng-based rsi/trend/volume_tone/support/breakout are replaced
    with the real computed values."""
    from app.core.config import settings
    from app.services import room_runner
    from app.services.technicals import Technicals

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())
    real = Technicals(
        rsi=67, rsi_tone="neither overbought nor oversold", trend="trading",
        volume_tone="above 20-day average", support=90.0, breakout=110.0,
    )
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: real)

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["technicals_source"] == "live"
    assert profile["rsi"] == 67
    assert profile["rsi_tone"] == "neither overbought nor oversold"
    assert profile["trend"] == "trading"
    assert profile["volume_tone"] == "above 20-day average"
    assert profile["support"] == 90.0
    assert profile["breakout"] == 110.0


def test_profile_technicals_falls_back_to_synthetic_when_unavailable(monkeypatch):
    """compute_technicals returning None (short history, provider failure)
    must not break the run — falls through to the synthetic block."""
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert "technicals_source" not in profile
    # Synthetic fields still present so the rest of the prompt build doesn't break.
    assert "rsi" in profile and "trend" in profile


def test_profile_technicals_independent_of_fundamentals_overlay(monkeypatch):
    """A profile can have live fundamentals + synthetic technicals, or vice
    versa, simultaneously — the two flags must not be coupled."""
    from app.core.config import settings
    from app.services import room_runner
    from app.services.technicals import Technicals

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: {"pe": "35.2"})
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: None)
    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["data_source"] == "yfinance_live"
    assert "technicals_source" not in profile

    real = Technicals(
        rsi=50, rsi_tone="neither overbought nor oversold", trend="consolidating",
        volume_tone="in-line with 20-day average", support=90.0, breakout=110.0,
    )
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: real)
    profile2 = room_runner._profile_for_ticker("AAPL")
    assert profile2["data_source"] == "synthetic"
    assert profile2["technicals_source"] == "live"


def test_format_profile_labels_technicals_source_when_live():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic", "technicals_source": "live"})
    assert "RSI, trend, volume, support/breakout: LIVE" in block


def test_format_profile_labels_technicals_source_when_synthetic():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "RSI, trend, volume, support/breakout: alpha simulation scaffolding" in block


# ── Live news + earnings overlay (CR023, AT:R57) ──────────────────────────


def test_profile_overlays_live_news_when_enabled(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner
    from app.services.news_context import LiveHeadline

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    headline = LiveHeadline(
        title="Apple beats on EPS", link="https://x", publisher="Reuters",
        published_at=1_800_000_000, sentiment=None, source="yfinance",
    )
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: [headline])

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["news_source"] == "live"
    assert "Apple beats on EPS" in profile["catalyst"]
    assert profile["news_headlines"] == [headline]
    # Fields with no real source must stay exactly today's hardcoded strings.
    assert profile["forward_catalyst"] == "FOMC decision in 11 days, sector earnings in 3 weeks"
    assert profile["macro_tone"] == "constructive but fragile"
    assert profile["fed_tone"] == "data-dependent with a dovish lean"


def test_profile_news_falls_back_to_synthetic_when_fetch_fails(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["catalyst"] == "Q3 earnings (beat by ~4%)"
    assert "news_source" not in profile


def test_profile_news_independent_of_fundamentals_overlay(monkeypatch):
    """A profile can have live fundamentals + synthetic news, or vice versa,
    simultaneously — the two flags must not be coupled."""
    from app.core.config import settings
    from app.services import room_runner
    from app.services.news_context import LiveHeadline

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: {"pe": "35.2"})
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["data_source"] == "yfinance_live"
    assert "news_source" not in profile

    headline = LiveHeadline(title="X", link="", publisher="Y", published_at=1_800_000_000, sentiment=None, source="yfinance")
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: [headline])
    profile2 = room_runner._profile_for_ticker("AAPL")
    assert profile2["data_source"] == "synthetic"
    assert profile2["news_source"] == "live"


def test_profile_overlays_earnings_when_available(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner
    from app.services.market_data import EarningsInfo

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)

    class _EarningsProvider:
        def earnings(self, t):
            return EarningsInfo(earnings_date="2026-08-01", quarter="Q3", eps_estimate=2.1)

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _EarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["next_earnings_date"] == "2026-08-01"
    assert profile["next_earnings_quarter"] == "Q3"
    assert profile["next_earnings_eps_estimate"] == 2.1


def test_profile_earnings_absent_when_provider_errors(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)

    class _BoomProvider:
        def earnings(self, t):
            raise RuntimeError("yfinance is down")

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _BoomProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert "next_earnings_date" not in profile


def test_format_profile_labels_news_source_when_live():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic", "news_source": "live", "catalyst": "real headline"})
    assert "Recent catalyst/headline: LIVE" in block


def test_format_profile_labels_news_source_when_synthetic():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "Recent catalyst/headline: alpha simulation scaffolding" in block


def test_format_profile_always_flags_forward_catalyst_as_synthetic():
    """Even with fundamentals AND news AND social all live, forward
    catalyst/macro/Fed tone must still be disclosed as always-synthetic —
    they have no real source (no macro-calendar feed exists). Unlike
    sentiment (AT:R57-continued: now sometimes live via Adanos), this
    subset is unconditional."""
    from app.services.room_prompts import _format_profile

    block = _format_profile({
        "data_source": "yfinance_live", "news_source": "live", "social_source": "live",
    })
    assert "ALWAYS alpha simulation scaffolding" in block


def test_format_profile_labels_social_source_when_live():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic", "social_source": "live"})
    assert "Retail sentiment/mention/community fields: LIVE" in block


def test_format_profile_labels_social_source_when_synthetic():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "Retail sentiment/mention/influencer fields: alpha simulation scaffolding" in block


def test_format_profile_includes_earnings_when_present():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic", "next_earnings_date": "2026-08-01", "next_earnings_quarter": "Q3"})
    assert "Next earnings (LIVE): 2026-08-01 (Q3)" in block


def test_format_profile_omits_earnings_when_absent():
    from app.services.room_prompts import _format_profile

    block = _format_profile({"data_source": "synthetic"})
    assert "Next earnings" not in block


# ── Live Reddit sentiment overlay (CR024, AT:R57-continued) ──────────────


def test_profile_overlays_live_sentiment_when_enabled(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner
    from app.services.social_context import SocialSentiment

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)
    sentiment = SocialSentiment(
        ticker="AAPL", buzz_score=80.0, sentiment_score=0.3, mentions=500,
        bullish_pct=40, bearish_pct=10, trend="rising", period_days=7,
        top_subreddits=("wallstreetbets",), sample_snippets=(),
    )
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: sentiment)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["social_source"] == "live"
    assert profile["sentiment_tone"] == "bullish"
    assert "Adanos" in profile["sentiment_score"]
    assert "500" in profile["mention_trend"]
    assert "wallstreetbets" in profile["influencer_take"]


def test_profile_sentiment_falls_back_to_synthetic_when_fetch_fails(monkeypatch):
    from app.core.config import settings
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: None)
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert "social_source" not in profile
    assert "illustrative" in profile["sentiment_score"]


def test_profile_sentiment_independent_of_news_and_fundamentals(monkeypatch):
    """A profile can have live news + synthetic sentiment, or vice versa —
    all three (fundamentals/news/social) flip independently."""
    from app.core.config import settings
    from app.services import room_runner
    from app.services.news_context import LiveHeadline
    from app.services.social_context import SocialSentiment

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: None)
    monkeypatch.setattr(
        room_runner, "fetch_live_news",
        lambda t: [LiveHeadline(title="X", link="", publisher="Y", published_at=1_800_000_000, sentiment=None, source="yfinance")],
    )
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)

    class _NoEarningsProvider:
        def earnings(self, t):
            return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _NoEarningsProvider())

    profile = room_runner._profile_for_ticker("AAPL")
    assert profile["news_source"] == "live"
    assert "social_source" not in profile


# ── Social Media truthfulness (CR024, AT:R57) ─────────────────────────────


def test_social_media_scripted_fallback_never_names_real_platforms():
    """AT:R57-continued: the template itself is neutral (like NEWS_ANALYST's)
    — it doesn't hardcode "Reddit" or "illustrative"/"no live feed" wording,
    since the field VALUES now carry that honesty (real when Adanos is
    configured and succeeds, clearly-hedged-illustrative otherwise). The
    template must still never name Stocktwits/wallstreetbets outright,
    since those platforms are categorically never real."""
    from app.services.room_runner import _TEMPLATES

    tpl = _TEMPLATES[AgentId.SOCIAL_MEDIA_ANALYST][0]
    lowered = tpl.lower()
    assert "stocktwits" not in lowered
    assert "wallstreetbets" not in lowered


def test_social_media_scripted_fallback_renders_illustrative_values_honestly():
    """The synthetic (no Adanos key) VALUES must self-disclose as
    illustrative when rendered through the neutral template."""
    from app.services.room_runner import _TEMPLATES, _profile_for_ticker

    profile = _profile_for_ticker("AAPL")
    rendered = _TEMPLATES[AgentId.SOCIAL_MEDIA_ANALYST][0].format(**profile)
    assert "illustrative" in rendered.lower()
    assert "stocktwits" not in rendered.lower()
    assert "reddit" not in rendered.lower()


def test_social_media_sentiment_score_has_no_sigma_unit():
    from app.services import room_runner

    profile = room_runner._profile_for_ticker("AAPL")
    assert "σ" not in profile["sentiment_score"]
    assert "illustrative" in profile["sentiment_score"]


def test_social_media_mention_trend_is_hedged_illustrative():
    from app.services import room_runner

    profile = room_runner._profile_for_ticker("AAPL")
    assert "illustrative" in profile["mention_trend"]
    assert profile["mention_trend"] != "up 40% week-over-week"


def test_social_media_mention_trend_varies_by_ticker():
    """Regression guard: the old value was hardcoded identical for every
    ticker regardless of the per-ticker rng seed."""
    from app.services import room_runner

    trends = {room_runner._profile_for_ticker(t)["mention_trend"] for t in ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN"]}
    assert len(trends) > 1


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


# ── Resilience: background task + queue (start_run / subscribe) ───────────


def test_start_run_delivers_verdict_via_subscribe():
    """Happy path: start_run + subscribe yields all 12 agents and a verdict."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        run_id = await runner.start_run(
            user_id=uuid4(),
            ticker="MSFT",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        events = []
        async for ev in runner.subscribe(run_id):
            events.append(ev)
        verdicts = [e for e in events if e.kind == "verdict"]
        assert len(verdicts) == 1
        assert verdicts[0].verdict.action == VerdictAction.APPROVE.value
        # Run must be persisted as COMPLETED
        run = runner.get_run(run_id)
        assert run is not None
        assert run.status == RoomStatus.COMPLETED.value
    asyncio.run(_run())


def test_start_run_completes_after_subscribe_exits():
    """Phone-sleep simulation: SSE consumer exits after a few events.
    The background task must continue to COMPLETED — not CANCELLED."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = uuid4()
        run_id = await runner.start_run(
            user_id=user_id,
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        # Consume 5 events then abandon (simulates SSE client disconnect)
        count = 0
        async for _ in runner.subscribe(run_id):
            count += 1
            if count >= 5:
                break
        # Drain all background tasks before asserting — asyncio.run() would
        # cancel pending tasks when the main coro returns, so we must wait
        # for the _pump task to reach terminal state first.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        run = runner.get_run(run_id)
        assert run is not None
        assert run.status == RoomStatus.COMPLETED.value  # NOT cancelled
        assert len(run.transcript) == 12
    asyncio.run(_run())


def test_start_run_deduplicates_same_user_same_ticker():
    """Second POST for same user+ticker while run is in flight returns the same run_id."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = uuid4()
        run_id_1 = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        # Second submit while first is still running (in-memory dedup —
        # no await between calls so _pump hasn't started yet).
        run_id_2 = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        assert run_id_1 == run_id_2  # attached, not a new run
        # Drain background tasks before asserting DB state
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        runs = runner.list_runs_for_user(user_id)
        assert len(runs) == 1  # only one row in DB
    asyncio.run(_run())


def test_startup_sweep_queues_first_stuck_run_for_retry():
    """eeeb866f (AT:R34): a stuck RUNNING row with retry_count=0 must be
    claimed for retry — bumped to retry_count=1, transcript cleared,
    started_at refreshed, status STILL running, queued in
    _pending_retry. NOT marked failed on the first restart."""
    from datetime import timedelta
    from app.db import get_session
    from app.db.models import RoomRunRow

    user_id = uuid4()
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    run_id = uuid4()

    runner = RoomRunner()  # init schema
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker="STUCK",
            triggered_at=stale_at,
            started_at=stale_at,
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=[{"agent_id": "fundamentals_analyst", "role": "agent", "content": "stale"}],
            verdict=None,
            credit_cost=8,
            status="running",
            retry_count=0,
        ))

    # New runner instance triggers the sweep
    runner2 = RoomRunner()

    # Row is claimed: status still running, retry_count bumped, transcript cleared
    from sqlalchemy import select as _select
    with get_session() as s:
        row = s.execute(
            _select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.status == "running"
        assert row.retry_count == 1
        assert row.transcript == []
        assert row.error_message is None
        # started_at refreshed — normalize sqlite-test naive datetime to UTC
        row_started = row.started_at
        if row_started.tzinfo is None:
            row_started = row_started.replace(tzinfo=timezone.utc)
        assert row_started > stale_at

    # And queued for resume
    assert len(runner2._pending_retry) == 1
    assert runner2._pending_retry[0].run_id == run_id


def test_startup_sweep_marks_failed_after_max_retries():
    """eeeb866f (AT:R34): a stuck RUNNING row that already retried once
    (retry_count=1) gets marked FAILED on the next restart. Two deaths in
    a row likely indicates a real bug, not a transient restart."""
    from datetime import timedelta
    from app.db import get_session
    from app.db.models import RoomRunRow

    user_id = uuid4()
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)

    runner = RoomRunner()
    with get_session() as s:
        s.add(RoomRunRow(
            id=uuid4(),
            user_id=user_id,
            ticker="DEAD",
            triggered_at=stale_at,
            started_at=stale_at,
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=8,
            status="running",
            retry_count=1,  # already retried once
        ))

    runner2 = RoomRunner()
    runs = runner2.list_runs_for_user(user_id, limit=10)
    assert len(runs) == 1
    assert runs[0].status == RoomStatus.FAILED.value
    assert "abandoned" in (runs[0].error_message or "")
    assert "auto-retried 1 time" in (runs[0].error_message or "")
    assert runner2._pending_retry == []


def test_resume_pending_retries_respawns_and_completes():
    """eeeb866f (AT:R34): end-to-end — a stuck row gets respawned by
    resume_pending_retries() and completes with a verdict in the journal."""
    from datetime import timedelta
    from app.db import get_session
    from app.db.models import RoomRunRow
    from app.services.mandate_store import get_mandate_store
    from app.services.journal_store import get_journal_store
    from sqlalchemy import select as _select

    user_id = uuid4()
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    run_id = uuid4()

    # Seed the user's current mandate at version 1 so the respawn can
    # fetch a snapshot for the run.
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)

    runner = RoomRunner()
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker="AAPL",
            triggered_at=stale_at,
            started_at=stale_at,
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=8,
            status="running",
            retry_count=0,
        ))

    runner2 = RoomRunner()
    assert len(runner2._pending_retry) == 1

    async def _resume_and_wait():
        await runner2.resume_pending_retries()
        # Drain the SSE queue so the background _pump runs to completion.
        async for _ in runner2.subscribe(run_id):
            pass

    asyncio.run(_resume_and_wait())

    # Row finalised
    with get_session() as s:
        row = s.execute(
            _select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.status == RoomStatus.COMPLETED.value
        assert row.verdict is not None
        assert row.retry_count == 1  # bumped by sweep, never re-bumped

    # Journal entry was written (the retry path replays on_complete)
    entries, _total, _retention = get_journal_store().list_for_user(user_id)
    assert any(e.reference_id == run_id for e in entries)


def test_start_run_deduplicates_recently_completed_run():
    """Same user+ticker submitted after a completed run finishes (within the
    completed-dedup lookback) returns the prior run's ID — no fresh execution.
    Saves 5+ minutes of LLM time when the underlying market data hasn't moved."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = uuid4()
        # First run — completes to verdict
        run_id_1 = await runner.start_run(
            user_id=user_id, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        # Drain first run's background task to completion
        async for _ in runner.subscribe(run_id_1):
            pass
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        run_1 = runner.get_run(run_id_1)
        assert run_1 is not None
        assert run_1.status == RoomStatus.COMPLETED.value
        # Second submit — same user+ticker, first run already completed.
        # Should return the SAME run_id (dedup), no new row in DB.
        run_id_2 = await runner.start_run(
            user_id=user_id, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        assert run_id_2 == run_id_1  # completed-run dedup
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        runs = runner.list_runs_for_user(user_id)
        assert len(runs) == 1  # still only one row
    asyncio.run(_run())


def test_is_active_false_after_completed_dedup():
    """is_active() distinguishes fresh/in-flight from cached-dedup so the
    API layer can replay the persisted run instead of streaming an empty
    queue (which would surface as 'Room ended without a verdict' on the client)."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = uuid4()
        run_id_1 = await runner.start_run(
            user_id=user_id, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_id_1):
            pass
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        assert runner.is_active(run_id_1) is False  # completed, queue cleaned up
        # Second submit — cached dedup hit
        run_id_2 = await runner.start_run(
            user_id=user_id, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        assert run_id_2 == run_id_1
        assert runner.is_active(run_id_2) is False  # no new _pump task
    asyncio.run(_run())


def test_completed_dedup_window_zero_disables_dedup(monkeypatch):
    """Setting room_dedup_completed_hours=0 disables completed-run dedup so a
    second submit starts a fresh run. Lets ops dial the window off entirely."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "room_dedup_completed_hours", 0)

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = uuid4()
        run_id_1 = await runner.start_run(
            user_id=user_id, ticker="GOOGL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_id_1):
            pass
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        # Second submit with dedup disabled — should be a NEW run
        run_id_2 = await runner.start_run(
            user_id=user_id, ticker="GOOGL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        assert run_id_2 != run_id_1  # fresh run
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        runs = runner.list_runs_for_user(user_id)
        assert len(runs) == 2  # two distinct rows
    asyncio.run(_run())


def test_incremental_checkpoint_saves_partial_transcript():
    """After each agent, _checkpoint_run must have written the transcript to DB.
    Verified by cancelling after 3 agents and checking the DB has ≥3 messages."""
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    user_id = uuid4()

    async def _partial():
        gen = runner.run(
            user_id=user_id,
            ticker="GOOGL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        run_id = None
        agents_done = 0
        try:
            async for ev in gen:
                if ev.run_id:
                    run_id = ev.run_id
                if ev.kind == "agent_done":
                    agents_done += 1
                    if agents_done >= 3:
                        break
        finally:
            await gen.aclose()
        return run_id

    run_id = asyncio.run(_partial())
    run = runner.get_run(run_id)
    assert run is not None
    # Checkpoint writes happen after each agent_done — at least 3 must be in DB
    assert len(run.transcript) >= 3
