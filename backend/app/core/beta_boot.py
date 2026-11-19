"""CR279 (CR267 WP-41) — the boot-time refusals that apply only when `ENV=beta`.

Beta is the first environment real testers use, and its LLM posture is a
ruling, not a preference (Saiful, 2026-11-18/19): hosted open-weight models
only, no on-prem or LAN address, no Anthropic / Kimi / Gemini key, a daily
spend ceiling that is actually on, the 18+ gate enforced, a real SECRET_KEY.
Each of those is a place where a config slip would degrade silently — an
on-prem address would reach nothing from the Beta host and leave Rooms
failing; an unset ceiling would leave spend unbounded; a leftover Anthropic
key would quietly route a tester's data to a vendor Saiful excluded. So they
are refused at boot, by name, rather than documented (CLAUDE.md: prompt and
prose instructions are not controls).

`beta_boot_problems` is pure (no I/O, no DNS) so every rule is unit-testable;
`Settings` calls it from a model validator, which makes a bad Beta config fail
at import of `app.core.config`, i.e. before the app serves anything. The
`account_erasure_mode=archive` rule already exists on `Settings` for every env
(CR276) and is not duplicated here.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

# Mirrors app/main.py::check_secret_key_boot, which runs for every non-local env.
_SECRET_KEY_DEV_DEFAULT = "dev-secret-change-in-prod"
_SECRET_KEY_MIN_LEN = 32

# Hostname suffixes that only resolve inside a private network or a tailnet.
_PRIVATE_HOST_SUFFIXES = (".local", ".lan", ".internal", ".home", ".corp", ".ts.net")

# LLM base-URL settings that must never be private on Beta. `glm_base_url` is
# the self-hosted GLM slot (a Tailscale host today).
_LLM_URL_SETTINGS = ("vllm_base_url", "vllm_fallback_base_url", "glm_base_url")

# Vendor keys excluded from the app by ruling (2026-11-19).
_FORBIDDEN_KEY_SETTINGS = ("anthropic_api_key", "kimi_api_key", "google_ai_api_key")


def is_private_llm_host(url: str) -> bool:
    """True when `url` points at a LAN, loopback, link-local, CGNAT/Tailscale
    (100.64.0.0/10) or otherwise non-public host.

    Anything that does not parse to a host is treated as private: a base URL we
    cannot read is not one we can vouch for. Hostnames are not resolved (a boot
    check must not depend on DNS); instead bare single-label names (a compose
    service, `localhost`, `host.docker.internal`) and private-network suffixes
    are refused, and a literal IP is judged by `ipaddress`.
    """
    text = (url or "").strip()
    if "://" not in text:
        text = "//" + text
    try:
        host = urlparse(text).hostname
    except ValueError:
        return True
    if not host:
        return True
    host = host.rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or host == "localhost" or host.startswith("host.docker."):
            return True
        return host.endswith(_PRIVATE_HOST_SUFFIXES)
    return not ip.is_global


def beta_boot_problems(s: Any) -> list[str]:
    """Every reason `s` (a `Settings`) may not boot as `ENV=beta`; [] if none.

    Each message names the offending setting in its env-var spelling.
    """
    from app.core.config import parse_llm_prices

    problems: list[str] = []

    for name in _LLM_URL_SETTINGS:
        value = getattr(s, name, "")
        if value and is_private_llm_host(value):
            problems.append(
                f"{name.upper()} points at a private/on-prem address ({value!r}): Beta "
                "uses hosted LLMs only (CR267 §3a). Remove it or use a public https endpoint."
            )

    if not s.vllm_base_url:
        problems.append(
            "VLLM_BASE_URL is empty: Beta's primary model is the hosted DeepInfra model "
            "served through the vllm slot. Empty would boot on the mock provider."
        )

    for name in _FORBIDDEN_KEY_SETTINGS:
        if getattr(s, name, ""):
            problems.append(
                f"{name.upper()} is set: Beta runs with no Anthropic, Kimi or Gemini keys "
                "(Saiful, 2026-11-19). Unset it."
            )

    ceiling = s.llm_daily_spend_ceiling_usd
    if ceiling is None or ceiling <= 0:
        problems.append(
            "LLM_DAILY_SPEND_CEILING_USD is unset or 0: Beta must run with the daily "
            "spend ceiling on (CR270). Set a positive USD figure."
        )

    if not s.onboarding_age_gate_enforced:
        problems.append(
            "ONBOARDING_AGE_GATE_ENFORCED is false: Beta must refuse onboarding without "
            "the 18+ confirmation (CR273)."
        )

    if not s.sentry_dsn.strip():
        problems.append(
            "SENTRY_DSN is empty: Beta must report backend errors (CR267 WP-44). An empty "
            "DSN makes `init_sentry` a silent no-op and every crash goes unseen."
        )

    key = s.secret_key
    if key == _SECRET_KEY_DEV_DEFAULT or len(key) < _SECRET_KEY_MIN_LEN:
        problems.append(
            "SECRET_KEY is the dev default or shorter than "
            f"{_SECRET_KEY_MIN_LEN} characters: generate a fresh one with `openssl rand -hex 32`."
        )

    # With a ceiling on, a model absent from the price table makes the ceiling
    # fail CLOSED (CR270) — every Room would be refused as "temporarily
    # unavailable". Catch it at boot instead of at the first tester's Room.
    if ceiling is not None and ceiling > 0:
        prices = parse_llm_prices(s.llm_prices_json)
        served = [("VLLM_MODEL", s.vllm_model)]
        if s.vllm_fallback_base_url:
            served.append(("VLLM_FALLBACK_MODEL", s.vllm_fallback_model))
        for name, model in served:
            if model not in prices:
                problems.append(
                    f"{name}={model!r} has no entry in LLM_PRICES_JSON: with the spend "
                    "ceiling on, an unpriced model fails the ceiling closed and refuses every Room."
                )

    return problems
