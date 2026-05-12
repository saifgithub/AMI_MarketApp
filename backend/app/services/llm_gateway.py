"""LLM gateway — provider-agnostic interface for the rest of the backend.

The gateway picks a provider at runtime based on:
  - which API keys are configured in settings
  - the requested model tier (cheap / mid / premium)
  - the user's locale (Arabic prefers Gemini; we'll wire that when Google client added)

Providers implemented:
  - MockProvider     → returns canned responses; used when no real key is set.
                       Lets the full UX work without API keys configured.
  - AnthropicProvider → direct Anthropic API. Supports streaming.

Coming later (W4+):
  - OpenAIProvider, GoogleProvider, OpenRouterProvider

See docs/08_tech/llm_routing.md for the routing strategy.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

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
    ) -> AsyncIterator[str]:
        """Yield content chunks as they arrive from the provider."""
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
                except Exception as e:
                    logger.warn("anthropic_chunk_parse_failed", error=str(e), line=line[:200])

    async def aclose(self) -> None:
        await self._client.aclose()


# ── vLLM provider (on-prem, OpenAI-compatible) ───────────────────────────


class VLLMProvider(LLMProvider):
    """Streams completions from an on-prem vLLM server.

    vLLM exposes the OpenAI `/v1/chat/completions` schema, so the only
    bespoke logic here is the SSE parser (`choices[0].delta.content`
    instead of Anthropic's `content_block_delta`) and the system-prompt
    placement (vLLM/OpenAI puts `system` inside `messages`, not as a
    sibling field).

    Tier mapping: vLLM serves a single model at a time, so all tiers
    resolve to the same `model_name`. The per-(plan, agent) tier policy
    in `tier_policy.py` still picks a tier — vLLM just ignores the
    distinction. When the day comes that we host multiple sizes side by
    side, swap `model_name` for a `tier_to_model` map.
    """

    name = "vllm"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model_name = model_name
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
    ) -> AsyncIterator[str]:
        # OpenAI / vLLM put the system message as the first entry of `messages`.
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
        }

        async with self._client.stream("POST", "/v1/chat/completions", json=body) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                logger.error(
                    "vllm_error",
                    status=resp.status_code,
                    body=err_body.decode()[:500],
                )
                yield (
                    f"\n\n[AMI error: HTTP {resp.status_code} from the on-prem AMI server. "
                    "Check backend logs.]"
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
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception as e:
                    logger.warn("vllm_chunk_parse_failed", error=str(e), line=line[:200])

    async def aclose(self) -> None:
        await self._client.aclose()


# ── Gateway: picks the right provider based on what's available ──────────


class LLMGateway:
    """Single entry point for LLM calls. Picks provider based on config + tier."""

    # Preference order: on-prem vLLM first (free + private + fast LAN),
    # Anthropic second (managed fallback), mock last.
    _PREFERENCE: tuple[str, ...] = ("vllm", "anthropic", "mock")

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

    def has_real_provider(self) -> bool:
        return any(name != "mock" for name in self._providers)

    def _active_provider_name(self) -> str:
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
        # When vLLM is active, every tier resolves to the single hosted model.
        if active == "vllm":
            tier_to_model: dict[str, str] = {t: settings.vllm_model for t in TIER_TO_MODEL}
        else:
            tier_to_model = dict(TIER_TO_MODEL)
        return {
            "providers_registered": sorted(self._providers.keys()),
            "active_provider": active,
            "has_real_provider": self.has_real_provider(),
            "tier_to_model": tier_to_model,
        }

    def _pick_provider(self, locale: str, model_tier: ModelTier) -> LLMProvider:
        """Pick a provider in preference order (vllm > anthropic > mock)."""
        for name in self._PREFERENCE:
            if name in self._providers:
                return self._providers[name]
        return self._providers["mock"]

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        locale: str = "en",
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        provider = self._pick_provider(locale, model_tier)
        logger.info(
            "llm_call_start",
            provider=provider.name,
            tier=model_tier,
            locale=locale,
            messages_count=len(messages),
        )
        async for chunk in provider.stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=model_tier,
            max_tokens=max_tokens,
        ):
            yield chunk


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
