"""CR281 — LIVE model-swap proof against DeepInfra, through the real LLMGateway.

NOT part of the unit suite: this directory is outside `testpaths = ["tests"]`, so
`pytest tests/unit` and CI never reach it. It also skips (never fails) unless
`DEEPINFRA_API_KEY` is in the process environment. The key is read from the
environment only: it is never written to a file, a fixture, or output.

Run it once by hand:

    set -a; . <env file holding DEEPINFRA_API_KEY>; set +a
    cd backend && .venv/bin/python -m pytest tests_live -q -s -p no:cacheprovider

It makes at most 4 completion calls (+1 catalogue GET), each max_tokens=50.
What it proves, by env only (no code edit between steps):
  a. a slot (vllm_fallback, kind openai) pointed at DeepInfra + DeepSeek-V4-Flash answers;
  b. the same slot swapped to a second catalogue model by env answers, as that model;
  c. with the key unset the call fails as a loud 401/403, and no Authorization
     header was sent;
  d. (optional) the keyless on-prem Ling slot (kind vllm), when reachable.
"""

from __future__ import annotations

import os

import httpx
import pytest

from app.core.config import Settings
from app.services import llm_gateway as gw_mod
from app.services.llm_gateway import ChatMessage, LLMGateway

_KEY = os.environ.get("DEEPINFRA_API_KEY", "")
pytestmark = pytest.mark.skipif(not _KEY, reason="DEEPINFRA_API_KEY not set")

_BASE = "https://api.deepinfra.com"
_MODEL_A = "deepseek-ai/DeepSeek-V4-Flash"
_MODEL_B = "zai-org/GLM-5.3-Flash"
_LING_URL = "http://100.98.142.64:8004"
_LING_MODEL = "ling-3.0-flash-fin-fp4"

_ENV_NAMES = (
    "VLLM_BASE_URL", "VLLM_MODEL", "VLLM_API_KEY", "VLLM_KIND",
    "VLLM_FALLBACK_BASE_URL", "VLLM_FALLBACK_MODEL", "VLLM_FALLBACK_API_KEY",
    "VLLM_FALLBACK_KIND", "LLM_PROVIDER_ALLOWLIST",
    "ANTHROPIC_API_KEY", "KIMI_API_KEY", "GOOGLE_AI_API_KEY",
)


def _gateway(monkeypatch, env: dict[str, str]) -> LLMGateway:
    # The audit row needs a database this script deliberately does not have.
    from app.services import audit

    monkeypatch.setattr(audit, "record_llm_call", lambda *a, **k: None)
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(gw_mod, "settings", Settings(_env_file=None))
    return LLMGateway()


async def _ask(g: LLMGateway, slot: str) -> tuple[str, dict]:
    meta: dict = {}
    chunks = []
    async for c in g.stream_chat(
        system_prompt="You are a terse test endpoint.",
        messages=[ChatMessage(role="user", content="Reply with the single word: pong")],
        provider_name=slot,
        max_tokens=50,
        meta=meta,
        audit_flow="cr281_live_swap",
    ):
        chunks.append(c)
    return "".join(chunks), meta


def _summary(label: str, text: str, meta: dict) -> None:
    usage = meta.get("usage") or {}
    print(
        f"\n[live] {label}: reply_chars={len(text)} model={meta.get('reported_model')!r} "
        f"finish={meta.get('finish_reason')!r} usage={usage} "
        f"stream_error={meta.get('stream_error_status')}"
    )


def _env(model: str, key: str) -> dict[str, str]:
    env = {
        "VLLM_FALLBACK_BASE_URL": _BASE,
        "VLLM_FALLBACK_MODEL": model,
        "VLLM_FALLBACK_KIND": "openai",
    }
    if key:
        env["VLLM_FALLBACK_API_KEY"] = key
    return env


@pytest.mark.asyncio
async def test_swap_model_by_env_then_drop_the_key(monkeypatch):
    # a. DeepSeek-V4-Flash
    g = _gateway(monkeypatch, _env(_MODEL_A, _KEY))
    assert "authorization" in {h.lower() for h in g._providers["vllm_fallback"]._client.headers}
    text, meta = await _ask(g, "vllm_fallback")
    _summary("a", text, meta)
    assert "stream_error" not in meta, "DeepInfra call failed"
    assert meta["configured_model"] == _MODEL_A
    assert (meta.get("usage") or {}).get("output_tokens", 1) > 0

    # catalogue check for the second model (GET, no completion, no spend)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{_BASE}/v1/openai/models", headers={"Authorization": f"Bearer {_KEY}"})
    assert r.status_code == 200
    assert _MODEL_B in {m.get("id") for m in r.json().get("data", [])}, "model B not in catalogue"

    # b. swap the model by env only
    g = _gateway(monkeypatch, _env(_MODEL_B, _KEY))
    text, meta = await _ask(g, "vllm_fallback")
    _summary("b", text, meta)
    assert "stream_error" not in meta, "DeepInfra call failed after swap"
    assert meta["configured_model"] == _MODEL_B

    # c. no key: loud auth failure, and no Authorization header was ever sent
    g = _gateway(monkeypatch, _env(_MODEL_A, ""))
    assert "authorization" not in {h.lower() for h in g._providers["vllm_fallback"]._client.headers}
    text, meta = await _ask(g, "vllm_fallback")
    _summary("c", text, meta)
    assert meta.get("stream_error_status") in (401, 403)
    assert "[AMI error: HTTP" in text


@pytest.mark.asyncio
async def test_keyless_onprem_ling_slot_when_reachable(monkeypatch):
    try:
        httpx.get(f"{_LING_URL}/v1/models", timeout=3)
    except Exception:
        pytest.skip("Ling host not reachable from here")
    g = _gateway(monkeypatch, {
        "VLLM_FALLBACK_BASE_URL": _LING_URL,
        "VLLM_FALLBACK_MODEL": _LING_MODEL,
        "VLLM_FALLBACK_KIND": "vllm",
    })
    assert "authorization" not in {h.lower() for h in g._providers["vllm_fallback"]._client.headers}
    text, meta = await _ask(g, "vllm_fallback")
    _summary("d", text, meta)
    assert "stream_error" not in meta
