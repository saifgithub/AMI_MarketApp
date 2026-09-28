"""Single-agent prompt replay (DESIGN.md §4.5): run one exact captured prompt
(system_prompt + messages) N times against a provider and report the answer
distribution — the instrument for "is this agent noisy on THIS input?".

Replaces v1 `docs/tools/room_investigation/room_agent_replay.py`: v1's three
duplicated HTTP call bodies (`_call_kimi` / `_call_vllm` / `_call_deepinfra`)
are now `provider_gateway.direct_call()` on the shared PROVIDERS registry, and
v1's `_extract` is now `scoring.extract_decision()` — this module keeps only
the repeat loop, the draw record schema, and the distribution/token rollup.

Use this BEFORE concluding an agent itself is unstable: v1's BAC replay showed
5/5 stable draws per fixed input — the divergence lived upstream, not in the
agent.
"""
from __future__ import annotations

import os
from collections import Counter

try:
    from library import provider_gateway, scoring
except ImportError:
    import provider_gateway
    import scoring


async def replay_prompt(
    provider: str,
    *,
    system_prompt: str,
    messages: list[dict],
    repeats: int = 5,
    extract_pattern: str | None = None,
    extract_json_key: str | None = None,
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int = 5000,
    label: str = "",
) -> dict:
    """Replay one captured prompt `repeats` times, sequentially.

    Sequential by design: sampling draws must not race a provider rate
    limiter, or throttling becomes part of what's measured. A failed draw
    (transport error, thinking-not-disabled refusal) is recorded with
    error=repr(exc)[:300] and the loop continues — one bad draw must not lose
    the other N-1. A null-content completion (text=None) is a legitimate draw,
    recorded with extracted=None, not an error.

    Raises ValueError on an unknown provider, or when `temperature` is given
    for a provider whose spec says supports_temperature=False — direct_call()
    raises SystemExit for both, which a library must not do to its caller, so
    the checks live here against the same PROVIDERS registry.
    """
    if provider not in provider_gateway.PROVIDERS:
        raise ValueError(
            f"unknown provider {provider!r} — valid: "
            f"{', '.join(sorted(provider_gateway.PROVIDERS))}"
        )
    spec = provider_gateway.PROVIDERS[provider]
    if temperature is not None and not spec.supports_temperature:
        raise ValueError(
            f"provider {provider!r} does not support temperature pinning "
            f"(valid here: {', '.join(n for n, s in provider_gateway.PROVIDERS.items() if s.supports_temperature)})"
        )

    resolved_model = model or (
        os.environ.get("VLLM_MODEL", spec.default_model)
        if provider == "vllm"
        else spec.default_model
    )

    draws = []
    for i in range(1, repeats + 1):
        try:
            out = await provider_gateway.direct_call(
                provider,
                system_prompt=system_prompt,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            draws.append({
                "draw": i,
                "extracted": None,
                "full_text": None,
                "usage": None,
                "error": repr(exc)[:300],
            })
            continue
        text = out["text"]
        draws.append({
            "draw": i,
            "extracted": scoring.extract_decision(
                text, pattern=extract_pattern, json_key=extract_json_key
            ),
            "full_text": text,
            "usage": out["usage"],
            "error": None,
        })

    dist = Counter("None" if d["extracted"] is None else d["extracted"] for d in draws)

    total_in = 0
    total_out = 0
    total_reasoning: int | None = None
    for d in draws:
        usage = d["usage"] or {}
        total_in += usage.get("prompt_tokens") or 0
        total_out += usage.get("completion_tokens") or 0
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        if reasoning:
            total_reasoning = (total_reasoning or 0) + reasoning

    return {
        "label": label,
        "provider": provider,
        "model": resolved_model,
        "repeats": repeats,
        "temperature": temperature,
        "draws": draws,
        "distribution": dict(dist),
        "total_tokens": {
            "input": total_in,
            "output": total_out,
            "reasoning": total_reasoning,
        },
    }
