"""Unit tests for the AT:R16 audit service + LLM gateway hook + 1-on-1 capture."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import HTTPAuditRow, LLMAuditRow, OneOnOneMessageRow
from app.db.session import get_session
from app.services.audit import (
    record_http,
    record_llm_call,
    record_one_on_one_message,
)


def test_record_llm_call_persists_full_row():
    user_id = uuid4()
    record_llm_call(
        user_id=user_id,
        agent_id="market_analyst",
        flow="one_on_one",
        tier="cheap",
        provider="vllm",
        locale="en",
        system_prompt="You are the Market Analyst.",
        messages=[{"role": "user", "content": "Why is AAPL up?"}],
        response_text="AAPL is up because of...",
        latency_ms=421,
        error=None,
    )
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.agent_id == "market_analyst"
        assert row.flow == "one_on_one"
        assert row.tier == "cheap"
        assert row.provider == "vllm"
        assert row.system_prompt.startswith("You are the Market Analyst.")
        assert row.messages == [{"role": "user", "content": "Why is AAPL up?"}]
        assert row.response_text.startswith("AAPL is up")
        assert row.latency_ms == 421
        assert row.error is None


def test_record_llm_call_truncates_huge_prompt():
    user_id = uuid4()
    huge = "X" * 500_000
    record_llm_call(
        user_id=user_id,
        agent_id="concierge",
        flow="concierge_floor",
        tier="mid",
        provider="vllm",
        locale="en",
        system_prompt=huge,
        messages=[],
        response_text=huge,
        latency_ms=100,
        error=None,
    )
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert len(row.system_prompt) == 200_000
        assert len(row.response_text) == 200_000


def test_record_llm_call_with_error():
    user_id = uuid4()
    record_llm_call(
        user_id=user_id,
        agent_id="portfolio_manager",
        flow="room_pm",
        tier="premium",
        provider="vllm",
        locale="en",
        system_prompt="...",
        messages=[],
        response_text=None,
        latency_ms=5_000,
        error="TimeoutError: vLLM took too long",
    )
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.error.startswith("TimeoutError")
        assert row.response_text is None


def test_record_http_basic():
    user_id = uuid4()
    record_http(
        method="POST",
        path="/v1/mandate/abc",
        query=None,
        user_id=user_id,
        client_ip="10.0.0.1",
        status_code=200,
        request_body=b'{"plan":"trader"}',
        response_body=b'{"ok":true}',
        response_truncated=False,
        is_streaming=False,
        latency_ms=17,
    )
    with get_session() as s:
        row = s.execute(select(HTTPAuditRow).where(HTTPAuditRow.user_id == user_id)).scalar_one()
        assert row.path == "/v1/mandate/abc"
        assert row.status_code == 200
        assert row.request_body == '{"plan":"trader"}'
        assert row.response_body == '{"ok":true}'
        assert row.is_streaming is False
        assert row.latency_ms == 17


def test_record_http_streaming_skips_response_body():
    record_http(
        method="POST",
        path="/v1/room/stream",
        query=None,
        user_id=None,
        client_ip=None,
        status_code=200,
        request_body=b"",
        response_body=None,
        response_truncated=False,
        is_streaming=True,
        latency_ms=8_000,
    )
    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow).where(HTTPAuditRow.path == "/v1/room/stream")
        ).scalar_one()
        assert row.is_streaming is True
        assert row.response_body is None


def test_record_one_on_one_message_pair():
    session_id = uuid4()
    user_id = uuid4()
    record_one_on_one_message(
        session_id=session_id, user_id=user_id, agent_id="concierge",
        role="user", content="What's a P/E ratio?",
    )
    record_one_on_one_message(
        session_id=session_id, user_id=user_id, agent_id="concierge",
        role="assistant", content="P/E means price-to-earnings...",
    )
    with get_session() as s:
        rows = s.execute(
            select(OneOnOneMessageRow)
            .where(OneOnOneMessageRow.session_id == session_id)
            .order_by(OneOnOneMessageRow.created_at)
        ).scalars().all()
        assert len(rows) == 2
        assert rows[0].role == "user"
        assert rows[1].role == "assistant"
        assert "P/E" in rows[1].content


@pytest.mark.asyncio
async def test_llm_gateway_writes_audit_on_success():
    """Buffer the streamed chunks; verify a single row lands in llm_audit."""
    from app.services.llm_gateway import (
        ChatMessage,
        LLMGateway,
        LLMProvider,
    )

    class _StreamProvider(LLMProvider):
        name = "stream_fake"

        async def stream_chat(self, *, system_prompt, messages, model_tier, max_tokens=1024):
            yield "Hello "
            yield "world"

    gw = LLMGateway()
    gw._providers["stream_fake"] = _StreamProvider()  # type: ignore[attr-defined]
    # Bypass preference: register at the head
    gw._PREFERENCE = ("stream_fake", "mock")  # type: ignore[assignment]

    user_id = uuid4()
    chunks: list[str] = []
    async for c in gw.stream_chat(
        system_prompt="sys",
        messages=[ChatMessage(role="user", content="hi")],
        model_tier="cheap",
        locale="en",
        audit_user_id=user_id,
        audit_agent_id="market_analyst",
        audit_flow="one_on_one",
    ):
        chunks.append(c)

    assert "".join(chunks) == "Hello world"
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.response_text == "Hello world"
        assert row.provider == "stream_fake"
        assert row.flow == "one_on_one"
        assert row.error is None
        assert row.latency_ms is not None and row.latency_ms >= 0


@pytest.mark.asyncio
async def test_llm_gateway_writes_audit_on_error():
    """When the provider raises, the audit row still lands with the error."""
    from app.services.llm_gateway import (
        ChatMessage,
        LLMGateway,
        LLMProvider,
    )

    class _BoomProvider(LLMProvider):
        name = "boom"

        async def stream_chat(self, *, system_prompt, messages, model_tier, max_tokens=1024):
            yield "partial"
            raise RuntimeError("connection reset")

    gw = LLMGateway()
    gw._providers["boom"] = _BoomProvider()  # type: ignore[attr-defined]
    gw._PREFERENCE = ("boom", "mock")  # type: ignore[assignment]

    user_id = uuid4()
    with pytest.raises(RuntimeError):
        async for _ in gw.stream_chat(
            system_prompt="sys",
            messages=[ChatMessage(role="user", content="hi")],
            model_tier="cheap",
            locale="en",
            audit_user_id=user_id,
            audit_agent_id="trader",
            audit_flow="one_on_one",
        ):
            pass

    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.response_text == "partial"
        assert "RuntimeError" in (row.error or "")
        assert "connection reset" in (row.error or "")
