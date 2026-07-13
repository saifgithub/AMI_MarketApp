"""Bull/Bear Researcher 1-on-1 must get real Decision Journal history —
Bull/Bear only, not all 12 agents (unlike the shared fundamentals block).
DEF054/DEF055, AT:R58.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentId, Mandate
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.one_on_one import ChatMsg, OneOnOneSession
from app.services.agent_runner import AgentRunner
from app.services.journal_store import get_journal_store


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


def _session(mandate: Mandate, agent: AgentId, user_id) -> OneOnOneSession:
    return OneOnOneSession(
        id=uuid4(),
        agent_id=agent,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=user_id,
    )


def _seed(user_id, ticker, title):
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ROOM_RUN, title=title, ticker=ticker,
    ))


def test_journal_block_injected_for_bull_researcher_when_ticker_mentioned(base_mandate):
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE")

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.BULL_RESEARCHER, user_id)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the case for AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "DECISION JOURNAL HISTORY — AAPL" in sp
    assert "Room on AAPL — APPROVE" in sp


def test_journal_block_injected_for_bear_researcher_when_ticker_mentioned(base_mandate):
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — REJECT")

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.BEAR_RESEARCHER, user_id)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the risk on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "DECISION JOURNAL HISTORY — AAPL" in sp
    assert "Room on AAPL — REJECT" in sp


def test_journal_block_not_injected_for_other_agents(base_mandate):
    """The Bull/Bear-only gate."""
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE")

    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.MARKET_ANALYST, user_id)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the setup on AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "DECISION JOURNAL HISTORY" not in sp


def test_journal_block_absent_when_no_history(base_mandate):
    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.BULL_RESEARCHER, uuid4())

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the case for AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "DECISION JOURNAL HISTORY" not in sp


def test_journal_block_absent_for_anonymous_session(base_mandate):
    fake = _FakeGateway()
    runner = AgentRunner(fake)  # type: ignore[arg-type]
    session = _session(base_mandate, AgentId.BULL_RESEARCHER, None)

    _collect_stream(runner.stream_one_on_one_message(
        session=session, history=[], user_message="What's the case for AAPL?",
    ))

    sp = fake.calls[0]["system_prompt"]
    assert "DECISION JOURNAL HISTORY" not in sp
