"""CR281 — the LLM provider allow-list: which gateway slots an environment may use.

Why a setting and not "comment the key out": a commented-out key is not a
control. Uncommenting it, or copying an older env file over, silently re-enables
a vendor the operator excluded, and nothing reports it. `LLM_PROVIDER_ALLOWLIST`
makes the exclusion structural: when set, the gateway never registers a slot
outside the list, whatever keys or URLs are present, and boot logs every slot
that is configured but blocked (names only, never values).

Empty (the default) keeps the pre-CR281 behaviour exactly: every configured
provider is allowed. This module is pure — no I/O — so each rule is unit-testable
and `Settings` / `beta_boot` can call it at import time.
"""

from __future__ import annotations

from typing import Any, Iterable

# Every slot name the gateway can register, in registration order. `mock` is the
# always-present scripted provider: it needs no key, is never "configured", and
# is accepted in the list only so a copied list round-trips; it is not blocked
# by an allow-list (the existing "mock never silently serves real users" rules
# live elsewhere and are untouched).
KNOWN_SLOTS: tuple[str, ...] = (
    "vllm",
    "vllm_fallback",
    "anthropic",
    "kimi",
    "deepseek",
    "qwen",
    "glm",
    "gemini",
    "mock",
)

# slot -> the Settings attribute whose presence registers it.
_SLOT_CONFIG_SETTING: dict[str, str] = {
    "vllm": "vllm_base_url",
    "vllm_fallback": "vllm_fallback_base_url",
    "anthropic": "anthropic_api_key",
    "kimi": "kimi_api_key",
    "deepseek": "deepseek_api_key",
    "qwen": "dashscope_api_key",
    "glm": "glm_base_url",
    "gemini": "google_ai_api_key",
}

# Slots a Beta config must never allow (Saiful, 2026-11-19).
BETA_FORBIDDEN_SLOTS: tuple[str, ...] = ("anthropic", "kimi", "gemini")


def unknown_slots(names: Iterable[str]) -> list[str]:
    """Names in `names` that are not a gateway slot."""
    return [n for n in names if n not in KNOWN_SLOTS]


def normalize_allowlist(names: Iterable[str]) -> list[str]:
    """Lower-cased, stripped, de-duplicated (order kept), blanks dropped."""
    seen: list[str] = []
    for raw in names:
        n = str(raw).strip().lower()
        if n and n not in seen:
            seen.append(n)
    return seen


def configured_slots(s: Any) -> list[str]:
    """Slots whose key/URL is present in `s`, allowed or not."""
    return [
        slot
        for slot, attr in _SLOT_CONFIG_SETTING.items()
        if getattr(s, attr, "")
    ]


def slot_allowed(s: Any, slot: str) -> bool:
    """True when `slot` may be registered/used under `s`'s allow-list."""
    allow = getattr(s, "llm_provider_allowlist", None) or []
    return not allow or slot in allow


def blocked_slots(s: Any) -> list[str]:
    """Configured-but-not-allowed slots (empty when no allow-list is set)."""
    return [slot for slot in configured_slots(s) if not slot_allowed(s, slot)]
