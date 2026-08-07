"""CR141 — usage capture: parsing + the NULL-vs-0 / never-breaks-the-stream
guarantees.

Three provider-level concerns (acceptance 1-3):
  - OpenAI-compatible terminal usage frame (vLLM/DeepSeek/Gemini/Qwen shape)
    and Anthropic's usage split across `message_start` + `message_delta`
    both land in `meta["usage"]` correctly.
  - A provider that omits a cache field records None there, not 0 — the
    DeepSeek/vLLM-style key-absent case, distinct from a key present with
    value 0 (a real measurement).
  - A missing or malformed usage frame never breaks the stream: text still
    yields, and (via the full LLMGateway.stream_chat path) the audit row
    still writes, with the usage columns NULL.

The end-to-end tests go through `LLMGateway.stream_chat` + `LLMAuditRow`
(rather than stopping at `meta["usage"]`) because acceptance 2/3 are about
what actually lands in `llm_audit`, not just what a provider computes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import LLMAuditRow
from app.db.session import get_session
from app.services.llm_gateway import (
    AnthropicProvider,
    ChatMessage,
    LLMGateway,
    OpenAICompatibleProvider,
    _parse_openai_compatible_usage,
)


# ── shared SSE fakes (mirrors test_llm_gateway.py's _FakeClient/_FakeSSEResponse) ──


class _FakeSSEResponse:
    def __init__(self, status_code: int, lines: list[str], body: bytes = b""):
        self.status_code = status_code
        self._lines = lines
        self._body = body

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body


class _FakeClient:
    def __init__(self, resp: _FakeSSEResponse):
        self._resp = resp

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        yield self._resp

    async def aclose(self) -> None:
        pass


def _sse(payload: str) -> str:
    return f"data: {payload}"


# ── OpenAI-compatible terminal usage frame ────────────────────────────────


@pytest.mark.asyncio
async def test_openai_compat_parses_realistic_terminal_usage_frame():
    """vLLM/OpenAI shape: usage on an empty-`choices` terminal frame, cache
    field nested under prompt_tokens_details."""
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        _sse(
            '{"choices":[],"usage":{"prompt_tokens":500,"completion_tokens":10,'
            '"total_tokens":510,"prompt_tokens_details":{"cached_tokens":100}}}'
        ),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    assert meta["usage"] == {
        "input_tokens": 500,
        "output_tokens": 10,
        "cache_read_tokens": 100,
        "cache_write_tokens": None,
    }


@pytest.mark.asyncio
async def test_openai_compat_parses_deepseek_cache_hit_field():
    """DeepSeek reports the cache field at the top level, not nested."""
    lines = [
        _sse(
            '{"choices":[],"usage":{"prompt_tokens":500,"completion_tokens":10,'
            '"total_tokens":510,"prompt_cache_hit_tokens":80,'
            '"prompt_cache_miss_tokens":420}}'
        ),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(name="deepseek", base_url="https://api.deepseek.com", model_name="deepseek-chat")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    async for _ in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        pass

    assert meta["usage"]["cache_read_tokens"] == 80


def test_parse_openai_compatible_usage_no_cache_field_is_none_not_zero():
    """CR141 acceptance 2: a provider that never mentions a cache field at
    all must yield None — never a fabricated 0."""
    usage = {"prompt_tokens": 500, "completion_tokens": 10, "total_tokens": 510}
    parsed = _parse_openai_compatible_usage(usage)
    assert parsed["cache_read_tokens"] is None


def test_parse_openai_compatible_usage_explicit_zero_cache_stays_zero():
    """Contrast case: a REPORTED 0 is a real measurement and must survive as
    0, not be conflated with the None-means-unmeasured case above."""
    usage = {
        "prompt_tokens": 500, "completion_tokens": 10,
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    parsed = _parse_openai_compatible_usage(usage)
    assert parsed["cache_read_tokens"] == 0
    assert parsed["cache_read_tokens"] is not None


def test_parse_openai_compatible_usage_no_provider_reports_a_write_fee():
    parsed = _parse_openai_compatible_usage({"prompt_tokens": 1, "completion_tokens": 1})
    assert parsed["cache_write_tokens"] is None


# ── Anthropic split-frame usage ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_anthropic_parses_usage_split_across_message_start_and_delta():
    lines = [
        _sse(
            '{"type":"message_start","message":{"id":"msg_1","usage":'
            '{"input_tokens":1000,"output_tokens":1,'
            '"cache_creation_input_tokens":50,"cache_read_input_tokens":200}}}'
        ),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"PO"}}'),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"NG"}}'),
        _sse('{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":42}}'),
        _sse('{"type":"message_stop"}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    assert meta["usage"] == {
        "input_tokens": 1000,
        "cache_read_tokens": 200,
        "cache_write_tokens": 50,
        # Overwritten by message_delta's CUMULATIVE count, not message_start's
        # streaming placeholder (1).
        "output_tokens": 42,
    }
    assert meta["finish_reason"] == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_cache_fields_absent_when_provider_omits_them():
    """A message_start with no cache keys at all leaves both None — same
    NULL-not-0 guarantee as the OpenAI-compatible path."""
    lines = [
        _sse('{"type":"message_start","message":{"id":"msg_1","usage":{"input_tokens":10}}}'),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"OK"}}'),
        _sse('{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":3}}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    async for _ in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        pass

    assert meta["usage"]["cache_read_tokens"] is None
    assert meta["usage"]["cache_write_tokens"] is None


# ── acceptance 3: missing / malformed usage never breaks the stream ───────


@pytest.mark.asyncio
async def test_openai_compat_missing_usage_frame_still_yields_all_text():
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    assert "usage" not in meta


@pytest.mark.asyncio
async def test_openai_compat_malformed_usage_frame_still_yields_all_text():
    """`usage` present but not the expected shape (a bare string) must not
    crash parsing or the SSE loop."""
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[],"usage":"not-an-object"}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")], meta=meta,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    assert "usage" not in meta


@pytest.mark.asyncio
async def test_anthropic_malformed_usage_still_yields_all_text():
    lines = [
        _sse('{"type":"message_start","message":{"usage":"garbage"}}'),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"OK"}}'),
        _sse('{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":"also-garbage"}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    assert "".join(chunks) == "OK"


# ── full round-trip: LLMGateway.stream_chat -> llm_audit ──────────────────


@pytest.mark.asyncio
async def test_gateway_writes_usage_columns_on_success():
    gw = LLMGateway()
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"OK"}}]}'),
        _sse(
            '{"choices":[],"usage":{"prompt_tokens":42,"completion_tokens":7,'
            '"prompt_tokens_details":{"cached_tokens":5}}}'
        ),
        "data: [DONE]",
    ]
    provider = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    provider._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]
    gw._providers["vllm"] = provider  # type: ignore[attr-defined]

    user_id = uuid4()
    async for _ in gw.stream_chat(
        system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
        model_tier="cheap", locale="en",
        audit_user_id=user_id, audit_agent_id="market_analyst", audit_flow="one_on_one",
    ):
        pass

    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.input_tokens == 42
        assert row.output_tokens == 7
        assert row.cache_read_tokens == 5
        # Anthropic-only concept; this provider never reports it.
        assert row.cache_write_tokens is None


@pytest.mark.asyncio
async def test_gateway_writes_null_usage_columns_when_frame_is_absent():
    """CR141 acceptance 3: the audit row still writes, and every usage
    column is NULL — not 0 — when the provider never sent a usage frame."""
    gw = LLMGateway()
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"OK"}}]}'),
        "data: [DONE]",
    ]
    provider = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    provider._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]
    gw._providers["vllm"] = provider  # type: ignore[attr-defined]

    user_id = uuid4()
    chunks: list[str] = []
    async for c in gw.stream_chat(
        system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
        model_tier="cheap", locale="en",
        audit_user_id=user_id, audit_agent_id="market_analyst", audit_flow="one_on_one",
    ):
        chunks.append(c)

    assert "".join(chunks) == "OK"
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.input_tokens is None
        assert row.output_tokens is None
        assert row.cache_read_tokens is None
        assert row.cache_write_tokens is None


@pytest.mark.asyncio
async def test_gateway_writes_null_usage_columns_when_frame_is_malformed():
    gw = LLMGateway()
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"OK"}}]}'),
        _sse('{"choices":[],"usage":[1,2,3]}'),  # wrong type entirely
        "data: [DONE]",
    ]
    provider = OpenAICompatibleProvider(name="vllm", base_url="http://lan:8000", model_name="ami-llm")
    provider._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]
    gw._providers["vllm"] = provider  # type: ignore[attr-defined]

    user_id = uuid4()
    chunks: list[str] = []
    async for c in gw.stream_chat(
        system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
        model_tier="cheap", locale="en",
        audit_user_id=user_id, audit_agent_id="market_analyst", audit_flow="one_on_one",
    ):
        chunks.append(c)

    assert "".join(chunks) == "OK"
    with get_session() as s:
        row = s.execute(select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)).scalar_one()
        assert row.input_tokens is None
        assert row.cache_read_tokens is None
