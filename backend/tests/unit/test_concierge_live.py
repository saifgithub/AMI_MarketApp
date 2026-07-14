"""Post-onboarding Concierge → AMI wiring (A2).

Mirrors `test_room_runner.py`'s live-gateway tests: a fake gateway
records calls + returns programmed text; we assert the runner routes
through the gateway when `has_real_provider()` is True and falls back
to the deterministic scripted reply otherwise. Also exercises the
prompt builder directly to make sure the journal / unlocked agents /
lesson catalogue actually make it into the system prompt.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentId, Mandate
from app.schemas.journal import EntryType, JournalEntry
from app.schemas.lessons import LessonMeta
from app.schemas.one_on_one import OneOnOneSession
from app.services.agent_runner import AgentRunner
from app.services.concierge_prompts import (
    build_concierge_messages,
    scripted_reply,
)


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeGateway:
    """Records every call. has_real_provider() is configurable per test."""

    def __init__(self, *, real: bool, reply: str = "AMI Concierge live reply."):
        self._real = real
        self._reply = reply
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return self._real

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        self.calls.append({
            "system_prompt": system_prompt,
            "messages": [(m.role, m.content) for m in messages],
            "tier": model_tier,
            "locale": locale,
        })
        # Stream in two chunks to exercise the buffered path
        mid = len(self._reply) // 2
        yield self._reply[:mid]
        yield self._reply[mid:]


def _collect_stream(coro_gen) -> str:
    async def run():
        out: list[str] = []
        async for chunk in coro_gen:
            out.append(chunk)
        return "".join(out)
    return asyncio.run(run())


def _make_session(mandate: Mandate, *, user_id=None) -> OneOnOneSession:
    return OneOnOneSession(
        id=uuid4(),
        agent_id=AgentId.CONCIERGE,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=user_id,
    )


# ── Live path ────────────────────────────────────────────────────────────


def test_concierge_routes_to_gateway_when_real_provider_present(base_mandate):
    fake = _FakeGateway(real=True, reply="Try lesson 003 — Mandate Basics.")
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _make_session(base_mandate)

    out = _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=[],
        user_message="What lesson should I take next?",
    ))

    assert "Mandate Basics" in out
    assert len(fake.calls) == 1
    sp = fake.calls[0]["system_prompt"]
    # Floor Concierge context block is appended on top of the base prompt
    assert "FLOOR CONCIERGE CONTEXT" in sp
    # Mandate snapshot is present
    assert f"risk_score={base_mandate.risk_score}" in sp
    # User message lands at the end of the conversation
    assert fake.calls[0]["messages"][-1] == ("user", "What lesson should I take next?")


def test_concierge_prompt_carries_lesson_catalogue(base_mandate):
    """Concierge needs lesson IDs in the prompt so it can name them."""
    fake = _FakeGateway(real=True, reply="ok")
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _make_session(base_mandate)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="anything",
    ))
    sp = fake.calls[0]["system_prompt"]
    assert "Available lessons" in sp
    # Real lesson catalogue (loaded from content/lessons) shows real entries.
    # Default mode is full_context (CR020/CR021): every lesson is listed as
    # `NNN · id · title · topic · tags`, grouped by track.
    catalogue = sp.split("Available lessons", 1)[1]
    assert "001_what_is_a_stock" in catalogue
    assert " · " in catalogue


def test_concierge_prompt_lists_unlocked_agents_for_real_user(base_mandate):
    """When user_id is set + lessons-service has an activation, the
    prompt should call that agent out so the LLM can route confidently.
    """
    from app.services.lessons_service import get_lessons_service

    user_id = uuid4()
    get_lessons_service().grant_activation(
        user_id, AgentId.MARKET_ANALYST.value, method="founder_grant",
    )

    fake = _FakeGateway(real=True, reply="ok")
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _make_session(base_mandate, user_id=user_id)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="who can i ask about TSLA?",
    ))
    sp = fake.calls[0]["system_prompt"]
    assert "Market Analyst" in sp


# ── Scripted-fallback path ───────────────────────────────────────────────


def test_concierge_uses_scripted_fallback_when_no_real_provider(base_mandate):
    """has_real_provider() False ⇒ runner does NOT call the gateway."""
    fake = _FakeGateway(real=False)
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _make_session(base_mandate)

    out = _collect_stream(runner.stream_one_on_one_message(
        session=session,
        history=[],
        user_message="What's my mandate?",
    ))

    # Gateway was never invoked
    assert fake.calls == []
    # Scripted mandate reply mentions the snapshot
    assert f"risk score {base_mandate.risk_score}/5" in out
    assert "Settings → Mandate" in out


def test_scripted_reply_routes_lesson_intent(base_mandate):
    sample_lessons = [
        LessonMeta(
            id="003_mandate_basics",
            title="Mandate Basics",
            duration_min=4,
            level=1,
            track="foundations",
            topic="mandate",
        ),
    ]
    out = scripted_reply(
        user_message="teach me about risk",
        mandate=base_mandate,
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=sample_lessons,
    )
    assert "003_mandate_basics" in out or "Mandate Basics" in out


def test_scripted_reply_routes_to_unlocked_agent(base_mandate):
    out = scripted_reply(
        user_message="can I talk to the market analyst?",
        mandate=base_mandate,
        recent_journal=[],
        unlocked_agents={"market_analyst"},
        available_lessons=[],
    )
    assert "Market Analyst" in out


def test_scripted_reply_refuses_trading_advice(base_mandate):
    out = scripted_reply(
        user_message="should I buy NVDA?",
        mandate=base_mandate,
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=[],
    )
    # Routes away — does not speculate
    assert "Market Analyst" in out or "Convene" in out or "Room" in out
    assert "buy NVDA" not in out.lower()  # no echo of the request


def test_scripted_reply_summarises_journal(base_mandate):
    user_id = uuid4()
    entries = [
        JournalEntry(
            user_id=user_id,
            entry_type=EntryType.ROOM_RUN,
            title="Convened on AAPL — APPROVE",
            agents_involved=[],
        ),
        JournalEntry(
            user_id=user_id,
            entry_type=EntryType.SIM_TRADE,
            title="BUY MSFT @ $410",
            agents_involved=[],
        ),
    ]
    out = scripted_reply(
        user_message="what have I done recently?",
        mandate=base_mandate,
        recent_journal=entries,
        unlocked_agents=set(),
        available_lessons=[],
    )
    assert "AAPL" in out
    assert "MSFT" in out


# ── build_concierge_messages directly ────────────────────────────────────


def test_build_concierge_messages_includes_all_context_blocks(base_mandate):
    user_id = uuid4()
    entries = [
        JournalEntry(
            user_id=user_id,
            entry_type=EntryType.ROOM_RUN,
            title="Convened on AAPL",
            ticker="AAPL",
            agents_involved=[],
        ),
    ]
    lessons = [
        LessonMeta(
            id="001_intro",
            title="Welcome",
            duration_min=3,
            level=1,
            track="foundations",
            topic="intro",
        ),
    ]
    system_prompt, messages = build_concierge_messages(
        mandate=base_mandate,
        user_id=user_id,
        user_message="hello",
        history=[],
        recent_journal=entries,
        unlocked_agents={"market_analyst"},
        available_lessons=lessons,
    )

    assert "FLOOR CONCIERGE CONTEXT" in system_prompt
    assert "AAPL" in system_prompt
    assert "Market Analyst" in system_prompt
    assert "001_intro" in system_prompt
    assert "Welcome" in system_prompt
    # Concierge's role rules from the base prompt come through too
    assert "Concierge" in system_prompt
    # User message is the last entry in `messages`
    assert messages[-1].role == "user"
    assert messages[-1].content == "hello"
