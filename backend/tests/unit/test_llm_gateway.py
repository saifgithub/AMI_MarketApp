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
    VLLMProvider,
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


def test_gateway_prefers_vllm_when_both_keys_set(monkeypatch):
    """On-prem vLLM wins over Anthropic when both are configured."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "sk-ant-fake")
    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "vllm_model", "gemma-4-31b-it-nvfp4")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "vllm"
    assert s["providers_registered"] == ["anthropic", "mock", "vllm"]
    # vLLM serves a single model; every tier resolves to it.
    assert s["tier_to_model"]["cheap"] == "gemma-4-31b-it-nvfp4"
    assert s["tier_to_model"]["premium"] == "gemma-4-31b-it-nvfp4"


def test_gateway_status_with_only_vllm(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "vllm_model", "gemma-4-31b-it-nvfp4")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "vllm"
    assert s["has_real_provider"] is True


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


# ── vLLM provider SSE parser ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vllm_provider_parses_openai_deltas():
    captured: dict = {}
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"role":"assistant","content":""}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        "data: [DONE]",
    ]
    p = VLLMProvider(base_url="http://lan:8000", model_name="gemma-4-31b-it-nvfp4")
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="be terse",
        messages=[ChatMessage(role="user", content="ping")],
        max_tokens=32,
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    body = captured["json"]
    assert body["model"] == "gemma-4-31b-it-nvfp4"
    assert body["max_tokens"] == 32
    assert body["stream"] is True
    # OpenAI/vLLM puts the system prompt inside `messages`, not as a sibling.
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    assert body["messages"][1] == {"role": "user", "content": "ping"}


@pytest.mark.asyncio
async def test_vllm_provider_error_yields_inline_error():
    captured: dict = {}
    p = VLLMProvider(base_url="http://lan:8000", model_name="gemma-4-31b-it-nvfp4")
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(503, [], body=b'{"error":"server overloaded"}'),
        captured,
    )

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    full = "".join(chunks)
    assert "503" in full
    assert "vLLM" in full


@pytest.mark.asyncio
async def test_vllm_provider_tolerates_empty_delta_chunks():
    """vLLM emits chunks with empty `delta` between content tokens — skip them."""
    captured: dict = {}
    lines = [
        _sse('{"choices":[{"index":0,"delta":{}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"OK"}}]}'),
        _sse('{"choices":[]}'),
        "data: [DONE]",
    ]
    p = VLLMProvider(base_url="http://lan:8000", model_name="gemma-4-31b-it-nvfp4")
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    assert "".join(chunks) == "OK"


@pytest.mark.asyncio
async def test_vllm_provider_sends_bearer_when_api_key_set():
    """When api_key is configured, the underlying httpx client carries the
    bearer header on every outbound request."""
    p = VLLMProvider(
        base_url="http://lan:8000",
        model_name="gemma-4-31b-it-nvfp4",
        api_key="topsecret",
    )
    try:
        assert p._client.headers.get("Authorization") == "Bearer topsecret"
        assert p._client.headers.get("Content-Type") == "application/json"
    finally:
        await p.aclose()


@pytest.mark.asyncio
async def test_vllm_provider_omits_bearer_without_api_key():
    p = VLLMProvider(base_url="http://lan:8000", model_name="gemma-4-31b-it-nvfp4")
    try:
        assert "Authorization" not in p._client.headers
    finally:
        await p.aclose()
