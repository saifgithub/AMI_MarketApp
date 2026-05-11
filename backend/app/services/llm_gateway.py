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


# Per-agent tier routing. Lets a Floor-Pass user still get Opus when the
# Portfolio Manager rules on a trade, while routing chatter to Haiku.
# The plan-tier remains the base; per-agent rules can BUMP UP (not down)
# so the safety floor never gets a cheaper brain than the team.
AGENT_MIN_TIER: dict[str, ModelTier] = {
    "concierge": "cheap",
    "fundamentals_analyst": "mid",
    "market_analyst": "mid",
    "news_analyst": "cheap",
    "social_media_analyst": "cheap",
    "bull_researcher": "mid",
    "bear_researcher": "mid",
    "research_manager": "mid",
    "trader": "mid",
    "aggressive_debator": "mid",
    "conservative_debator": "mid",
    "neutral_debator": "mid",
    "portfolio_manager": "premium",  # safety-floor enforcer, always premium
}


_TIER_RANK: dict[ModelTier, int] = {"cheap": 0, "mid": 1, "premium": 2}


def resolve_tier(plan_tier: ModelTier, agent_id: str | None) -> ModelTier:
    """Take the higher of (plan tier, per-agent min tier).

    Floor-Pass user 1-on-1 with Concierge → cheap.
    Floor-Pass user 1-on-1 with Portfolio Manager → premium.
    Floor-Manager Room run with any agent → premium.
    """
    if agent_id is None:
        return plan_tier
    min_tier = AGENT_MIN_TIER.get(agent_id, plan_tier)
    return plan_tier if _TIER_RANK[plan_tier] >= _TIER_RANK[min_tier] else min_tier


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
            "Mock Fundamentals Analyst here. Without live financial data I can't run a "
            "real evaluation, but the framework is:\n\n"
            "• Pull last 4 quarters of income statement, balance sheet, cash flow\n"
            "• Compute trailing P/E, EV/EBITDA, FCF yield vs sector median\n"
            "• Check debt-to-equity and interest coverage\n"
            "• Compare against the 3 nearest peers\n\n"
            "Once Saiful configures an LLM API key (Anthropic / OpenRouter), I'll do the "
            "actual numbers. For now you're seeing this canned text."
        ),
        "market_analyst": (
            "Mock Market Analyst. The chart would show me trend, momentum, key levels. "
            "When live, I'd give you specific entries, targets, stops.\n\n"
            "Configure an LLM API key to swap me from canned to real."
        ),
        "bear_researcher": (
            "Mock Bear here. My real job is to find what's wrong with the thesis. The "
            "structure of a good bear case: identify the 2-3 risks that materially matter, "
            "quantify them, address how the Bull would respond.\n\n"
            "Configure an LLM API key for live analysis."
        ),
        "bull_researcher": (
            "Mock Bull here. My real job is to steelman the long case. Structure: "
            "thesis in one sentence, cite the Analysts' evidence, anticipate the Bear's "
            "counter, propose sizing.\n\n"
            "Configure an LLM API key for live analysis."
        ),
        "trader": (
            "Mock Trader. Once we have live data I'll give you: instrument, side, size, "
            "entry, target, stop, time horizon. All sized to your mandate.\n\n"
            "Configure an LLM API key to go live."
        ),
        "portfolio_manager": (
            "Mock PM here. My role is to gatekeep — every trade goes through compliance "
            "check (deterministic) and judgment review (LLM, once configured).\n\n"
            "Configure an LLM API key for real verdicts."
        ),
        "concierge": (
            "Mock Concierge here! I'd normally route you to the right lesson, search your "
            "journal, or schedule briefings. Once Saiful configures an LLM API key in the "
            "backend, I'll be fully live.\n\n"
            "For now: the onboarding flow works fully (no LLM needed), and you can browse "
            "lessons. Want me to find one for you?"
        ),
    }

    _DEFAULT = (
        "I'm running in mock mode — no LLM API key configured yet. Once Saiful adds an "
        "Anthropic or OpenRouter key to the backend's .env file, I'll come fully online "
        "and respond properly to your question."
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
                    f"\n\n[LLM error: HTTP {resp.status_code} from Anthropic. "
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


# ── Gateway: picks the right provider based on what's available ──────────


class LLMGateway:
    """Single entry point for LLM calls. Picks provider based on config + tier."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockProvider()}
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

    def status(self) -> dict[str, object]:
        """Snapshot of what the gateway will actually do at call time.

        Surfaced by /v1/llm/status so Saiful can curl-check whether the live
        flip happened without grepping env vars. Does NOT call any provider.
        """
        return {
            "providers_registered": sorted(self._providers.keys()),
            "active_provider": "anthropic" if "anthropic" in self._providers else "mock",
            "has_real_provider": self.has_real_provider(),
            "tier_to_model": dict(TIER_TO_MODEL),
            "agent_min_tier": dict(AGENT_MIN_TIER),
        }

    def _pick_provider(self, locale: str, model_tier: ModelTier) -> LLMProvider:
        """Routing logic. V0: prefer Anthropic if present, else mock.
        V1 will add OpenRouter as primary and route Arabic → Gemini.
        """
        if "anthropic" in self._providers:
            return self._providers["anthropic"]
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
