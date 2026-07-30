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
    OpenAICompatibleProvider,
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
    monkeypatch.setattr(cfg.settings, "vllm_model", "ami-llm")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "vllm"
    assert s["providers_registered"] == ["anthropic", "mock", "vllm"]
    # vLLM serves a single model; every tier resolves to it.
    assert s["tier_to_model"]["cheap"] == "ami-llm"
    assert s["tier_to_model"]["premium"] == "ami-llm"


def test_gateway_status_with_only_vllm(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "vllm_model", "ami-llm")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "vllm"
    assert s["has_real_provider"] is True


def test_gateway_status_with_only_kimi(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "kimi_api_key", "sk-kimi-fake")
    monkeypatch.setattr(cfg.settings, "kimi_model", "kimi-for-coding")
    g = LLMGateway()
    s = g.status()
    assert s["active_provider"] == "kimi"
    assert s["has_real_provider"] is True
    # Kimi serves a single selected model; every tier resolves to it.
    assert s["tier_to_model"]["cheap"] == "kimi-for-coding"
    assert s["tier_to_model"]["premium"] == "kimi-for-coding"


def test_gateway_kimi_ranks_below_vllm_and_anthropic(monkeypatch):
    """With every provider configured, preference order still wins — Kimi is
    a candidate B7 provider being tested, not yet a default (CR126/D-068)."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "sk-ant-fake")
    monkeypatch.setattr(cfg.settings, "kimi_api_key", "sk-kimi-fake")
    g = LLMGateway()
    assert g.status()["active_provider"] == "vllm"
    assert g.status()["providers_registered"] == ["anthropic", "kimi", "mock", "vllm"]


def test_llm_force_provider_overrides_preference(monkeypatch):
    """LLM_FORCE_PROVIDER lets Kimi be exercised for real without touching
    _PREFERENCE or unregistering vLLM."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "kimi_api_key", "sk-kimi-fake")
    monkeypatch.setattr(cfg.settings, "llm_force_provider", "kimi")
    g = LLMGateway()
    assert g.status()["active_provider"] == "kimi"


def test_llm_force_provider_falls_through_when_unregistered(monkeypatch):
    """A typo'd/unconfigured forced provider must never 500 a live flow —
    fall through to normal preference instead."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "llm_force_provider", "kimi")  # not registered
    g = LLMGateway()
    assert g.status()["active_provider"] == "vllm"


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
    # Mock copy carries the AMI brand + fallback signal regardless of which
    # agent matched.
    assert "AMI" in text
    assert "fallback" in text.lower() or "offline" in text.lower()


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
    assert "AMI error" in full
    assert "upstream provider" in full


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
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
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
    assert body["model"] == "ami-llm"
    assert body["max_tokens"] == 32
    assert body["stream"] is True
    # OpenAI/vLLM puts the system prompt inside `messages`, not as a sibling.
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    assert body["messages"][1] == {"role": "user", "content": "ping"}


@pytest.mark.asyncio
async def test_vllm_provider_error_yields_inline_error():
    captured: dict = {}
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
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
    assert "AMI error" in full
    assert "upstream provider" in full
    assert "vllm" in full


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
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
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
        model_name="ami-llm",
        api_key="topsecret",
    )
    try:
        assert p._client.headers.get("Authorization") == "Bearer topsecret"
        assert p._client.headers.get("Content-Type") == "application/json"
    finally:
        await p.aclose()


@pytest.mark.asyncio
async def test_vllm_provider_omits_bearer_without_api_key():
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    try:
        assert "Authorization" not in p._client.headers
    finally:
        await p.aclose()


# ── OpenAICompatibleProvider (Kimi, and any future chat-completions API,
#    CR017) — proves the generalized class works under a non-vllm name ─────


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_deltas_under_kimi_name():
    """Same OpenAI-shaped SSE parsing VLLMProvider already covers, but through
    a plain OpenAICompatibleProvider("kimi", ...) instance — proving the
    generalization didn't silently couple the parser to the vllm name."""
    captured: dict = {}
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(
        name="kimi", base_url="https://api.kimi.com/coding", model_name="kimi-for-coding",
        api_key="sk-kimi-fake",
    )
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="be terse",
        messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"
    assert captured["json"]["model"] == "kimi-for-coding"


@pytest.mark.asyncio
async def test_openai_compatible_provider_skips_reasoning_content_deltas():
    """Kimi's Coding Plan models (kimi-for-coding, k3) are reasoning models —
    verified live (CR130) that streaming deltas carry reasoning as a separate
    `reasoning_content` field, with no `content` key at all on those chunks,
    before the real answer starts arriving under `content`. The parser must
    silently skip the reasoning chunks and only yield real content — not
    error, and not leak chain-of-thought into what an agent "says"."""
    captured: dict = {}
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"role":"assistant","content":null}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"reasoning_content":"thinking..."}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"reasoning_content":"more thinking"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
        "data: [DONE]",
    ]
    p = OpenAICompatibleProvider(
        name="kimi", base_url="https://api.kimi.com/coding", model_name="kimi-for-coding",
    )
    p._client = _FakeClient(_FakeSSEResponse(200, lines), captured)  # type: ignore[assignment]

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    assert "".join(chunks) == "PONG"


@pytest.mark.asyncio
async def test_openai_compatible_provider_error_names_the_provider():
    """Errors must identify which provider failed — generic "on-prem" wording
    would be actively wrong for a hosted API like Kimi."""
    captured: dict = {}
    p = OpenAICompatibleProvider(
        name="kimi", base_url="https://api.kimi.com/coding", model_name="kimi-for-coding",
        api_key="sk-kimi-fake",
    )
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(429, [], body=b'{"error":"rate_limited"}'),
        captured,
    )

    chunks: list[str] = []
    async for c in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")],
    ):
        chunks.append(c)

    full = "".join(chunks)
    assert "429" in full
    assert "kimi" in full
    assert "on-prem" not in full


@pytest.mark.asyncio
async def test_openai_compatible_provider_extra_body_merged_into_request():
    """extra_body (CR017 §3 — e.g. Qwen's enable_thinking) must reach the
    outbound request body without disturbing the required fields."""
    captured: dict = {}
    p = OpenAICompatibleProvider(
        name="kimi", base_url="https://api.kimi.com/coding", model_name="kimi-for-coding",
        extra_body={"reasoning_effort": "low"},
    )
    p._client = _FakeClient(_FakeSSEResponse(200, ["data: [DONE]"]), captured)  # type: ignore[assignment]

    async for _ in p.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="ping")],
    ):
        pass

    assert captured["json"]["reasoning_effort"] == "low"
    assert captured["json"]["model"] == "kimi-for-coding"


# ── CR077 Phase 0 second guard — prefix-cache startup check ──────────────


class _FakeMetricsResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code != 200:
            raise Exception(f"HTTP {self.status_code}")


_SAMPLE_METRICS_ENABLED = """
vllm:prefix_cache_queries_total{engine="0",model_name="ami-llm"} 2.0e+08
vllm:prefix_cache_hits_total{engine="0",model_name="ami-llm"} 1.0e+08
vllm:cache_config_info{engine="0",enable_prefix_caching="True",block_size="2096"} 1.0
"""

_SAMPLE_METRICS_DISABLED = """
vllm:prefix_cache_queries_total{engine="0",model_name="ami-llm"} 0.0
vllm:prefix_cache_hits_total{engine="0",model_name="ami-llm"} 0.0
vllm:cache_config_info{engine="0",enable_prefix_caching="False",block_size="2096"} 1.0
"""


@pytest.mark.asyncio
async def test_prefix_cache_status_logs_hit_rate_when_enabled(monkeypatch):
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    try:
        async def fake_get(url, timeout=5.0):
            assert url == "/metrics"
            return _FakeMetricsResponse(_SAMPLE_METRICS_ENABLED)

        monkeypatch.setattr(p._client, "get", fake_get)

        from app.services import llm_gateway as gw

        logged: list[dict] = []
        monkeypatch.setattr(gw.logger, "info", lambda event, **kw: logged.append({"event": event, **kw}))
        monkeypatch.setattr(
            gw.logger, "warn",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not warn when enabled")),
        )

        await p.log_prefix_cache_status()

        status = next(l for l in logged if l["event"] == "vllm_prefix_cache_status")
        assert status["enable_prefix_caching"] is True
        assert status["hits_total"] == 1.0e08
        assert status["queries_total"] == 2.0e08
        assert status["hit_rate"] == pytest.approx(0.5)
    finally:
        await p.aclose()


@pytest.mark.asyncio
async def test_prefix_cache_status_warns_loudly_when_disabled(monkeypatch):
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    try:
        async def fake_get(url, timeout=5.0):
            return _FakeMetricsResponse(_SAMPLE_METRICS_DISABLED)

        monkeypatch.setattr(p._client, "get", fake_get)

        from app.services import llm_gateway as gw

        warned: list[dict] = []
        monkeypatch.setattr(gw.logger, "info", lambda event, **kw: None)
        monkeypatch.setattr(gw.logger, "warn", lambda event, **kw: warned.append({"event": event, **kw}))

        await p.log_prefix_cache_status()

        assert any(w["event"] == "vllm_prefix_caching_disabled" for w in warned)
    finally:
        await p.aclose()


@pytest.mark.asyncio
async def test_prefix_cache_status_unreachable_warns_not_raises(monkeypatch):
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    try:
        async def fake_get(url, timeout=5.0):
            raise Exception("connection refused")

        monkeypatch.setattr(p._client, "get", fake_get)

        from app.services import llm_gateway as gw

        warned: list[dict] = []
        monkeypatch.setattr(gw.logger, "warn", lambda event, **kw: warned.append({"event": event, **kw}))

        await p.log_prefix_cache_status()  # must not raise

        assert any(w["event"] == "vllm_prefix_cache_check_failed" for w in warned)
    finally:
        await p.aclose()


@pytest.mark.asyncio
async def test_gateway_check_prefix_cache_at_startup_is_noop_without_vllm():
    """No vLLM provider registered ⇒ no-op, doesn't raise."""
    g = LLMGateway()
    await g.check_prefix_cache_at_startup()  # must not raise


@pytest.mark.asyncio
async def test_gateway_check_prefix_cache_at_startup_ignores_kimi(monkeypatch):
    """Kimi registered (no vLLM) must NOT trip the vLLM-only /metrics probe —
    a bare OpenAICompatibleProvider instance must fail the isinstance(VLLMProvider)
    check, or startup would try to scrape a hosted API path that doesn't exist."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "kimi_api_key", "sk-kimi-fake")
    g = LLMGateway()
    assert not isinstance(g._providers["kimi"], VLLMProvider)
    await g.check_prefix_cache_at_startup()  # must not raise or hit /metrics
