"""1-on-1 agents must get live ticker fundamentals injected into their
system prompt when the user mentions a ticker.

Bug 85469d8e — the Fundamentals agent (and the other 11) were quoting
P/E from training memory because no live data was being injected into
the 1-on-1 path. The Room path got this in commit 4c59f61; this test
covers the extension to 1-on-1.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentId, Mandate
from app.schemas.one_on_one import ChatMsg, OneOnOneSession
from app.services import fundamentals
from app.services.agent_runner import AgentRunner


class _FakeGateway:
    def __init__(self):
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        self.calls.append({
            "system_prompt": system_prompt,
            "messages": [(m.role, m.content) for m in messages],
        })
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


def test_live_block_injected_when_user_mentions_ticker(
    base_mandate, monkeypatch,
):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {"base_price": 250.0, "pe": "35.2"},
    )

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.FUNDAMENTALS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=[],
        user_message="What is AAPL's P/E ratio?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE MARKET DATA — AAPL" in sp
    assert "P/E: 35.2" in sp
    assert "training memory" in sp.lower()


def test_live_block_falls_back_to_history_when_message_has_no_ticker(
    base_mandate, monkeypatch,
):
    """If the current message doesn't name a ticker, look back at the
    last few user turns — the user might just say 'what about it?'."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {"base_price": 400.0, "pe": "30.0"},
    )

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST)

    history = [
        ChatMsg(role="user", content="Tell me about MSFT"),
        ChatMsg(role="assistant", content="Microsoft is …"),
    ]
    _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=history,
        user_message="And what's the support level?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE MARKET DATA — MSFT" in sp


def test_no_block_when_no_ticker_anywhere(base_mandate, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {"base_price": 100.0, "pe": "20.0"},
    )

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.TRADER)

    _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=[],
        user_message="hello, how does this app work?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE MARKET DATA" not in sp


def test_live_block_disabled_in_test_default(base_mandate):
    """Default test config has use_real_market_data=False — even if the
    user names a ticker, no block is injected."""
    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.FUNDAMENTALS_ANALYST)

    _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=[],
        user_message="What's AAPL doing?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "LIVE MARKET DATA" not in sp
