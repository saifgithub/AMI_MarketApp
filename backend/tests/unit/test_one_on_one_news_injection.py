"""News Analyst 1-on-1 must get real headlines injected — News Analyst only,
not all 12 agents (unlike the shared fundamentals block). CR023, AT:R57.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentId, Mandate
from app.schemas.one_on_one import ChatMsg, OneOnOneSession
from app.services import news_context
from app.services.agent_runner import AgentRunner
from app.services.news_context import LiveHeadline


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


_HEADLINE = LiveHeadline(
    title="Apple beats on EPS", link="https://x", publisher="Reuters",
    published_at=1_800_000_000, sentiment=None, source="yfinance",
)


def test_news_block_injected_for_news_analyst_when_ticker_mentioned(base_mandate, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: [_HEADLINE])

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.NEWS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the latest on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE NEWS — AAPL" in sp
    assert "Apple beats on EPS" in sp


def test_news_block_not_injected_for_other_agents(base_mandate, monkeypatch):
    """The News-only gate — unlike the shared fundamentals block, headlines
    must not leak into every agent's prompt."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: [_HEADLINE])

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the latest on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE NEWS" not in sp


def test_news_block_absent_when_disabled_by_default(base_mandate, monkeypatch):
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: [_HEADLINE])

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.NEWS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the latest on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE NEWS" not in sp


def test_news_block_absent_when_fetch_fails(base_mandate, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: None)

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.NEWS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the latest on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE NEWS" not in sp
