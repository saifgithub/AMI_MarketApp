"""Unit tests for the LLM gateway: status surface + AnthropicProvider SSE parsing.

The AnthropicProvider tests mock httpx so they never touch the network — we
verify the streaming parser, the error path, and the request body shape.
Per-(plan, agent) tier routing lives in `app.services.tier_policy` and is
covered by `test_tier_policy.py`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest

from app.services.llm_gateway import (
    AnthropicProvider,
    ChatMessage,
    LLMGateway,
    MockProvider,
    TIER_TO_MODEL,
)


# ── gateway status ────────────────────────────────────────────────────────


def test_gateway_status_no_key_reports_mock():
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "mock"
    assert s["has_real_provider"] is False
    assert "mock" in s["providers_registered"]
    assert s["tier_to_model"] == dict(TIER_TO_MODEL)


def test_gateway_status_with_key_reports_anthropic(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "sk-ant-fake")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "anthropic"
    assert s["has_real_provider"] is True
    assert "anthropic" in s["providers_registered"]


# ── mock provider ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_provider_returns_canned_text():
    p = MockProvider()
    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="agent_id: portfolio_manager\nyou are the PM",
        messages=[ChatMessage(role="user", content="hi")],
    ):
        chunks.append(c)
    text = "".join(chunks)
    assert "Mock PM" in text or "Portfolio Manager" in text or "mock mode" in text.lower()


# ── anthropic provider SSE parser ─────────────────────────────────────────


class _FakeSSEResponse:
    """Stand-in for httpx.AsyncClient.stream() response."""

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
    def __init__(self, resp: _FakeSSEResponse, captured: dict):
        self._resp = resp
        self._captured = captured

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        self._captured["method"] = method
        self._captured["url"] = url
        self._captured["json"] = json
        yield self._resp

    async def aclose(self) -> None:
        pass


def _sse(payload: str) -> str:
    return f"data: {payload}"


@pytest.mark.asyncio
async def test_anthropic_provider_parses_text_deltas():
    captured: dict = {}
    lines = [
        _sse('{"type":"message_start"}'),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"PO"}}'),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"NG"}}'),
        _sse('{"type":"message_stop"}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="be terse",
        messages=[ChatMessage(role="user", content="ping")],
        model_tier="cheap",
        max_tokens=32,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    body = captured["json"]
    assert body["model"] == TIER_TO_MODEL["cheap"]
    assert body["max_tokens"] == 32
    assert body["stream"] is True
    assert body["system"] == "be terse"
    assert body["messages"] == [{"role": "user", "content": "ping"}]


@pytest.mark.asyncio
async def test_anthropic_provider_error_yields_inline_error():
    captured: dict = {}
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(429, [], body=b'{"error":"rate_limited"}'),
        captured,
    )

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    full = "".join(chunks)
    assert "429" in full
    assert "Anthropic" in full


@pytest.mark.asyncio
async def test_anthropic_provider_tolerates_junk_lines():
    """Empty lines, non-data lines, and bad JSON must not crash the stream."""
    captured: dict = {}
    lines = [
        "",
        "event: ping",
        _sse("not-json"),
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"OK"}}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    assert "".join(chunks) == "OK"
