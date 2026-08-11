"""Market Analyst 1-on-1 must get real technicals injected — Market Analyst
only, not all 12 agents (unlike the shared fundamentals block). DEF052, AT:R58.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentId, Mandate
from app.schemas.one_on_one import ChatMsg, OneOnOneSession
from app.services import technicals
from app.services.agent_runner import AgentRunner
from app.services.technicals import Technicals


class _FakeGateway:
    def __init__(self):
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        self.calls.append({"system_prompt": system_prompt})
        yield "AMI reply."


def _collect_stream(coro_gen) -> str:
    async def run():
        chunks: list[str] = []
        async for chunk in coro_gen:
            chunks.append(chunk)
        return "".join(chunks)
    return asyncio.run(run())


def _session(mandate: Mandate, agent: AgentId) -> OneOnOneSession:
    return OneOnOneSession(
        id=uuid4(),
        agent_id=agent,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=None,
    )


_TECHNICALS = Technicals(
    rsi=67, rsi_tone="neither overbought nor oversold", trend="uptrend",
    volume_tone="above 20-day average", support=90.0, breakout=110.0,
    price=105.0,
    # CR146 Tier B — kept coherent with the labels above: price > 20d > 50d is
    # what "uptrend" means, and 1.35 is what "above 20-day average" is a
    # bucketing of. A fixture whose number and label disagree would test nothing.
    sma_short=102.0, sma_long=98.0, volume_ratio=1.35,
)


def test_technicals_block_injected_for_market_analyst_when_ticker_mentioned(base_mandate, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(technicals, "compute_technicals", lambda t: _TECHNICALS)

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the setup on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE TECHNICALS — AAPL" in sp
    assert "RSI(14): 67" in sp


def test_technicals_block_not_injected_for_other_agents(base_mandate, monkeypatch):
    """The Market-Analyst-only gate — technicals must not leak into every
    agent's prompt."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(technicals, "compute_technicals", lambda t: _TECHNICALS)

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.NEWS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the setup on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE TECHNICALS" not in sp


def test_technicals_block_absent_when_disabled_by_default(base_mandate, monkeypatch):
    monkeypatch.setattr(technicals, "compute_technicals", lambda t: _TECHNICALS)

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the setup on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE TECHNICALS" not in sp


def test_technicals_block_absent_when_compute_fails(base_mandate, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(technicals, "compute_technicals", lambda t: None)

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the setup on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE TECHNICALS" not in sp
