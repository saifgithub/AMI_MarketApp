#!/usr/bin/env python3
"""Shared core for running the Room (RoomRunner) against Kimi, vLLM, OR
DeepInfra, in-process, on the Mac — extracted from CR228/RES009's
`run_local_kimi*.py` family (2026-09, CR228 risk-appetite benchmark
cross-check). Every other script in this directory imports from here rather
than re-copying this logic. Despite the filename (kept for git-history
continuity — this module started Kimi-only), `force_vllm_gateway()` and
`force_deepinfra_gateway()` are the vLLM/DeepInfra counterparts to
`force_kimi_gateway()`, and every CLI script in this toolkit takes
`--provider {kimi,vllm,deepinfra}` via the shared `force_gateway()` dispatch.

## Why this exists

`LLM_FORCE_PROVIDER` is a process-global env var read once at `Settings()`
construction (backend/app/core/config.py) and consulted by every LLM call in
that process. Setting it on melehost's shared `ami_api_alpha` container would
redirect ALL live users' Room/Coach/Brief/Concierge traffic to Kimi for the
whole run, not just a benchmark's calls (confirmed live — no per-request or
per-user provider override exists anywhere in the stack; CR035's arms B/C
took this hit and call it out explicitly). This module runs `RoomRunner.run()`
directly, in a throwaway Python process on the Mac, with its own `LLMGateway`
instance forced to Kimi FOR THIS PROCESS ONLY (`Settings` is a per-process
singleton) — melehost's process, and any real user traffic on it, is never
touched.

## Which Kimi, and why (RES009 05_kimi_cross_check.md has the full story)

Two separate Kimi products, two separate key scopes:
- Kimi Coding Plan (`api.kimi.com/coding`, key prefix `sk-kimi-…`) — melehost's
  existing key, wired for Saiful's own coding-assistant use. NEVER reuse this
  for benchmark/research traffic.
- Moonshot Open Platform (`api.moonshot.ai`, key prefix `sk-ZJutc…` on the
  Mac's `.env`) — the key this module uses. `kimi-k3` is the one Open
  Platform model that genuinely zeroes reasoning tokens when thinking is
  disabled (`kimi-k2.7-code*` 400s on this key's namespace; `kimi-k2.6`
  leaves a ~1-token residual — see RES009 for the live-tested evidence).

## Disabling reasoning/thinking

Moonshot's OpenAI-compatible endpoint does NOT honor the OpenAI/Qwen-style
`enable_thinking` flag already used elsewhere in this codebase for Qwen
(`llm_gateway.py`, `extra_body={"enable_thinking": False}`). Four candidate
request-body shapes were tested live (RES009 05); only one works:
    {"no_thinking": true}              -> 200 OK, reasoning_tokens still nonzero (ignored)
    {"enable_thinking": false}         -> 200 OK, reasoning_tokens still nonzero (ignored)
    {"thinking": false}                -> 400 Bad Request
    {"thinking": {"type": "disabled"}} -> 200 OK, reasoning_tokens: None (works)
Reasoning-enabled Kimi calls run ~1-3min each (~18min/ticker full convene);
thinking-disabled calls run ~3-6min per FULL 30-ticker convene (~5-6min/call
average across the whole 12-agent pipeline) — roughly a 3-4x speedup, and
critically avoids blowing the Room's vLLM-tuned `room_agent_timeout_s`
default (180s), which reasoning-enabled Kimi calls repeatedly did.

## Usage pattern

    from room_kimi_gateway import force_kimi_gateway, run_one_ticker, base_mandate

    gateway = force_kimi_gateway()
    runner = RoomRunner(llm=gateway)
    mandate = resolve_mandate(user_id, base_mandate(risk_score=3))
    result = await run_one_ticker(runner, user_id, "AAPL", mandate)

Requires (exported before running):
    KIMI_API_KEY   — the Mac's Open Platform key, NOT melehost's Coding Plan key
    DATABASE_URL   — melehost's Postgres, via SSH tunnel (see room_db_tunnel.md)
    Run from backend/ with backend/.venv/bin/python3 (already has app deps).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

KIMI_OPEN_PLATFORM_BASE_URL = "https://api.moonshot.ai"
KIMI_OPEN_PLATFORM_MODEL = "kimi-k3"
KIMI_EXTRA_BODY = {"thinking": {"type": "disabled"}}

# CR240 — DeepInfra's OpenAI-compatible endpoint. `OpenAICompatibleProvider`
# (llm_gateway.py) always POSTs to "{base_url}/v1/chat/completions", so this
# must be the bare host — NOT "https://api.deepinfra.com/v1/openai" (that
# shape is what room_agent_replay.py's standalone `_call_deepinfra` uses,
# which builds its own "{base}/chat/completions" path instead; the two
# tools' base URLs are deliberately NOT the same string, since they append
# different suffixes — confirmed live: DeepInfra 404'd every Room agent call
# under the OpenAICompatibleProvider path when this constant carried the
# "/v1/openai" suffix, since the request landed on
# ".../v1/openai/v1/chat/completions", a route that doesn't exist).
DEEPINFRA_BASE_URL = "https://api.deepinfra.com"
DEEPINFRA_DEFAULT_MODEL = "zai-org/GLM-5.3-Flash"

# vLLM's tuned default (room_agent_timeout_s config default, 180s) starves
# Kimi even with thinking disabled some of the time — this internet-path,
# different-provider margin is deliberate, not copied blindly from vLLM's
# LAN-tuned figure.
DEFAULT_AGENT_TIMEOUT_S = 300.0


def base_mandate(*, risk_score: int, display_name: str | None = None) -> dict[str, Any]:
    """CR228's own mandate shape: risk_score, drawdown_response, and
    concentration_tolerance all track the same arm value (matches
    run_pilot.sh's base_mandate() and room_benchmark.py's
    NEUTRAL_MANDATE_OVERRIDE, both risk_score=3 by default) —
    max_drawdown_pct pinned at 30 regardless of risk_score.
    """
    return {
        "display_name": display_name or f"Room investigation R{risk_score} (Kimi)",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": "long_horizon",
        "risk_score": risk_score,
        "drawdown_response": risk_score,
        "regret_asymmetry": 0,
        "concentration_tolerance": risk_score,
        "max_drawdown_pct": 30,
        "compliance": {},
    }


def force_kimi_gateway():
    """Build an LLMGateway resolving to Kimi (Moonshot Open Platform,
    thinking disabled) for every call, in THIS PROCESS ONLY.

    LLMGateway.__init__'s own Kimi-registration branch (llm_gateway.py,
    ~line 1024) does not accept an extra_body override — that constructor
    param only reaches the gateway's Qwen branch today. Rather than fork
    LLMGateway's registration logic, this builds the gateway normally (every
    other provider registers exactly as production would) then replaces just
    the "kimi" entry with a manually-constructed OpenAICompatibleProvider
    that adds extra_body=KIMI_EXTRA_BODY — same base_url/model/api_key/
    max_tokens_floor the gateway would have used, so CR130's reasoning-token
    headroom fix (kimi_max_tokens_floor) stays in effect even with thinking
    disabled.
    """
    from app.core.config import settings
    from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider

    if not settings.kimi_api_key:
        raise SystemExit(
            "KIMI_API_KEY not set (needs the Mac's Open Platform key, not "
            "melehost's Coding Plan key) — refusing to run with Kimi "
            "unregistered, which would silently fall through to vLLM"
        )
    settings.llm_force_provider = "kimi"
    settings.kimi_base_url = KIMI_OPEN_PLATFORM_BASE_URL
    settings.kimi_model = KIMI_OPEN_PLATFORM_MODEL
    gateway = LLMGateway()
    gateway._providers["kimi"] = OpenAICompatibleProvider(  # noqa: SLF001 — see docstring
        name="kimi",
        base_url=KIMI_OPEN_PLATFORM_BASE_URL,
        model_name=KIMI_OPEN_PLATFORM_MODEL,
        api_key=settings.kimi_api_key,
        max_tokens_floor=settings.kimi_max_tokens_floor,
        extra_body=KIMI_EXTRA_BODY,
    )
    active = gateway._active_provider_name()  # noqa: SLF001 — verifying the force actually took
    if active != "kimi":
        raise SystemExit(
            f"LLM_FORCE_PROVIDER=kimi did not take effect — active provider "
            f"resolved to {active!r} instead. Refusing to run: this would "
            f"silently score vLLM against itself under a Kimi label."
        )
    print(f"LLM gateway forced to: {active} ({KIMI_OPEN_PLATFORM_BASE_URL}, "
          f"{KIMI_OPEN_PLATFORM_MODEL}, thinking disabled)")
    return gateway


async def run_one_ticker(
    runner,
    user_id: UUID,
    ticker: str,
    mandate,
    *,
    agent_timeout_s: float = DEFAULT_AGENT_TIMEOUT_S,
) -> dict[str, Any]:
    """Drive one real Room convene via RoomRunner.run(), return a
    room_benchmark.py-shaped result dict (verdict, model_tier, duration_ms,
    status) — the JSONL record needs only batch/ticker bookkeeping added by
    the caller on top of this.
    """
    run_id = uuid4()
    started = time.monotonic()
    verdict = None
    model_tier = None
    status = "completed"
    error_message = None
    try:
        async for ev in runner.run(
            run_id=run_id, user_id=user_id, ticker=ticker, mandate=mandate,
            agent_timeout_s=agent_timeout_s,
        ):
            if ev.kind == "verdict" and ev.verdict is not None:
                verdict = ev.verdict.model_dump() if hasattr(ev.verdict, "model_dump") else ev.verdict
            if getattr(ev, "phase", None) and model_tier is None:
                pass  # RoomEvent doesn't carry model_tier directly; left None, matching room_benchmark.py
        if verdict is None:
            status = "no_verdict"
    except Exception as exc:  # noqa: BLE001 — record and continue the batch
        status = "script_error"
        error_message = repr(exc)[:300]
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "run_id": str(run_id),
        "cached": False,
        "status": status,
        "verdict": verdict,
        "model_tier": model_tier,
        "duration_ms": duration_ms,
        "error_message": error_message,
    }


def snapshot_price(ticker: str) -> float | None:
    try:
        import yfinance as yf
        price = yf.Ticker(ticker).fast_info["last_price"]
        return round(float(price), 4) if price else None
    except Exception:  # noqa: BLE001 — a spot-price miss must not sink the run
        return None


def force_vllm_gateway(*, temperature: float | None = None):
    """Build an LLMGateway resolving to vLLM for every call, in THIS PROCESS
    ONLY. Unlike Kimi, vLLM registers correctly from `settings.vllm_base_url`/
    `vllm_model` already — no base-url/model override, no thinking-disable,
    no provider-surgery needed. Requires the Mac to reach vLLM LAN-direct
    (`VLLM_BASE_URL=http://192.168.20.74:8000` — see feedback_lan_route.md;
    this only works from the office LAN, not from a remote/cloud sandbox).

    `temperature` is NOT plumbed through `LLMGateway`/`RoomRunner` — nothing
    in this codebase pins temperature anywhere (RES009 01-06: this is a
    deliberate finding, not an oversight — every provider call runs at
    whatever the server's own default is). To test at a pinned temperature,
    use `room_agent_replay.py --provider vllm --temperature X` instead, which
    calls vLLM directly rather than through RoomRunner/LLMGateway.
    """
    from app.core.config import settings
    from app.services.llm_gateway import LLMGateway

    if temperature is not None:
        raise SystemExit(
            "temperature is not supported through RoomRunner/LLMGateway — "
            "use room_agent_replay.py --provider vllm --temperature X for a "
            "single-agent, pinned-temperature test instead"
        )
    if not settings.vllm_base_url:
        raise SystemExit(
            "VLLM_BASE_URL not set — export it (e.g. http://192.168.20.74:8000, "
            "LAN-direct from the Mac) before running against vLLM"
        )
    settings.llm_force_provider = "vllm"
    gateway = LLMGateway()
    active = gateway._active_provider_name()  # noqa: SLF001 — verifying the force actually took
    if active != "vllm":
        raise SystemExit(
            f"LLM_FORCE_PROVIDER=vllm did not take effect — active provider "
            f"resolved to {active!r} instead. Refusing to run: this would "
            f"silently score the wrong provider under a vLLM label."
        )
    print(f"LLM gateway forced to: {active} ({settings.vllm_base_url}, {settings.vllm_model})")
    return gateway


def force_deepinfra_gateway(*, model: str = DEEPINFRA_DEFAULT_MODEL):
    """Build an LLMGateway resolving to DeepInfra for every call, in THIS
    PROCESS ONLY. CR240 (hosted-provider evaluation for production) — this
    is the full-Room counterpart to `room_agent_replay.py --provider
    deepinfra`'s single-agent replay; same endpoint/model, but driven
    through RoomRunner so every one of the 12 agents in a convene actually
    calls DeepInfra, not just one captured prompt replayed in isolation.

    Not registered in LLMGateway.__init__ at all (unlike vLLM/Kimi, which
    have dedicated branches there) — DeepInfra is injected the same way
    Kimi's extra_body override is: build the gateway normally, then add a
    manually-constructed OpenAICompatibleProvider entry and force selection
    onto it via `settings.llm_force_provider`.
    """
    import os

    from app.core.config import settings
    from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider

    api_key = os.environ.get("DEEPINFR_API_KEY")  # codebase's own spelling, see .env — no trailing A
    if not api_key:
        raise SystemExit(
            "DEEPINFR_API_KEY not set — refusing to run with DeepInfra "
            "unregistered, which would silently fall through to vLLM"
        )
    settings.llm_force_provider = "deepinfra"
    gateway = LLMGateway()
    gateway._providers["deepinfra"] = OpenAICompatibleProvider(  # noqa: SLF001 — see docstring
        name="deepinfra",
        base_url=DEEPINFRA_BASE_URL,
        model_name=model,
        api_key=api_key,
    )
    active = gateway._active_provider_name()  # noqa: SLF001 — verifying the force actually took
    if active != "deepinfra":
        raise SystemExit(
            f"LLM_FORCE_PROVIDER=deepinfra did not take effect — active "
            f"provider resolved to {active!r} instead. Refusing to run: this "
            f"would silently score vLLM against itself under a DeepInfra label."
        )
    print(f"LLM gateway forced to: {active} ({DEEPINFRA_BASE_URL}, {model})")
    return gateway


def force_gateway(provider: str, **kwargs):
    """Dispatch to force_kimi_gateway() / force_vllm_gateway() /
    force_deepinfra_gateway() by name — the single entry point every CLI
    script in this toolkit should call.
    """
    if provider == "kimi":
        return force_kimi_gateway()
    if provider == "vllm":
        return force_vllm_gateway(**kwargs)
    if provider == "deepinfra":
        return force_deepinfra_gateway(**kwargs)
    raise SystemExit(f"unknown provider {provider!r} — expected 'kimi', 'vllm', or 'deepinfra'")
