"""Provider registry + gateway forcing + single-call replay path (DESIGN.md §4.2).

Why this exists: v1 (`docs/tools/room_investigation/room_kimi_gateway.py`)
scattered provider knowledge across `force_kimi_gateway` /
`force_vllm_gateway` / `force_deepinfra_gateway` plus replay's standalone
`_call_kimi` / `_call_vllm` / `_call_deepinfra`, with inconsistent flags per
script and the DeepInfra base-URL split (bare host for the
OpenAICompatibleProvider path, `/v1/openai` for replay's own path — mixing
them 404'd live 2026-09-26). V2 puts every provider in one `PROVIDERS`
registry: `force_provider()` handles the in-process LLMGateway surgery for
full-Room runs, `direct_call()` is the single-call prompt-replay path, and
each endpoint's URL-suffix rule lives in exactly one place.

Kept from v1, strengthened: after forcing, the ACTIVE provider AND the
resolved model are verified against the request — a force that didn't take
would silently score vLLM under a Kimi label.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    from library import env_bootstrap
except ImportError:
    import env_bootstrap

if TYPE_CHECKING:
    from app.services.llm_gateway import LLMGateway

REASONING_TOKEN_TOLERANCE = 2  # RES009: kimi leaves ~1 residual even with thinking disabled

# CR247 D25: every harness convene runs with a 5000-token output floor so a
# cheap-tier truncation (bear_researcher cut at 1400 live on GLM-5.3-Flash,
# 2026-09-28) can never contaminate a baseline measurement. Harness-only —
# production caps are untouched.
HARNESS_MAX_TOKENS_FLOOR = 5000

_DIRECT_CALL_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str
    default_model: str
    api_key_env: str | None
    extra_body: dict | None
    supports_temperature: bool


PROVIDERS: dict[str, ProviderSpec] = {
    "kimi": ProviderSpec(
        name="kimi",
        base_url="https://api.moonshot.ai",
        default_model="kimi-k3",
        api_key_env="KIMI_API_KEY",
        extra_body={"thinking": {"type": "disabled"}},
        supports_temperature=False,
    ),
    # base_url is resolved from VLLM_BASE_URL at call time, never at import —
    # the registry entry deliberately carries an empty one.
    "vllm": ProviderSpec(
        name="vllm",
        base_url="",
        default_model=env_bootstrap.VLLM_DEFAULT_MODEL,
        api_key_env=None,
        extra_body=None,
        supports_temperature=True,
    ),
    # Bare host: OpenAICompatibleProvider appends /v1/chat/completions itself.
    # The /v1/openai suffix exists ONLY in direct_call's own URL below.
    "deepinfra": ProviderSpec(
        name="deepinfra",
        base_url="https://api.deepinfra.com",
        default_model="zai-org/GLM-5.3-Flash",
        api_key_env="DEEPINFR_API_KEY",  # codebase's own spelling, no trailing A
        extra_body=None,
        supports_temperature=True,
    ),
}


def _resolve(name: str) -> tuple[ProviderSpec, str, str | None]:
    spec = PROVIDERS[name]
    if name == "kimi":
        return spec, spec.base_url, env_bootstrap.require_kimi_open_platform_key()
    if name == "deepinfra":
        key = env_bootstrap.require_keys(spec.api_key_env)[spec.api_key_env]
        return spec, spec.base_url, key
    base_url, _ = env_bootstrap.require_vllm()
    return spec, base_url, None


def force_provider(
    name: str, *, model: str | None = None, temperature: float | None = None
) -> "LLMGateway":
    """Build an LLMGateway forced to `name` for every call, THIS PROCESS ONLY.

    Never set LLM_FORCE_PROVIDER on melehost's shared container — that would
    redirect all live users' traffic. `Settings` is a per-process singleton,
    so mutating it here is safe precisely because this runs in a throwaway
    Mac-side process (v1 module docstring has the full story).
    """
    if name not in PROVIDERS:
        raise SystemExit(
            f"unknown provider {name!r} — valid: {', '.join(sorted(PROVIDERS))}"
        )
    spec = PROVIDERS[name]
    if temperature is not None:
        if not spec.supports_temperature:
            raise SystemExit(
                f"provider {name!r} does not support temperature pinning — "
                "use the replay path (direct_call / room_replay) on a provider "
                "that does (vllm, deepinfra)"
            )
        raise SystemExit(
            "temperature is not plumbed through LLMGateway/RoomRunner anywhere "
            "in this codebase (RES009 01-06) — use direct_call() for a "
            "single-agent, pinned-temperature test instead"
        )
    spec, base_url, api_key = _resolve(name)
    resolved_model = model or (
        os.environ.get("VLLM_MODEL", spec.default_model)
        if name == "vllm"
        else spec.default_model
    )

    env_bootstrap.ensure_backend_path()
    from app.core.config import settings
    from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider

    settings.llm_force_provider = name
    settings.vllm_max_tokens_floor = max(
        settings.vllm_max_tokens_floor or 0, HARNESS_MAX_TOKENS_FLOOR
    )
    settings.kimi_max_tokens_floor = max(
        settings.kimi_max_tokens_floor or 0, HARNESS_MAX_TOKENS_FLOOR
    )
    if name == "kimi":
        settings.kimi_base_url = base_url
        settings.kimi_model = resolved_model
    elif name == "vllm":
        settings.vllm_base_url = base_url
        settings.vllm_model = resolved_model

    gateway = LLMGateway()
    if name == "kimi":
        # LLMGateway's own kimi branch takes no extra_body (that ctor param
        # only reaches its Qwen branch), so the entry is replaced with a
        # manually-built provider carrying the thinking-disabled body —
        # same base_url/model/key/floor the gateway would have used.
        gateway._providers["kimi"] = OpenAICompatibleProvider(  # noqa: SLF001
            name="kimi",
            base_url=base_url,
            model_name=resolved_model,
            api_key=api_key,
            max_tokens_floor=settings.kimi_max_tokens_floor,
            extra_body=spec.extra_body,
        )
    elif name == "deepinfra":
        # Not registered by LLMGateway.__init__ at all — injected the same
        # way kimi's extra_body override is.
        gateway._providers["deepinfra"] = OpenAICompatibleProvider(  # noqa: SLF001
            name="deepinfra",
            base_url=base_url,
            model_name=resolved_model,
            api_key=api_key,
            max_tokens_floor=HARNESS_MAX_TOKENS_FLOOR,
        )

    active = gateway._active_provider_name()  # noqa: SLF001 — verifying the force took
    if active != name:
        raise SystemExit(
            f"llm_force_provider={name} did not take effect — active provider "
            f"resolved to {active!r}. Refusing to run: this would silently "
            f"score {active} under a {name} label."
        )
    served_model = getattr(gateway._providers[name], "_model_name", None)  # noqa: SLF001
    if served_model != resolved_model:
        raise SystemExit(
            f"forced provider {name!r} is serving model {served_model!r}, not "
            f"the requested {resolved_model!r} — refusing to run under a "
            "wrong-model label"
        )
    note = ", thinking disabled" if spec.extra_body else ""
    print(f"LLM gateway forced to: {active} ({base_url}, {resolved_model}{note}, "
          f"max_tokens floor {HARNESS_MAX_TOKENS_FLOOR})")
    return gateway


async def direct_call(
    provider: str,
    *,
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 5000,
) -> dict:
    """One OpenAI-shaped chat completion, NOT through LLMGateway — the replay
    path for a single captured prompt. Returns {"text": str|None, "usage":
    dict|None}; text may legitimately be None (vLLM null-content draws, hit
    live 2026-09-27) and is returned as-is rather than raised.
    """
    import httpx

    if provider not in PROVIDERS:
        raise SystemExit(
            f"unknown provider {provider!r} — valid: {', '.join(sorted(PROVIDERS))}"
        )
    spec = PROVIDERS[provider]
    if temperature is not None and not spec.supports_temperature:
        raise SystemExit(
            f"provider {provider!r} does not support temperature pinning "
            f"(valid here: {', '.join(n for n, s in PROVIDERS.items() if s.supports_temperature)})"
        )

    if provider == "kimi":
        api_key = env_bootstrap.require_kimi_open_platform_key()
        url = f"{spec.base_url}/v1/chat/completions"
        resolved_model = model or spec.default_model
        headers = {"Authorization": f"Bearer {api_key}"}
        extra = spec.extra_body or {}
    elif provider == "vllm":
        base_url = env_bootstrap.require_keys("VLLM_BASE_URL")["VLLM_BASE_URL"].rstrip("/")
        url = f"{base_url}/v1/chat/completions"
        resolved_model = model or os.environ.get("VLLM_MODEL", spec.default_model)
        headers = {}
        extra = {}
    else:  # deepinfra — the one place the /v1/openai suffix lives
        api_key = env_bootstrap.require_keys(spec.api_key_env)[spec.api_key_env]
        url = f"{spec.base_url}/v1/openai/chat/completions"
        resolved_model = model or spec.default_model
        headers = {"Authorization": f"Bearer {api_key}"}
        extra = {}

    body: dict[str, Any] = {
        "model": resolved_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "max_tokens": max_tokens,
        **extra,
    }
    if temperature is not None:
        body["temperature"] = temperature

    async with httpx.AsyncClient(timeout=_DIRECT_CALL_TIMEOUT_S) as client:
        resp = await client.post(url, headers=headers, json=body)
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or None
    if provider == "kimi":
        reasoning = (usage or {}).get("completion_tokens_details", {}).get("reasoning_tokens")
        if reasoning and reasoning > REASONING_TOKEN_TOLERANCE:
            raise RuntimeError(
                f"thinking not disabled: reasoning_tokens={reasoning} "
                f"(tolerance {REASONING_TOKEN_TOLERANCE})"
            )
    choices = data.get("choices") or []
    text = choices[0].get("message", {}).get("content") if choices else None
    return {"text": text, "usage": usage}
