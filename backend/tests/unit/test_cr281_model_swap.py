"""CR281 — swapping a model or provider on a slot is an env change, nothing else.

Four properties, each the way a swap used to break:
  1. Two different URL+model pairs per slot, set ONLY through env vars, both
     route to the right host with the right model id (no code edit between).
  2. Auth: a configured key is sent as `Authorization: Bearer <key>` on both
     kinds; an empty/blank key sends no auth header at all (never `Bearer `).
  3. A base URL with or without `/v1` (or a trailing slash) reaches the same
     `/v1/chat/completions` — it used to become `/v1/v1/...` and 404.
  4. No model id literal in the gateway's / routers' decision paths.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.services import llm_gateway as gw_mod
from app.services.llm_gateway import (
    LLMGateway,
    OpenAICompatibleProvider,
    VLLMProvider,
    normalise_base_url,
    openai_compatible_headers,
)

_APP = Path(__file__).resolve().parents[2] / "app"

# slot -> (url env, model env, key env, extra env that turns the slot on / sets kind)
_SLOTS = {
    "vllm": ("VLLM_BASE_URL", "VLLM_MODEL", "VLLM_API_KEY", {}),
    "vllm_fallback": ("VLLM_FALLBACK_BASE_URL", "VLLM_FALLBACK_MODEL", "VLLM_FALLBACK_API_KEY", {}),
    "glm": ("GLM_BASE_URL", "GLM_MODEL", "GLM_API_KEY", {}),
    "kimi": ("KIMI_BASE_URL", "KIMI_MODEL", "KIMI_API_KEY", {}),
    "deepseek": ("DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEY", {}),
    "qwen": ("QWEN_BASE_URL", "QWEN_MODEL", "DASHSCOPE_API_KEY", {}),
    "gemini": ("GEMINI_BASE_URL", "GEMINI_MODEL", "GOOGLE_AI_API_KEY", {}),
}
# slots a key alone turns on (a missing key means "not registered")
_KEY_REGISTERS = {"kimi", "deepseek", "qwen", "gemini"}

_ENV_NAMES = {n for v in _SLOTS.values() for n in v[:3]} | {
    "VLLM_KIND", "VLLM_FALLBACK_KIND", "LLM_PROVIDER_ALLOWLIST",
    "ANTHROPIC_API_KEY", "LLM_FORCE_PROVIDER",
}


def _sse() -> httpx.Response:
    body = (
        'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
        "data: [DONE]\n\n"
    )
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def _gateway(monkeypatch, env: dict[str, str]) -> tuple[LLMGateway, list[httpx.Request]]:
    """A gateway built from a Settings parsed from `env` ALONE, with every
    provider's transport replaced by a recorder (no network)."""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(gw_mod, "settings", Settings(_env_file=None))
    g = LLMGateway()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _sse()

    for p in g._providers.values():
        if isinstance(p, OpenAICompatibleProvider):
            p._client = httpx.AsyncClient(
                base_url=p._client.base_url,
                headers=p._client.headers,
                transport=httpx.MockTransport(handler),
            )
    return g, seen


async def _call(g: LLMGateway, slot: str) -> None:
    async for _ in g.stream_chat(
        system_prompt="s",
        messages=[gw_mod.ChatMessage(role="user", content="hi")],
        provider_name=slot,
        max_tokens=5,
    ):
        pass


def _env_for(slot: str, url: str, model: str, key: str = "k-test") -> dict[str, str]:
    u, m, k, extra = _SLOTS[slot]
    env = {u: url, m: model, **extra}
    if key:
        env[k] = key
    if slot == "vllm_fallback":
        env["VLLM_FALLBACK_KIND"] = "vllm"
    return env


# ── 1. swap by env only ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("slot", sorted(_SLOTS))
async def test_a_slot_swaps_url_and_model_by_env_alone(monkeypatch, slot):
    for url, model in (
        ("https://host-one.example.com", "vendor-a/model-one"),
        ("https://host-two.example.com", "vendor-b/model-two"),
    ):
        g, seen = _gateway(monkeypatch, _env_for(slot, url, model))
        await _call(g, slot)
        assert len(seen) == 1
        req = seen[0]
        assert req.url.host == httpx.URL(url).host
        assert req.url.path == "/v1/chat/completions"
        assert json.loads(req.content)["model"] == model


@pytest.mark.parametrize("slot", ["vllm", "vllm_fallback", "glm", "kimi", "deepseek", "qwen", "gemini"])
def test_status_tiers_resolve_to_the_slots_configured_model(monkeypatch, slot):
    """A swapped model must be what status() advertises for that slot."""
    env = _env_for(slot, "https://host-one.example.com", "vendor-a/model-one")
    g, _ = _gateway(monkeypatch, env)
    monkeypatch.setattr(gw_mod.settings, "llm_force_provider", slot)
    assert g.status()["active_provider"] == slot
    assert set(g.status()["tier_to_model"].values()) == {"vendor-a/model-one"}


# ── 2. keyed vs keyless ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("slot", ["vllm", "vllm_fallback", "glm"])
@pytest.mark.parametrize("kind", ["vllm", "openai"])
async def test_auth_header_present_only_when_a_key_is_configured(monkeypatch, slot, kind):
    kind_env = {"vllm": "VLLM_KIND", "vllm_fallback": "VLLM_FALLBACK_KIND"}
    for key, expect in (("secret-key-123", "Bearer secret-key-123"), ("", None), ("   ", None)):
        env = _env_for(slot, "http://h.example.com:8004", "m", key="")
        if key:
            env[_SLOTS[slot][2]] = key
        if slot in kind_env:
            env[kind_env[slot]] = kind
        g, seen = _gateway(monkeypatch, env)
        await _call(g, slot)
        assert seen[0].headers.get("authorization") == expect
        if expect is None:
            assert "authorization" not in {h.lower() for h in seen[0].headers}


def test_headers_helper_never_emits_an_empty_or_placeholder_bearer():
    assert "Authorization" not in openai_compatible_headers(None)
    assert "Authorization" not in openai_compatible_headers("")
    assert "Authorization" not in openai_compatible_headers("  \n")
    assert openai_compatible_headers(" k ")["Authorization"] == "Bearer k"


def test_vllm_kind_keeps_a_configured_key():
    p = VLLMProvider(base_url="http://h:8000", model_name="m", api_key="abc", kind="vllm")
    assert p._client.headers["Authorization"] == "Bearer abc"
    q = VLLMProvider(base_url="http://h:8000", model_name="m", api_key=None, kind="vllm")
    assert "Authorization" not in q._client.headers


# ── 3. URL shapes ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "http://h.example.com:8000",
        "http://h.example.com:8000/",
        "http://h.example.com:8000/v1",
        "http://h.example.com:8000/v1/",
        "  http://h.example.com:8000/v1  ",
        "http://h.example.com:8000/v1/openai",
        "http://h.example.com:8000/v1/openai/",
    ],
)
def test_normalise_base_url_collapses_every_spelling(raw):
    assert normalise_base_url(raw) == "http://h.example.com:8000"


def test_normalise_keeps_a_path_prefix():
    assert normalise_base_url("https://proxy.example.com/llm/v1") == "https://proxy.example.com/llm"


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/", "/v1", "/v1/"])
async def test_chat_and_models_paths_never_double_v1(monkeypatch, suffix):
    env = _env_for("vllm", "http://h.example.com:8000" + suffix, "m")
    g, seen = _gateway(monkeypatch, env)
    await _call(g, "vllm")
    assert seen[0].url.path == "/v1/chat/completions"
    p = g._providers["vllm"]
    assert str(p._client.base_url).rstrip("/") == "http://h.example.com:8000"


# ── 4. no model-id literals in decision paths ────────────────────────────────

# Anthropic's tier→model aliases are the vendor's own fixed ids for the one
# provider that is not a single-model OpenAI-compatible slot (TIER_TO_MODEL).
# Everything else — every OpenAI-compatible slot's model and URL — comes from
# Settings. Adding a literal here means a model swap needs a code edit again.
_ALLOWED_MODEL_LITERALS = {"claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"}
_MODEL_ID = re.compile(
    r"^(claude-|deepseek-|qwen[-\d]|gemini-|glm-|kimi-|ami-llm|ling-|gpt-|llama|mistral|o\d-)", re.I
)
_DECISION_FILES = ("services/llm_gateway.py", "services/provider_policy.py", "services/tier_policy.py")


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


@pytest.mark.parametrize("rel", _DECISION_FILES)
def test_no_model_id_literals_in_the_decision_paths(rel):
    found = [
        s for s in _string_constants(_APP / rel)
        if _MODEL_ID.match(s.strip()) and s not in _ALLOWED_MODEL_LITERALS
    ]
    assert not found, (
        f"{rel} hard-codes model id(s) {found}: a model swap must be an env change. "
        "Add a Settings field instead."
    )


def test_no_hardcoded_openai_compatible_endpoint_in_the_gateway():
    urls = [s for s in _string_constants(_APP / "services/llm_gateway.py")
            if s.startswith(("http://", "https://")) and "anthropic.com" not in s]
    assert not urls, f"endpoint literal(s) in the gateway: {urls}"
