"""LLM gateway — provider-agnostic interface for the rest of the backend.

The gateway picks a provider at runtime based on:
  - which API keys are configured in settings
  - the requested model tier (cheap / mid / premium)
  - the user's locale (Arabic prefers Gemini; we'll wire that when Google client added)

Providers implemented:
  - MockProvider     → returns canned responses; used when no real key is set.
                       Lets the full UX work without API keys configured.
  - AnthropicProvider → direct Anthropic API. Supports streaming.
  - OpenAICompatibleProvider → any OpenAI-chat-completions-compatible endpoint
                       (CR017). VLLMProvider is a thin subclass of this;
                       KimiProvider instances register the same way.

Coming later (W4+):
  - GoogleProvider, OpenRouterProvider, DeepSeek/Qwen (CR017 §3 — same
    OpenAICompatibleProvider class, just a new registration block each)

See docs/initial_specs/08_tech/llm_routing.md for the routing strategy.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.logging import logger


ModelTier = Literal["cheap", "mid", "premium"]


# ── Model selection per tier (configurable) ──────────────────────────────
#
# Model IDs are the dated aliases supported by Anthropic's Messages API.
# When Anthropic rotates a snapshot, only this map needs to change.

TIER_TO_MODEL: dict[ModelTier, str] = {
    "cheap": "claude-haiku-4-5",
    "mid": "claude-sonnet-4-6",
    "premium": "claude-opus-4-7",
}

# Per-(plan, agent) tier routing lives in app.services.tier_policy.pick_tier.
# This module owns the tier→model alias map only.


# ── Message + result types ───────────────────────────────────────────────


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


# ── CR056: universal grounding directive (no assumed data) ───────────────
#
# Prepended to the system prompt of EVERY call routed through
# LLMGateway.stream_chat — the single chokepoint all 12 Room agents, the
# Concierge, and the PM verdict reformatter pass through, and where the prompt
# is recorded to llm_audit. Defence-in-depth for the phantom-data class: a model
# filling a silent gap with an invented holding, price, date, or prior event
# (the SCHD incident behind CR055). This is a SOFT control — prompt instructions
# are ~30% effective (CR038 / failure_patterns P2/P4), NOT a substitute for the
# structural data-supply fix (CR055 supplies the holdings the model was missing).
#
# Two invariants the wording + placement must hold, or the suite breaks:
#   1. The preamble contains NONE of the agent-id tokens the MockProvider routes
#      on (it branches on system_prompt.lower(); a stray "trader" / "market
#      analyst" / … would mis-route the mock to the wrong canned reply).
#   2. PREPEND only. The Portfolio Manager's safety floor must remain the LAST
#      instruction (recency dominance, safety_floor.py); appending would displace
#      it. Prepending frames the top and leaves the floor untouched at the tail.

GROUNDING_DIRECTIVE_SENTINEL = "─── GROUNDING DIRECTIVE (applies to every response) ───"

GROUNDING_DIRECTIVE = (
    f"{GROUNDING_DIRECTIVE_SENTINEL}\n"
    "Use only the facts and numbers explicitly provided in this prompt. Do not "
    "assume, infer, invent, or recall any datum you were not given — such as "
    "holdings, positions, prices, balances, ratios, dates, or prior events. If a "
    "fact you need is absent, say it is unavailable or omit the claim; never fill "
    "the gap with an assumption.\n\n"
)


def prepend_grounding_directive(system_prompt: str) -> str:
    """Prepend the universal no-assumed-data directive to a system prompt, once.

    Idempotent: if the sentinel is already present (re-entry, or a caller that
    pre-framed the prompt), the prompt is returned unchanged so the directive is
    never stacked. Prepend-only, so a trailing block (e.g. the PM safety floor)
    stays last.
    """
    if GROUNDING_DIRECTIVE_SENTINEL in system_prompt:
        return system_prompt
    return GROUNDING_DIRECTIVE + system_prompt


# ── Provider interface ───────────────────────────────────────────────────


class LLMProvider:
    name: str = "base"

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield content chunks as they arrive from the provider.

        DEF125: [meta] is a per-call, caller-owned dict the provider writes the
        terminal `finish_reason` into (normalised across providers: `"length"`
        when the model was cut off at `max_tokens`, `"stop"` on a natural end).
        A dict rather than a return value because the contract is a generator —
        and per-call rather than provider state because providers are shared
        singletons serving concurrent runs, so an attribute would race.
        """
        raise NotImplementedError


# ── Mock provider — used when no real key is configured ──────────────────


class MockProvider(LLMProvider):
    """Returns a canned, agent-aware response without hitting any real API.

    Used during dev when keys aren't configured. The response varies based on
    the system prompt content so different agents feel different.
    """

    name = "mock"

    _CANNED = {
        "fundamentals_analyst": (
            "AMI's Fundamentals Analyst here, but I'm offline right now. Without a live "
            "connection I can't run a real evaluation; the framework would be:\n\n"
            "• Pull last 4 quarters of income statement, balance sheet, cash flow\n"
            "• Compute trailing P/E, EV/EBITDA, FCF yield vs sector median\n"
            "• Check debt-to-equity and interest coverage\n"
            "• Compare against the 3 nearest peers\n\n"
            "Once AMI is back online, I'll do the actual numbers."
        ),
        "market_analyst": (
            "AMI's Market Analyst, currently offline. The chart would show me trend, "
            "momentum, and key levels. When live, I'd give you specific entries, "
            "targets, and stops.\n\n"
            "AMI is in fallback mode — check back in a moment."
        ),
        "bear_researcher": (
            "AMI's Bear here, but I'm offline. My real job is to find what's wrong with "
            "the thesis: identify the 2-3 risks that materially matter, quantify them, "
            "and address how the Bull would respond.\n\n"
            "AMI is in fallback mode."
        ),
        "bull_researcher": (
            "AMI's Bull here, offline at the moment. My real job is to steelman the long "
            "case: thesis in one sentence, cite the Analysts' evidence, anticipate the "
            "Bear's counter, propose sizing.\n\n"
            "AMI is in fallback mode."
        ),
        "trader": (
            "AMI's Trader, currently offline. Once we have live data I'll give you: "
            "instrument, side, size, entry, target, stop, time horizon — all sized to "
            "your mandate.\n\n"
            "AMI is in fallback mode."
        ),
        "portfolio_manager": (
            "AMI's PM here, offline. My role is to gatekeep — every trade goes through "
            "a compliance check (deterministic) and a judgment review (AMI, once "
            "online).\n\n"
            "AMI is in fallback mode for the judgment side; the compliance check still "
            "runs."
        ),
        "concierge": (
            "AMI's Concierge here! I'm in fallback mode right now — I'd normally route "
            "you to the right lesson, search your journal, or schedule briefings.\n\n"
            "Onboarding works fully (no AI needed), and you can browse lessons. Want me "
            "to find one for you?"
        ),
    }

    _DEFAULT = (
        "AMI is in fallback mode — the backend isn't connected to a live model right "
        "now. Once AMI is back online, I'll respond properly to your question."
    )

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        # Pick canned response based on which agent's prompt this is
        text = self._DEFAULT
        sp = system_prompt.lower()
        for key, response in self._CANNED.items():
            if f"agent_id: {key}" in sp or key.replace("_", " ") in sp:
                text = response
                break

        # Stream char-by-char so the UI sees the typewriter effect
        for char in text:
            yield char
            # Small jitter so it feels organic
            await asyncio.sleep(random.uniform(0.005, 0.020))


# ── Anthropic provider ───────────────────────────────────────────────────


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=60.0,
        )

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        model = TIER_TO_MODEL[model_tier]
        # Anthropic separates `system` from `messages`; user/assistant only in messages
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "system": system_prompt,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        async with self._client.stream("POST", "/v1/messages", json=body) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                logger.error(
                    "anthropic_error",
                    status=resp.status_code,
                    body=err_body.decode()[:500],
                )
                yield (
                    f"\n\n[AMI error: HTTP {resp.status_code} from the upstream provider. "
                    "Falling back. Check backend logs.]"
                )
                return

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: ") :].strip()
                if data == "[DONE]":
                    return
                # Anthropic SSE chunks are JSON like:
                # {"type":"content_block_delta","delta":{"type":"text_delta","text":"…"}}
                try:
                    import json

                    obj = json.loads(data)
                    if obj.get("type") == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                    elif obj.get("type") == "message_delta" and meta is not None:
                        # DEF125: Anthropic reports the terminal stop on
                        # `message_delta.delta.stop_reason`. Normalise its
                        # `max_tokens` to the OpenAI/vLLM vocabulary so callers
                        # test one value regardless of which provider served.
                        stop = ((obj.get("delta") or {}).get("stop_reason"))
                        if stop:
                            meta["finish_reason"] = (
                                "length" if stop == "max_tokens" else str(stop)
                            )
                except Exception as e:
                    logger.warn("anthropic_chunk_parse_failed", error=str(e), line=line[:200])

    async def aclose(self) -> None:
        await self._client.aclose()


# ── OpenAI-compatible provider (vLLM, Kimi, and any future chat-completions
#    endpoint — CR017) ────────────────────────────────────────────────────


class OpenAICompatibleProvider(LLMProvider):
    """Streams completions from any OpenAI `/v1/chat/completions`-shaped API.

    CR017: our on-prem vLLM server, Moonshot's Kimi API, and (later)
    DeepSeek/Qwen/Gemini's OpenAI-compat endpoints all speak the same
    request/response shape — the only bespoke logic anywhere is the SSE
    parser (`choices[0].delta.content` instead of Anthropic's
    `content_block_delta`) and the system-prompt placement (OpenAI-style
    puts `system` inside `messages`, not as a sibling field). So this is
    ONE class, instantiated once per provider with a different
    name/base_url/model/key — not a new class per provider.

    Tier mapping: each instance serves a single model, so all tiers
    resolve to the same `model_name`. The per-(plan, agent) tier policy
    in `tier_policy.py` still picks a tier — this class just ignores the
    distinction. `extra_body` exists for provider-specific request-body
    quirks (e.g. Qwen's `enable_thinking`, CR017 §3) — unused today.
    """

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model_name: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._model_name = model_name
        self._extra_body = extra_body or {}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
        )

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        # OpenAI-style puts the system message as the first entry of `messages`.
        openai_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        for m in messages:
            openai_messages.append({"role": m.role, "content": m.content})

        body = {
            "model": self._model_name,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
            **self._extra_body,
        }

        async with self._client.stream("POST", "/v1/chat/completions", json=body) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                logger.error(
                    f"{self.name}_error",
                    status=resp.status_code,
                    body=err_body.decode()[:500],
                )
                yield (
                    f"\n\n[AMI error: HTTP {resp.status_code} from the upstream provider "
                    f"({self.name}). Check backend logs.]"
                )
                return

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: ") :].strip()
                if data == "[DONE]":
                    return
                try:
                    import json

                    obj = json.loads(data)
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    # DEF125: the terminal `finish_reason` arrives on the
                    # final chunk, whose delta is empty — read it BEFORE the
                    # `content` guard, which would otherwise `continue`
                    # straight past it.
                    if meta is not None:
                        finish = choices[0].get("finish_reason")
                        if finish:
                            meta["finish_reason"] = str(finish)
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception as e:
                    logger.warn(
                        f"{self.name}_chunk_parse_failed", error=str(e), line=line[:200]
                    )

    async def aclose(self) -> None:
        await self._client.aclose()


class VLLMProvider(OpenAICompatibleProvider):
    """Thin subclass, not a plain alias — CR077's `check_prefix_cache_at_startup`
    identifies "the vLLM instance" by `isinstance(provider, VLLMProvider)` to
    call the vLLM-only `/metrics` endpoint below. A bare `OpenAICompatibleProvider`
    instance (e.g. Kimi) must NOT satisfy that isinstance check, or startup would
    try to scrape a hosted API's `/metrics` path that doesn't exist.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            name="vllm",
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    async def log_prefix_cache_status(self) -> None:
        """CR077 Phase 0 second guard.

        The whole-lesson-catalogue reorder in `concierge_prompts.py` depends
        on this host's prefix cache actually being on — CR077 measured it
        sitting at 0% hit on the Concierge prompt for months with nobody
        noticing, purely because of where the static block sat. Log the
        measured hit rate at startup and warn loudly if the server reports
        `enable_prefix_caching` off, so a second silent regression like that
        shows up in the logs instead of just costing 2+ seconds a message.
        Best-effort: an unreachable `/metrics` logs a warning, not a crash —
        this is instrumentation, not a request-path dependency.
        """
        try:
            resp = await self._client.get("/metrics", timeout=5.0)
            resp.raise_for_status()
            text = resp.text
        except Exception as exc:
            logger.warn("vllm_prefix_cache_check_failed", error=str(exc))
            return

        enabled = 'enable_prefix_caching="True"' in text
        hits = _sum_prometheus_metric(text, "vllm:prefix_cache_hits_total")
        queries = _sum_prometheus_metric(text, "vllm:prefix_cache_queries_total")
        hit_rate = (hits / queries) if queries else None
        logger.info(
            "vllm_prefix_cache_status",
            enable_prefix_caching=enabled,
            hits_total=hits,
            queries_total=queries,
            hit_rate=hit_rate,
        )
        if not enabled:
            logger.warn(
                "vllm_prefix_caching_disabled",
                detail=(
                    "enable_prefix_caching not reported True by /metrics — the "
                    "CR077 Concierge static-head reorder is silently getting "
                    "zero benefit from this"
                ),
            )


def _sum_prometheus_metric(text: str, metric_name: str) -> float:
    """Sum every labelled sample of a Prometheus counter/gauge by name.

    A metric can have multiple label combinations (e.g. per engine); the
    startup check wants the total across all of them, not any one line.
    """
    total = 0.0
    prefix = metric_name + "{"
    bare = metric_name + " "
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith(prefix) or line.startswith(bare):
            try:
                total += float(line.rsplit(" ", 1)[1])
            except (IndexError, ValueError):
                continue
    return total


# ── Gateway: picks the right provider based on what's available ──────────


class LLMGateway:
    """Single entry point for LLM calls. Picks provider based on config + tier."""

    # Preference order: on-prem vLLM first (free + private + fast LAN),
    # Anthropic second (managed fallback), Kimi third (CR126 — a candidate
    # B7 provider being manually tested, not yet trusted as a default),
    # mock last.
    _PREFERENCE: tuple[str, ...] = ("vllm", "anthropic", "kimi", "mock")

    # Single-model providers: every tier resolves to the one hosted/selected
    # model rather than TIER_TO_MODEL's cheap/mid/premium Anthropic aliases.
    # Keyed by provider name -> the Settings attribute holding its model id.
    _SINGLE_MODEL_SETTING: dict[str, str] = {"vllm": "vllm_model", "kimi": "kimi_model"}

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockProvider()}

        if settings.vllm_base_url:
            self._providers["vllm"] = VLLMProvider(
                base_url=settings.vllm_base_url,
                model_name=settings.vllm_model,
                api_key=settings.vllm_api_key or None,
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider="vllm",
                base_url=settings.vllm_base_url,
                model=settings.vllm_model,
            )
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="vllm",
                reason="no VLLM_BASE_URL in env",
            )

        if settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
            logger.info("llm_gateway_provider_registered", provider="anthropic")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="anthropic",
                reason="no ANTHROPIC_API_KEY in env",
            )

        if settings.kimi_api_key:
            self._providers["kimi"] = OpenAICompatibleProvider(
                name="kimi",
                base_url=settings.kimi_base_url,
                model_name=settings.kimi_model,
                api_key=settings.kimi_api_key,
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider="kimi",
                base_url=settings.kimi_base_url,
                model=settings.kimi_model,
            )
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="kimi",
                reason="no KIMI_API_KEY in env",
            )

    def has_real_provider(self) -> bool:
        return any(name != "mock" for name in self._providers)

    async def check_prefix_cache_at_startup(self) -> None:
        """CR077 Phase 0 second guard — no-op when vLLM isn't registered."""
        provider = self._providers.get("vllm")
        if isinstance(provider, VLLMProvider):
            await provider.log_prefix_cache_status()

    def _active_provider_name(self) -> str:
        """Which provider a call will actually hit right now.

        `LLM_FORCE_PROVIDER` (settings.llm_force_provider) short-circuits the
        preference order for manual testing — e.g. exercising Kimi without
        touching `_PREFERENCE` or unregistering vLLM. An unregistered/typo'd
        name falls through to normal preference rather than erroring: a test
        env var must never be able to 500 a live flow. `status()` and
        `_pick_provider()` both read this, so /v1/llm/status never disagrees
        with what a real call would do.
        """
        forced = settings.llm_force_provider
        if forced and forced in self._providers:
            return forced
        for name in self._PREFERENCE:
            if name in self._providers:
                return name
        return "mock"

    def status(self) -> dict[str, object]:
        """Snapshot of what the gateway will actually do at call time.

        Surfaced by /v1/llm/status so Saiful can curl-check whether the live
        flip happened without grepping env vars. Does NOT call any provider.
        Per-(plan, agent) routing decisions live in
        `app.services.tier_policy.pick_tier`, not in the gateway.
        """
        active = self._active_provider_name()
        single_model_setting = self._SINGLE_MODEL_SETTING.get(active)
        if single_model_setting:
            single_model = getattr(settings, single_model_setting)
            tier_to_model: dict[str, str] = {t: single_model for t in TIER_TO_MODEL}
        else:
            tier_to_model = dict(TIER_TO_MODEL)
        return {
            "providers_registered": sorted(self._providers.keys()),
            "active_provider": active,
            "has_real_provider": self.has_real_provider(),
            "tier_to_model": tier_to_model,
        }

    def _pick_provider(self, locale: str, model_tier: ModelTier) -> LLMProvider:
        """Pick a provider — see `_active_provider_name` for the actual logic."""
        return self._providers[self._active_provider_name()]

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        locale: str = "en",
        max_tokens: int = 1024,
        audit_user_id: object = None,
        audit_agent_id: str | None = None,
        audit_flow: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        import time
        from app.services.audit import record_llm_call

        provider = self._pick_provider(locale, model_tier)
        # CR056: every call gets the no-assumed-data directive prepended, so it is
        # both applied (handed to the provider) AND auditable (recorded to
        # llm_audit) on this one shared path — agents, Concierge, reformatter alike.
        effective_system_prompt = prepend_grounding_directive(system_prompt)
        logger.info(
            "llm_call_start",
            provider=provider.name,
            tier=model_tier,
            locale=locale,
            messages_count=len(messages),
            agent_id=audit_agent_id,
            flow=audit_flow,
        )
        started = time.perf_counter()
        buf: list[str] = []
        error_str: str | None = None
        # DEF125: always give the provider somewhere to report the stop reason,
        # even when the caller did not ask for it — the length-stop warning
        # below is what makes a silent truncation visible on EVERY flow
        # (room, one-on-one, brief, Concierge), not only the ones that opted in.
        call_meta: dict[str, Any] = meta if meta is not None else {}
        try:
            async for chunk in provider.stream_chat(
                system_prompt=effective_system_prompt,
                messages=messages,
                model_tier=model_tier,
                max_tokens=max_tokens,
                meta=call_meta,
            ):
                buf.append(chunk)
                yield chunk
        except Exception as exc:
            error_str = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            if call_meta.get("finish_reason") == "length":
                # CR040 — degrade loudly. The model ran out of budget mid-
                # sentence and the caller is about to treat the fragment as a
                # finished answer. DEF125 measured this at 66% of Research
                # Manager turns while nothing anywhere said a word about it.
                logger.warning(
                    "llm_call_length_stop",
                    provider=provider.name,
                    tier=model_tier,
                    agent_id=audit_agent_id,
                    flow=audit_flow,
                    max_tokens=max_tokens,
                    chars=sum(len(c) for c in buf),
                )
            record_llm_call(
                user_id=audit_user_id if audit_user_id else None,
                agent_id=audit_agent_id,
                flow=audit_flow,
                tier=model_tier,
                provider=provider.name,
                locale=locale,
                system_prompt=effective_system_prompt,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                response_text="".join(buf) if buf else None,
                latency_ms=latency_ms,
                error=error_str,
            )


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
