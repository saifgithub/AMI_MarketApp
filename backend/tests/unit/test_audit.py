"""Unit tests for the AT:R16 audit service + LLM gateway hook + 1-on-1 capture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    HTTPAuditRow,
    LLMAuditRow,
    NotificationRow,
    OneOnOneMessageRow,
    RoomRunRow,
)
from app.db.session import get_session
from app.services.audit import (
    record_http,
    record_llm_call,
    record_one_on_one_message,
    trim_audit_tables,
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

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              max_tokens=1024, meta=None,
                              constraint=None):  # DEF125 meta + CR210 constraint
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

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              max_tokens=1024, meta=None,
                              constraint=None):  # DEF125 meta + CR210 constraint
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


def test_trim_audit_tables_deletes_old_rows_keeps_recent():
    """Rows older than the cutoff are deleted; newer rows survive."""
    old_ts = datetime.now(timezone.utc) - timedelta(days=91)
    new_ts = datetime.now(timezone.utc) - timedelta(days=1)

    old_uid = uuid4()
    new_uid = uuid4()

    # Write an old row and a new row to each table.
    record_llm_call(
        user_id=old_uid, agent_id="a", flow="f", tier="cheap",
        provider="mock", locale="en", system_prompt="old",
        messages=[], response_text="old", latency_ms=1, error=None,
    )
    record_llm_call(
        user_id=new_uid, agent_id="a", flow="f", tier="cheap",
        provider="mock", locale="en", system_prompt="new",
        messages=[], response_text="new", latency_ms=1, error=None,
    )
    record_http(
        method="GET", path="/v1/old", query=None, user_id=old_uid,
        client_ip=None, status_code=200, request_body=None,
        response_body=None, response_truncated=False, is_streaming=False,
        latency_ms=1,
    )
    record_http(
        method="GET", path="/v1/new", query=None, user_id=new_uid,
        client_ip=None, status_code=200, request_body=None,
        response_body=None, response_truncated=False, is_streaming=False,
        latency_ms=1,
    )

    # Back-date the "old" rows directly.
    with get_session() as s:
        for model, col in (
            (LLMAuditRow, LLMAuditRow.user_id),
            (HTTPAuditRow, HTTPAuditRow.user_id),
        ):
            from sqlalchemy import update
            s.execute(
                update(model).where(col == old_uid).values(created_at=old_ts)
            )
        s.commit()

    counts = trim_audit_tables(days=90)

    assert counts["llm_audit"] >= 1
    assert counts["http_audit"] >= 1

    # New rows must still be present.
    with get_session() as s:
        assert s.execute(
            select(LLMAuditRow).where(LLMAuditRow.user_id == new_uid)
        ).scalar_one_or_none() is not None
        assert s.execute(
            select(HTTPAuditRow).where(HTTPAuditRow.user_id == new_uid)
        ).scalar_one_or_none() is not None

    # Old rows must be gone.
    with get_session() as s:
        assert s.execute(
            select(LLMAuditRow).where(LLMAuditRow.user_id == old_uid)
        ).scalar_one_or_none() is None
        assert s.execute(
            select(HTTPAuditRow).where(HTTPAuditRow.user_id == old_uid)
        ).scalar_one_or_none() is None


def test_trim_audit_tables_aborts_stale_room_runs():
    """room_runs stuck in 'running' for > 30 min are marked aborted."""
    from sqlalchemy import insert, update as sa_update

    stale_ts = datetime.now(timezone.utc) - timedelta(minutes=40)
    recent_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    dummy_uid = uuid4()

    with get_session() as s:
        stale_id = uuid4()
        recent_id = uuid4()
        s.execute(
            insert(RoomRunRow).values([
                dict(
                    id=stale_id, user_id=dummy_uid, ticker="AAPL",
                    triggered_at=stale_ts, mandate_version=1,
                    model_tier="cheap", rounds=1, status="running",
                ),
                dict(
                    id=recent_id, user_id=dummy_uid, ticker="AAPL",
                    triggered_at=recent_ts, mandate_version=1,
                    model_tier="cheap", rounds=1, status="running",
                ),
            ])
        )
        s.commit()

    counts = trim_audit_tables()

    assert counts["room_runs_aborted"] >= 1

    with get_session() as s:
        stale_row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == stale_id)
        ).scalar_one()
        recent_row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == recent_id)
        ).scalar_one()
        assert stale_row.status == "aborted"
        assert recent_row.status == "running"


def test_trim_audit_tables_ages_out_old_notifications():
    """CR027: notifications rides the existing 90-day trim job — old rows
    age out, recent ones survive, same as the audit tables above."""
    old_ts = datetime.now(timezone.utc) - timedelta(days=91)
    new_ts = datetime.now(timezone.utc) - timedelta(days=1)
    old_id, new_id = uuid4(), uuid4()

    with get_session() as s:
        s.add(NotificationRow(
            id=old_id, user_id=uuid4(), type="price_alert", title="old",
            body="old", deep_link={}, created_at=old_ts,
        ))
        s.add(NotificationRow(
            id=new_id, user_id=uuid4(), type="price_alert", title="new",
            body="new", deep_link={}, created_at=new_ts,
        ))
        s.commit()

    counts = trim_audit_tables(days=90)
    assert counts["notifications"] >= 1

    with get_session() as s:
        assert s.get(NotificationRow, old_id) is None
        assert s.get(NotificationRow, new_id) is not None
