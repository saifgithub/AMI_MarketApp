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
                       KimiProvider/DeepSeek/Qwen/Gemini instances register
                       the same way (CR141 registers the latter three from
                       settings — see LLMGateway.__init__).

CR141 (build half of CR017) also added:
  - Usage capture: every provider writes prompt/completion/cache token counts
    into the shared DEF125 `meta` dict, which `stream_chat`'s `finally` block
    reads and threads into `record_llm_call` → `llm_audit`'s four `*_tokens`
    columns. See `_capture_anthropic_message_start_usage` /
    `_capture_anthropic_message_delta_usage` (Anthropic splits usage across
    two SSE frames) and `_parse_openai_compatible_usage` (single terminal
    frame, `stream_options.include_usage`).
  - `provider_policy.pick_provider` — a routing layer `_pick_provider`
    consults when a caller supplies `plan`/`agent_id`; unconsumed by any
    live call site yet (the plan→level mapping is still an open pricing
    decision — see `provider_policy`'s module docstring).

See docs/initial_specs/08_tech/llm_routing.md for the routing strategy.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.llm_allowlist import blocked_slots, configured_slots
from app.core.llm_extra_body import PROTECTED_BODY_FIELDS, parse_extra_body
from app.core.logging import logger
from app.schemas import AGENT_DISPLAY_NAMES, AgentId
from app.schemas.mandate import Plan


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


@dataclass(frozen=True)
class OutputConstraint:
    """CR210 — a decoding grammar for ONE call, which the provider either
    enforces on the wire or the gateway refuses to send.

    A typed object rather than a dict, and rather than separate
    `response_format=` / `structured_outputs=` kwargs, for three reasons:

    1. **The wire vocabulary is not the caller's business.** `guided_json` is
       not a field on this server's `ChatCompletionRequest`, and because that
       model declares `additionalProperties: true` it is accepted with HTTP 200
       and silently dropped (verified 2026-08-25 against ami-llm). A dict
       channel lets a call site ship that key; this object makes the spelling
       `_constraint_request_fields`' decision, in one place, tested once.
    2. **"Exactly one grammar" is enforceable here and nowhere else.** Two
       kwargs cannot express it; `__post_init__` can.
    3. **`name` is mandatory.** The audit column and every log line have to say
       WHICH grammar was in force, or the guard cannot distinguish the states it
       exists to distinguish.

    Frozen because providers are shared singletons serving concurrent runs —
    the same reason DEF125's `meta` is per-call rather than provider state.
    """

    name: str
    json_schema: dict[str, Any] | None = None
    regex: str | None = None

    def __post_init__(self) -> None:
        if (self.json_schema is None) == (self.regex is None):
            raise ValueError(
                "OutputConstraint takes exactly one of json_schema / regex"
            )
        if not self.name:
            raise ValueError("OutputConstraint needs a name — it is the audit label")

    @property
    def kind(self) -> Literal["json_schema", "regex"]:
        return "json_schema" if self.json_schema is not None else "regex"


def _constraint_request_fields(constraint: OutputConstraint) -> dict[str, Any]:
    """The outbound request fields for one constraint, on an OpenAI-compatible
    endpoint.

    JSON → the OpenAI-standard `response_format`, because it is the only spelling
    a non-vLLM endpoint might also honour. Regex → vLLM's `structured_outputs`,
    which has no OpenAI-standard equivalent — which is why the regex path is
    vLLM-only and says so in `VLLMProvider.supported_constraints`.

    NEVER `guided_json` / `guided_regex`. They are not fields on this server's
    `ChatCompletionRequest`, and `additionalProperties: true` means they come
    back HTTP 200 with a prose answer instead of an error (verified 2026-08-25:
    the model ignored the schema entirely). A constraint that cannot fail loudly
    is worse than no constraint, because every layer above reads it as enforced.

    `disable_any_whitespace` is deliberately not sent: measured on this build to
    have no visible effect, and shipping a field that does nothing is how the
    next reader concludes it does something.
    """
    if constraint.json_schema is not None:
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": constraint.name,
                    "schema": constraint.json_schema,
                    "strict": True,
                },
            }
        }
    return {"structured_outputs": {"regex": constraint.regex}}


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
#   2. PREPEND only. The Chief Investment Officer's safety floor must remain the LAST
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


_ANTHROPIC_MAX_TEMPERATURE = 1.0


def _desk_temperature_fields(*, ceiling: float | None = None) -> dict[str, float]:
    """CR269 — the one place the desk sampling temperature enters a request body.

    Empty when `llm_desk_temperature` is unset, so nothing changes on the wire
    until an operator sets it. `ceiling` is for a provider whose API rejects the
    full [0, 2] range (Anthropic: 1.0); exceeding it is clamped LOUDLY, because a
    400 from the first-fallback provider would turn an outage into a hard stop.
    """
    value = settings.llm_desk_temperature
    if value is None:
        return {}
    if ceiling is not None and value > ceiling:
        logger.warning(
            "llm_temperature_clamped",
            requested=value,
            sent=ceiling,
            detail="provider's maximum temperature is below LLM_DESK_TEMPERATURE",
        )
        value = ceiling
    return {"temperature": value}


_CALL_OVERRIDE_FIELDS = frozenset(
    {"temperature", "logprobs", "top_logprobs", "chat_template_kwargs"}
)


def _call_request_overrides(meta: dict[str, Any]) -> dict[str, Any]:
    """CR267 WP-22 — opt-in per-call sampling fields for the offline Room graders.

    A grader must run at temperature 0 and read token probabilities, while the
    desks keep the global `llm_desk_temperature`. The caller puts
    `request_overrides` in its own `meta`; only the three whitelisted fields
    reach the wire, and an absent key changes nothing for any other call.
    `chat_template_kwargs` (a vLLM chat-template hook, e.g. `enable_thinking`) is
    MERGED into the slot's own dict rather than replacing it (`_apply_call_overrides`),
    so a grader can switch thinking off for its short answers without touching the
    slot's desk-facing configuration.
    """
    raw = meta.get("request_overrides")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in _CALL_OVERRIDE_FIELDS}


def _apply_call_overrides(body: dict[str, Any], meta: dict[str, Any]) -> None:
    """Put the call's `request_overrides` on [body]; `chat_template_kwargs` merges
    key-by-key into what the slot already sends, everything else replaces."""
    overrides = _call_request_overrides(meta)
    kwargs = overrides.pop("chat_template_kwargs", None)
    body.update(overrides)
    if isinstance(kwargs, dict):
        body["chat_template_kwargs"] = {**(body.get("chat_template_kwargs") or {}), **kwargs}


class LLMProvider:
    name: str = "base"
    # CR210 — which decoding grammars this provider can actually ENFORCE.
    # Empty is the safe default: the gateway then refuses to put a constraint on
    # the wire and records the call `unsupported`, rather than sending a field
    # the server accepts and drops. A class attribute rather than `isinstance`
    # because capability is not a class question — `OpenAICompatibleProvider`
    # instances named "gemini" and "deepseek" are the same class with different
    # capabilities, so isinstance would force a class per endpoint.
    supported_constraints: frozenset[str] = frozenset()

    def static_model_identity(self) -> str | None:
        """CR270 — the most specific model id known WITHOUT a call, or None."""
        return None

    async def read_served_root(self, ttl_s: float) -> str | None:
        """CR267 WP-24 — the identity of the model behind this slot as the
        server itself reports it, read fresh within `ttl_s`; None when it cannot
        be read. A Room is banked only against a root, never against the alias
        or the configured id."""
        return None

    def resolve_model(self, meta: dict[str, Any]) -> str | None:
        """CR270 — the model that served one call, for `llm_audit.model`.

        `meta` is the call's DEF125 channel: the provider writes
        `configured_model` before the request and `reported_model` when the
        response names one. Most specific wins; None only when neither exists.
        """
        return meta.get("reported_model") or meta.get("configured_model")

    def price_keys(self, meta: dict[str, Any]) -> list[str]:
        """CR270 — the ids a price may be filed under, most specific first."""
        keys: list[str] = []
        for k in (
            self.resolve_model(meta),
            meta.get("reported_model"),
            meta.get("configured_model"),
        ):
            if k and k not in keys:
                keys.append(k)
        return keys

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
        constraint: OutputConstraint | None = None,
    ) -> AsyncIterator[str]:
        """Yield content chunks as they arrive from the provider.

        CR210: [constraint] is a decoding grammar the provider is expected to put
        on the wire. The gateway NEVER passes one whose `kind` is absent from
        this provider's `supported_constraints` — see `LLMGateway.stream_chat`'s
        capability gate — so an implementation may assume any constraint it
        receives is one it declared it can enforce. A provider that declares none
        may ignore the parameter; it will never be non-None.

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

    def static_model_identity(self) -> str | None:
        return "mock"

    async def read_served_root(self, ttl_s: float) -> str | None:
        return "mock"

    def resolve_model(self, meta: dict[str, Any]) -> str | None:
        return "mock"

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
            "AMI's Technical Strategist, currently offline. The chart would show me trend, "
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
            "AMI's Execution Desk, currently offline. Once we have live data I'll give you: "
            "instrument, side, size, entry, target, stop, time horizon — all sized to "
            "your mandate.\n\n"
            "AMI is in fallback mode."
        ),
        "portfolio_manager": (
            "AMI's CIO here, offline. My role is to gatekeep — every trade goes through "
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
        constraint: OutputConstraint | None = None,
    ) -> AsyncIterator[str]:
        # CR210 — accepted to satisfy the provider contract and never non-None
        # in practice: `supported_constraints` is empty for this provider, so the
        # gateway strips any constraint before calling here and records the call
        # `unsupported`. Deliberately NOT a raise — the capability gate lives in
        # exactly one place, and a second gate here would mean two places can
        # disagree about what "unsupported" means.
        # Pick canned response based on which agent's prompt this is
        text = self._DEFAULT
        sp = system_prompt.lower()
        for key, response in self._CANNED.items():
            display = AGENT_DISPLAY_NAMES[AgentId(key)].lower()
            if f"agent_id: {key}" in sp or key.replace("_", " ") in sp or display in sp:
                text = response
                break

        # Stream char-by-char so the UI sees the typewriter effect
        for char in text:
            yield char
            # Small jitter so it feels organic
            await asyncio.sleep(random.uniform(0.005, 0.020))


def canned_agent_fallback(agent_id: "AgentId | str") -> str:
    """The branded "AMI is offline" copy for one agent — DEF424.

    Same text `MockProvider` streams when no real provider is configured at
    all, reused here for the DIFFERENT case of a real provider that is
    configured but unreachable mid-call (a raised transport exception or an
    in-band `stream_error`). Keyed directly by `agent_id` rather than
    sniffing the system prompt (`MockProvider`'s own approach) — every
    caller of this function already knows exactly which agent it is, so a
    direct dict lookup can't mis-route the way a substring sniff could.

    An agent absent from `MockProvider._CANNED` (news_analyst,
    social_media_analyst, research_manager, the three risk debators) falls
    back to `MockProvider._DEFAULT` — still branded AMI copy, never a raw
    transport string.
    """
    key = agent_id.value if isinstance(agent_id, AgentId) else str(agent_id)
    return MockProvider._CANNED.get(key, MockProvider._DEFAULT)


# ── Anthropic provider ───────────────────────────────────────────────────
#
# CR141 usage capture: Anthropic splits token counts across TWO SSE frames —
# `message_start` carries input tokens + both cache fields once per stream;
# `message_delta` carries a CUMULATIVE output_tokens count, updated as the
# response grows. These two helpers merge into whatever `meta["usage"]`
# already holds rather than overwriting it, and each swallows its own parse
# failures (never raises) so a malformed usage sub-object degrades that one
# field, not the stream (CR141 acceptance 3).


def _capture_anthropic_message_start_usage(obj: dict, meta: dict[str, Any]) -> None:
    """`message_start.message.usage` → input_tokens + both cache fields.

    The cache fields are **not** guaranteed present. An earlier version of this
    docstring claimed Anthropic "always reports" them and that a None here
    therefore meant a malformed frame; the CR141 audit checked the official
    streaming examples and found 2 of 3 omit them from `message_start.usage`
    entirely. Corrected rather than deleted, because the wrong version was the
    kind of claim that invites someone to "simplify" the `.get()` into a `[...]`
    lookup and crash on a normal response.

    Behaviour was already right: `.get()` yields None and None is stored, so an
    absent field records NULL. Same NULL-vs-0 contract as the OpenAI-compatible
    path — a missing cache field is not a measured zero.
    """
    try:
        msg_usage = ((obj.get("message") or {}).get("usage")) or {}
        if not msg_usage:
            return
        usage = meta.setdefault("usage", {})
        usage["input_tokens"] = msg_usage.get("input_tokens")
        usage["cache_read_tokens"] = msg_usage.get("cache_read_input_tokens")
        usage["cache_write_tokens"] = msg_usage.get("cache_creation_input_tokens")
    except Exception as e:
        logger.warn("anthropic_usage_parse_failed", error=str(e), frame="message_start")


def _capture_anthropic_message_delta_usage(obj: dict, meta: dict[str, Any]) -> None:
    """`message_delta.usage.output_tokens` → the cumulative output count.

    Merges into whatever `message_start` already populated instead of
    replacing it, so a stream missing one frame still records the other.
    """
    try:
        delta_usage = obj.get("usage") or {}
        if not delta_usage or "output_tokens" not in delta_usage:
            return
        usage = meta.setdefault("usage", {})
        usage["output_tokens"] = delta_usage.get("output_tokens")
    except Exception as e:
        logger.warn("anthropic_usage_parse_failed", error=str(e), frame="message_delta")


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self, api_key: str, timeout_seconds: float | None = None
    ) -> None:
        self._key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            # DEF394 — derived from the Room's guard, never a literal. This class
            # is NOT an `OpenAICompatibleProvider`, so DEF392's fix did not reach
            # it, and `anthropic` is the FIRST fallback in `_PREFERENCE`. A 60s
            # transport inside the 180s guard means the guard can never fire and a
            # slow completion degrades into the DEF059 fail-safe PASS — on the very
            # path taken when vLLM is down, i.e. exactly when it is being relied on.
            timeout=(
                _default_transport_timeout_s()
                if timeout_seconds is None
                else timeout_seconds
            ),
        )

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
        constraint: OutputConstraint | None = None,
    ) -> AsyncIterator[str]:
        # CR210 — accepted to satisfy the provider contract and never non-None
        # in practice: `supported_constraints` is empty for this provider, so the
        # gateway strips any constraint before calling here and records the call
        # `unsupported`. Deliberately NOT a raise — the capability gate lives in
        # exactly one place, and a second gate here would mean two places can
        # disagree about what "unsupported" means.
        model = TIER_TO_MODEL[model_tier]
        if meta is not None:
            meta.pop("reported_model", None)
            meta["configured_model"] = model
        # Anthropic separates `system` from `messages`; user/assistant only in messages
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "system": system_prompt,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **_desk_temperature_fields(ceiling=_ANTHROPIC_MAX_TEMPERATURE),
        }

        async with self._client.stream("POST", "/v1/messages", json=body) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                detail = err_body.decode()[:500]
                logger.error(
                    "anthropic_error",
                    status=resp.status_code,
                    body=detail,
                )
                # RETRO-SECURITY MAJOR-2 (round 2) — this top-level transport
                # failure used to yield only the `[AMI error: …]` sentinel
                # TEXT with no `meta["stream_error"]` write, so a caller could
                # only detect the failure by string-matching the reply (the
                # in-band SSE error frame branch below already did this
                # correctly; this HTTP-status branch did not). Detection must
                # be structural, not prose-matching — same `stream_error` key
                # DEF376's in-band frame writes, so every caller that already
                # checks it (room_runner's per-agent fallback, and now
                # brief.py/one_on_one.py's refund gate) sees this failure
                # shape too, with no second code path to keep in sync.
                if meta is not None:
                    meta["stream_error"] = f"HTTP {resp.status_code}: {detail}"
                    meta["stream_error_status"] = resp.status_code
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
                    obj_type = obj.get("type")
                    if obj_type == "error":
                        # DEF376 — the Anthropic half of the same hole. This
                        # loop branches on `type`, and an `{"type": "error",
                        # "error": {…}}` frame matched NO branch, so it was
                        # silently skipped exactly like the OpenAI-compatible
                        # path's `{"error": …}`. Fixing one provider and not the
                        # other would leave the defect half-open: the statement
                        # is "in-band error frames are swallowed", not "vLLM's
                        # are". `finish_reason` stays unwritten here too.
                        err = obj.get("error") or {}
                        detail = err.get("message") if isinstance(err, dict) else err
                        detail = str(detail or obj)[:500]
                        logger.error(
                            "anthropic_stream_error",
                            error=detail,
                            channel="in-band SSE error frame (HTTP 200)",
                        )
                        if meta is not None:
                            meta["stream_error"] = detail
                        yield (
                            "\n\n[AMI error: the upstream provider (anthropic) "
                            "refused this request mid-stream. Check backend logs.]"
                        )
                        return
                    if obj_type == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                    elif obj_type == "message_start" and meta is not None:
                        # CR141: input tokens + both cache fields arrive once,
                        # here — see the helper's docstring.
                        _capture_anthropic_message_start_usage(obj, meta)
                        # CR270 — the dated snapshot the API actually served.
                        reported = (obj.get("message") or {}).get("model")
                        if reported:
                            meta["reported_model"] = str(reported)
                    elif obj_type == "message_delta" and meta is not None:
                        # DEF125: Anthropic reports the terminal stop on
                        # `message_delta.delta.stop_reason`. Normalise its
                        # `max_tokens` to the OpenAI/vLLM vocabulary so callers
                        # test one value regardless of which provider served.
                        stop = ((obj.get("delta") or {}).get("stop_reason"))
                        if stop:
                            meta["finish_reason"] = (
                                "length" if stop == "max_tokens" else str(stop)
                            )
                        # CR141: output_tokens is CUMULATIVE here, unlike the
                        # OpenAI-compat path's single terminal usage frame.
                        _capture_anthropic_message_delta_usage(obj, meta)
                except Exception as e:
                    logger.warn("anthropic_chunk_parse_failed", error=str(e), line=line[:200])

    async def aclose(self) -> None:
        await self._client.aclose()


# ── OpenAI-compatible provider (vLLM, Kimi, and any future chat-completions
#    endpoint — CR017) ────────────────────────────────────────────────────


def _parse_openai_compatible_usage(usage: dict[str, Any]) -> dict[str, Any]:
    """Normalise an OpenAI-compatible terminal `usage` object (CR141).

    `prompt_cache_hit_tokens` is DeepSeek's field name; `prompt_tokens_
    details.cached_tokens` is vLLM/OpenAI/Gemini's. A provider that reports
    NEITHER key yields None here — never 0 — because an absent field means
    "we don't know", not "zero cache hit" (CR040, CR141 acceptance 2): a key
    that IS present with value 0 (a real cache miss) is returned as 0,
    unchanged, since `.get()` only returns None on a genuine miss.

    No OpenAI-compatible provider registered here charges a cache WRITE fee
    (that's an Anthropic-only concept — see `AnthropicProvider`'s usage
    helpers), so `cache_write_tokens` is always None on this path.
    """
    cache_read = usage.get("prompt_cache_hit_tokens")
    if cache_read is None:
        details = usage.get("prompt_tokens_details")
        if isinstance(details, dict):
            cache_read = details.get("cached_tokens")
    return {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "cache_read_tokens": cache_read,
        "cache_write_tokens": None,
    }


# DEF392 — the TRANSPORT budget for any OpenAI-compatible provider is derived
# from the Room's orchestration guard, never written as a literal. A fixed
# default is what made this a defect twice: `timeout_seconds: float = 60.0` sat
# below the guard (DEF389 for vLLM, and — unfixed until now — for kimi,
# deepseek, qwen and gemini, whose registrations pass no timeout at all and so
# all inherited the 60s default inside a 180s guard). Derived from
# `settings.room_agent_timeout_s` instead, the ordering invariant holds for
# every provider and moves with the guard when it is retuned.
#
# The margin is the guard's own size, i.e. transport >= 2x the guard. At the
# shipped defaults that is 180 + 180 = 360s, the value DEF389 measured as
# needing >= 2x the 45.9s five-way `pm_self_consistency_samples` fan-out, so all
# five providers now carry the same shape of headroom rather than one provider
# and four defaults.
_TRANSPORT_TIMEOUT_MARGIN_S: float = 180.0


def _default_transport_timeout_s() -> float:
    """The transport budget a provider gets when the caller names none.

    Resolved at CONSTRUCTION, not at import: `Settings` is instantiated per
    process from env, and tests retune `settings.room_agent_timeout_s` between
    cases. A module-level constant computed from the setting would freeze the
    import-time value and stop tracking the guard.
    """
    return settings.room_agent_timeout_s + _TRANSPORT_TIMEOUT_MARGIN_S


class _TransientProviderError(Exception):
    """CR272 — a 429/5xx answered before any chunk existed; the retry loop in
    `OpenAICompatibleProvider.stream_chat` catches it. Never escapes that method."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalise_base_url(url: str) -> str:
    """CR281 — one spelling of an OpenAI-compatible base URL.

    The provider appends `/v1/chat/completions` (and `/v1/models`) itself, so a
    base configured WITH a trailing `/v1` used to become `/v1/v1/...` and 404.
    Strip whitespace, trailing slashes and one trailing `/v1`, so both spellings
    of the same endpoint work and a model/provider swap is an env change only.
    """
    text = (url or "").strip().rstrip("/")
    # `/v1/openai` is DeepInfra's documented spelling of the same endpoint the
    # bare host serves at `/v1/chat/completions` (verified live, CR281).
    for suffix in ("/v1/openai", "/v1"):
        if text.endswith(suffix):
            return text[: -len(suffix)].rstrip("/")
    return text


def openai_compatible_headers(api_key: str | None) -> dict[str, str]:
    """CR281 — request headers for an OpenAI-compatible slot, either kind.

    A configured key is sent as `Authorization: Bearer <key>`. An empty or
    whitespace-only key sends NO auth header at all: never `Bearer ` with
    nothing after it and never a placeholder, which a keyless server (on-prem
    vLLM) may treat as a malformed credential and a hosted one rejects.
    """
    headers = {"Content-Type": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


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
        timeout_seconds: float | None = None,
        extra_body: dict[str, Any] | None = None,
        max_tokens_floor: int | None = None,
        supported_constraints: frozenset[str] | None = None,
        max_retries: int = 0,
        retry_backoff_s: float = 1.0,
    ) -> None:
        # DEF392 — `None` is "derive it from the guard", not "use a default
        # number". Explicit callers are unchanged; what changes is that an
        # Omitted argument can no longer land the client inside the guard.
        if timeout_seconds is None:
            timeout_seconds = _default_transport_timeout_s()
        self.name = name
        # CR210 — instance override of the class default, the same idiom as
        # `self.name` on the line above. Set it ONLY for an endpoint whose
        # enforcement has actually been verified against that server; an
        # unverified value here is the `guided_json` silent-drop with our own
        # name on it.
        if supported_constraints is not None:
            self.supported_constraints = supported_constraints
        self._model_name = model_name
        # CR270 — what `GET /v1/models` said about the model behind this slot,
        # filled once at startup by `discover_served_model` (never required).
        # `served_root` is the vLLM `root` field (the real served path — the
        # alias the slot is configured with is reused across swaps and names
        # nothing); `served_id` is the entry's `id`.
        self.served_root: str | None = None
        self.served_id: str | None = None
        # CR267 WP-24 — monotonic time of the last discovery that reached the
        # server and found this slot's entry; None until one has.
        self.served_at: float | None = None
        # CR281 — fields the gateway owns can never arrive via extra_body.
        self._extra_body = {
            k: v for k, v in (extra_body or {}).items() if k not in PROTECTED_BODY_FIELDS
        }
        # CR272 — transient-failure retries, 0 (none) unless a slot opts in.
        self._max_retries = max(0, max_retries)
        self._retry_backoff_s = max(0.0, retry_backoff_s)
        # CR130: reasoning-style providers (Kimi) spend `max_tokens` on
        # invisible chain-of-thought before any visible content, so the
        # Room's per-agent budgets (tuned for vLLM, a non-reasoning model)
        # starve them. A floor here raises whatever the caller requests up
        # to at least this value for THIS provider instance only — every
        # other provider is unaffected.
        self._max_tokens_floor = max_tokens_floor
        self._client = httpx.AsyncClient(
            base_url=normalise_base_url(base_url),
            headers=openai_compatible_headers(api_key),
            timeout=timeout_seconds,
        )

    def static_model_identity(self) -> str | None:
        return self.served_root or self.served_id or self._model_name or None

    def resolve_model(self, meta: dict[str, Any]) -> str | None:
        """CR270 — most specific first: the `root` `/v1/models` reported for the
        slot (vLLM: the real served path), then what the response itself named,
        then the entry's `id`, then the configured id."""
        return (
            self.served_root
            or meta.get("reported_model")
            or self.served_id
            or meta.get("configured_model")
        )

    def price_keys(self, meta: dict[str, Any]) -> list[str]:
        keys: list[str] = []
        for k in (
            self.resolve_model(meta),
            meta.get("reported_model"),
            self.served_id,
            meta.get("configured_model"),
        ):
            if k and k not in keys:
                keys.append(k)
        return keys

    async def discover_served_model(self, timeout_s: float = 5.0) -> bool:
        """CR270 — best-effort `GET /v1/models`; records `root`/`id` for the
        entry matching this slot's configured model (or the only entry).

        Never raises: this is metadata, and a slow or absent endpoint must not
        touch boot or a request. A failure is logged at WARNING and the slot
        keeps resolving to the response-reported / configured id. Returns True
        only when the server answered and listed this slot's model (CR267 WP-24
        reads that to know the root is fresh).
        """
        try:
            resp = await self._client.get("/v1/models", timeout=timeout_s)
            resp.raise_for_status()
            entries = [e for e in (resp.json().get("data") or []) if isinstance(e, dict)]
            match = next((e for e in entries if e.get("id") == self._model_name), None)
            if match is None and len(entries) == 1:
                match = entries[0]
            if match is None:
                logger.warning(
                    "llm_served_model_discovery_no_match",
                    provider=self.name,
                    configured_model=self._model_name,
                    listed=len(entries),
                )
                return False
            root = match.get("root")
            self.served_root = str(root) if root else None
            self.served_id = str(match["id"]) if match.get("id") else None
            self.served_at = time.monotonic()
            logger.info(
                "llm_served_model",
                provider=self.name,
                configured_model=self._model_name,
                served_root=self.served_root,
                served_id=self.served_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "llm_served_model_discovery_failed",
                provider=self.name,
                error=f"{type(exc).__name__}: {str(exc)[:200]}",
                detail="llm_audit.model falls back to the response-reported / configured id",
            )
            return False

    async def read_served_root(self, ttl_s: float) -> str | None:
        """CR267 WP-24 — the `/v1/models` `root`, trusted for `ttl_s` seconds.

        The root names the real served model (the alias this slot is configured
        with is reused across swaps and names nothing), so it is the only thing
        a Room is keyed on. A cached read inside the TTL is returned as is; past
        it the endpoint is read again. If that read fails the stale root is NOT
        returned — the model may have been swapped, and serving a Room produced
        by another model is exactly what the key exists to prevent.

        A hosted ("openai"-kind) slot has no on-disk path, and a host may leave
        `root` empty; its `id` is the vendor's versioned model name rather than a
        local alias, so it stands in. A vLLM slot with no root returns None.
        """
        fresh = (
            self.served_at is not None
            and (time.monotonic() - self.served_at) < ttl_s
        )
        if not fresh:
            await self.discover_served_model()
            fresh = (
                self.served_at is not None
                and (time.monotonic() - self.served_at) < max(ttl_s, 1.0)
            )
        if not fresh:
            return None
        if self.served_root:
            return self.served_root
        if getattr(self, "kind", "vllm") == "openai" and self.served_id:
            return self.served_id
        return None

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
        constraint: OutputConstraint | None = None,
    ) -> AsyncIterator[str]:
        if meta is not None:
            meta.pop("reported_model", None)
            meta["configured_model"] = self._model_name
        # OpenAI-style puts the system message as the first entry of `messages`.
        openai_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        for m in messages:
            openai_messages.append({"role": m.role, "content": m.content})

        effective_max_tokens = max_tokens
        if self._max_tokens_floor is not None:
            effective_max_tokens = max(max_tokens, self._max_tokens_floor)

        body = {
            "model": self._model_name,
            "messages": openai_messages,
            "max_tokens": effective_max_tokens,
            "stream": True,
            # CR141: the terminal SSE frame otherwise carries no `usage` block
            # at all on this family of APIs — this is what turns it on.
            "stream_options": {"include_usage": True},
            **_desk_temperature_fields(),
            **self._extra_body,
        }
        # CR210 — applied AFTER the `**self._extra_body` spread, deliberately.
        # `extra_body` is a constructor-time, per-PROVIDER dict (Qwen's
        # `enable_thinking`); a constraint is per-CALL and per-prompt, and a
        # provider-level default must never be able to silence one call's
        # grammar. The reverse order would let a stray
        # `extra_body={"response_format": {"type": "text"}}` disable every schema
        # on that provider, with no error anywhere — this CR's own failure mode,
        # self-inflicted.
        if constraint is not None:
            body.update(_constraint_request_fields(constraint))
        if meta is not None:
            _apply_call_overrides(body, meta)

        # CR272 — retry TRANSIENT failures, and only before the first chunk
        # has been handed to the caller: once a chunk is out the reply is
        # partly delivered and a re-issue would duplicate or contradict it.
        # With `_max_retries == 0` (every slot that has not opted in) the first
        # attempt is also the last, so a transport error propagates exactly as
        # it always did and a non-200 reaches the sentinel path untouched.
        attempt = 0
        while True:
            yielded = False
            reason: str
            try:
                async with contextlib.aclosing(
                    self._stream_once(
                        body, meta, raise_transient=attempt < self._max_retries
                    )
                ) as inner:
                    async for chunk in inner:
                        yielded = True
                        yield chunk
                return
            except _TransientProviderError as exc:
                reason = exc.reason
            except httpx.TransportError as exc:
                if yielded or attempt >= self._max_retries:
                    raise
                reason = f"{type(exc).__name__}: {str(exc) or 'no detail'}"[:200]
            attempt += 1
            delay = self._retry_backoff_s * (2 ** (attempt - 1))
            logger.warning(
                f"{self.name}_transient_retry",
                attempt=attempt,
                max_retries=self._max_retries,
                reason=reason,
                delay_s=delay,
            )
            await asyncio.sleep(delay)

    async def _stream_once(
        self,
        body: dict[str, Any],
        meta: dict[str, Any] | None,
        *,
        raise_transient: bool,
    ) -> AsyncIterator[str]:
        """One attempt at the request. `raise_transient` turns a 429/5xx into
        `_TransientProviderError` (before any chunk exists) so the retry loop in
        `stream_chat` can decide; False keeps the sentinel path below."""
        async with self._client.stream("POST", "/v1/chat/completions", json=body) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                detail = err_body.decode()[:500]
                logger.error(
                    f"{self.name}_error",
                    status=resp.status_code,
                    body=detail,
                )
                if raise_transient and (
                    resp.status_code == 429 or resp.status_code >= 500
                ):
                    raise _TransientProviderError(f"HTTP {resp.status_code}")
                # RETRO-SECURITY MAJOR-2 (round 2) — the auditor's exact
                # probe: this is the branch that fires on a real vLLM/OpenAI-
                # compatible outage (DEF413's shape), and it used to yield
                # only the sentinel TEXT with no `meta["stream_error"]` write
                # — Brief and 1-on-1 charged a credit for it because neither
                # route had anything structural to check. Same key the
                # in-band frame below already sets, so one check downstream
                # covers both shapes.
                if meta is not None:
                    meta["stream_error"] = f"HTTP {resp.status_code}: {detail}"
                    # CR272 — the structural marker the gateway's failover and
                    # the Room's restart key on: the exchange failed at the
                    # provider (non-200), as opposed to DEF376's in-band frame
                    # (a refused request), which a second provider would not fix.
                    meta["stream_error_status"] = resp.status_code
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
                except Exception as e:
                    logger.warn(
                        f"{self.name}_chunk_parse_failed", error=str(e), line=line[:200]
                    )
                    continue

                # DEF376 — an IN-BAND error frame.
                #
                # This server answers a REFUSED request mid-stream with HTTP 200
                # and a single SSE frame `{"error": {"message": …, "code": 400}}`
                # followed by `[DONE]`. A malformed decoding grammar is the
                # reproducible case (verified 2026-08-25 against ami-llm on vLLM
                # 0.23.1; the NON-streaming path returns a real HTTP 400, and we
                # always stream — so the status-code guard above never fires).
                #
                # The frame carries no `choices`, so before this it fell straight
                # through the `if not choices: continue` guard below and the whole
                # call presented as a clean, empty answer: nothing yielded, no
                # `finish_reason`, and `record_llm_call` handed `response_text=
                # None, error=None`. A refusal was byte-for-byte indistinguishable
                # from a model with nothing to say, and `_parse_pm_verdict` would
                # fail safe to PASS with nothing anywhere to grep for. Pre-existing
                # for EVERY in-band error, not only grammar ones — which is why
                # this is a defect and not a line of CR210.
                #
                # Checked before the CR141 `usage` block for the same reason that
                # block runs before the `choices` guard: an error frame has no
                # usage and no choices, and nothing else in it is meaningful.
                err = obj.get("error")
                if err:
                    detail = err.get("message") if isinstance(err, dict) else err
                    detail = str(detail or err)[:500]
                    logger.error(
                        f"{self.name}_stream_error",
                        error=detail,
                        channel="in-band SSE error frame (HTTP 200)",
                    )
                    if meta is not None:
                        # DEF125's `finish_reason` is deliberately NOT written.
                        # It means "how the MODEL stopped", normalised across
                        # providers; here the model never ran. A sixth value in
                        # that channel would reach four call sites that test it
                        # with `== "length"`. `stream_error` present and
                        # `finish_reason` absent is already unambiguous.
                        meta["stream_error"] = detail
                    yield (
                        f"\n\n[AMI error: the upstream provider ({self.name}) "
                        f"refused this request mid-stream. Check backend logs.]"
                    )
                    return

                # CR270 — the model the server says answered (first frame wins).
                if meta is not None and "reported_model" not in meta:
                    reported = obj.get("model")
                    if isinstance(reported, str) and reported:
                        meta["reported_model"] = reported

                # CR141: the terminal usage frame's `choices` is EMPTY — this
                # must run before the `if not choices: continue` guard below,
                # or the usage frame is skipped past exactly like DEF125's
                # finish_reason would have been. Isolated in its own
                # try/except so a malformed `usage` sub-object costs only
                # this field, never the delta/finish_reason handling below
                # (CR141 acceptance 3 — usage capture must never break the
                # stream).
                if meta is not None:
                    usage = obj.get("usage")
                    if usage:
                        try:
                            meta["usage"] = _parse_openai_compatible_usage(usage)
                        except Exception as e:
                            logger.warn(
                                f"{self.name}_usage_parse_failed",
                                error=str(e), line=line[:200],
                            )

                choices = obj.get("choices") or []
                if not choices:
                    continue
                try:
                    # DEF125: the terminal `finish_reason` arrives on the
                    # final chunk, whose delta is empty — read it BEFORE the
                    # `content` guard, which would otherwise `continue`
                    # straight past it.
                    if meta is not None:
                        finish = choices[0].get("finish_reason")
                        if finish:
                            meta["finish_reason"] = str(finish)
                    if meta is not None and "request_overrides" in meta:
                        lp = (choices[0].get("logprobs") or {}).get("content")
                        if lp:
                            meta.setdefault("logprobs", []).extend(lp)
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
        timeout_seconds: float | None = None,
        max_tokens_floor: int | None = None,
        enable_thinking: bool = False,
        thinking_max_tokens: int | None = None,
        kind: Literal["vllm", "openai"] = "vllm",
        name: str = "vllm",
        max_retries: int = 0,
        retry_backoff_s: float = 1.0,
        extra_body_override: dict[str, Any] | None = None,
    ) -> None:
        self.kind = kind
        override = extra_body_override or {}
        if kind == "openai":
            # CR272 — a hosted OpenAI-compatible endpoint (DeepInfra). No
            # vLLM-only body field is sent: `chat_template_kwargs` is a vLLM
            # chat-template hook a hosted API may reject or ignore, and the
            # thinking floor exists only to budget for that hook. The grammar
            # claim shrinks to JSON-schema `response_format`, the one spelling
            # the OpenAI API itself defines; the regex `structured_outputs`
            # field is vLLM's and is therefore NOT advertised, so the gateway
            # records such a call `unsupported` instead of sending a field the
            # server may accept and drop (CR210).
            super().__init__(
                name=name,
                base_url=base_url,
                model_name=model_name,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_tokens_floor=max_tokens_floor,
                extra_body={**override},
                supported_constraints=frozenset({"json_schema"}),
                max_retries=max_retries,
                retry_backoff_s=retry_backoff_s,
            )
            return
        # CR259 — when thinking is on, the thinking floor dominates any
        # caller-requested floor (both are "raise max_tokens to at least X";
        # the larger of the two is the binding one).
        floor = max(max_tokens_floor or 0, thinking_max_tokens or 0) or None
        super().__init__(
            name=name,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            # CR211 — see `Settings.vllm_max_tokens_floor`. None when the
            # setting is 0, so a non-reasoning server carries no floor at all
            # rather than a floor of zero that reads as one.
            max_tokens_floor=floor,
            # CR259 — `extra_body` exists for exactly this (CR017 §3). Sent on
            # every call. The kwarg carries the SETTING'S value explicitly,
            # not only when True: `ami-llm`'s server defaults thinking OFF
            # (an explicit false is a no-op there), but `kolibri-1`'s server
            # defaults it ON — measured 2026-10-17, 686 of 850 completion
            # tokens were reasoning with no kwarg, and explicit
            # `enable_thinking: false` took reasoning to zero. Omitting the
            # kwarg when the setting is False made "thinking off" mean
            # "server default" — right on one server, silently wrong on the
            # other.
            extra_body={
                "chat_template_kwargs": {"enable_thinking": enable_thinking},
                **override,
            },
            # CR210 — both verified live against `ami-llm` on vLLM
            # 0.23.1.dev0+g0fc695fc6 on 2026-08-25, under `stream: true`:
            # `response_format` json_schema held a float enum against a direct
            # user instruction to leave it, and `structured_outputs.regex`
            # produced a conforming Trader money block. This set is a claim about
            # a SERVER, not about a class, so it moves only when the server is
            # re-verified — see `_constraint_request_fields` for why an
            # unverified claim here is worse than no claim.
            supported_constraints=frozenset({"json_schema", "regex"}),
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
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


# ── CR272: backup slot + Room failover signalling ─────────────────────────

FALLBACK_PROVIDER_NAME = "vllm_fallback"


@dataclass
class RoomFailoverState:
    """CR272 — the one object a Room run shares with the gateway.

    The Room runner arms it (via `arm_room_failover`) only when a backup slot is
    registered. While armed, the gateway does NOT re-issue a failed call on the
    backup — one Room must never mix two models' arguments — it reports the
    failure here with `trip`. The runner reads `tripped_reason` between desks,
    abandons the attempt and restarts the whole Room with `pinned_provider` set,
    after which every call in the run resolves to that provider.

    A ContextVar (not a parameter) carries it because eight Room call sites and
    several helpers reach the gateway, and a pin that one of them could forget
    would silently put two models in one Room. Tasks spawned under the run
    (the ANALYSTS `gather`, `wait_for`) copy the context and so share this same
    mutable object.
    """

    pinned_provider: str | None = None
    tripped_reason: str | None = None
    tripped_provider: str | None = None

    def trip(self, reason: str, *, provider: str, agent_id: str | None) -> None:
        if self.tripped_reason is not None:
            return
        self.tripped_reason = reason
        self.tripped_provider = provider
        logger.warning(
            "llm_failover_requested",
            provider=provider,
            reason=reason,
            agent_id=agent_id,
            detail="the Room will restart on the backup slot",
        )


_ROOM_FAILOVER: contextvars.ContextVar[RoomFailoverState | None] = (
    contextvars.ContextVar("ami_room_failover", default=None)
)


def arm_room_failover(state: RoomFailoverState | None) -> None:
    """Install (or, with None, remove) the Room failover state for this context."""
    _ROOM_FAILOVER.set(state)


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
    _SINGLE_MODEL_SETTING: dict[str, str] = {
        "vllm": "vllm_model",
        "kimi": "kimi_model",
        # CR217 — a single self-hosted model, like vllm: every tier must resolve
        # to it, or status() would advertise Anthropic's tier aliases for a
        # provider that has never heard of them.
        "glm": "glm_model",
        # CR281 — every registered single-model slot resolves its tiers to ITS
        # configured model; without these, status() advertised Anthropic's tier
        # aliases for a slot that has never heard of them.
        "vllm_fallback": "vllm_fallback_model",
        "deepseek": "deepseek_model",
        "qwen": "qwen_model",
        "gemini": "gemini_model",
    }

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockProvider()}
        # DEF413 — last transport outcome per provider name. In-process and
        # deliberately not persisted: it describes what THIS container observed,
        # and a restart genuinely has no evidence yet ("unknown"), which is a
        # different claim from "unreachable" and must not be able to
        # masquerade as one by outliving the process that measured it.
        self._transport: dict[str, dict[str, Any]] = {}
        self._discovery_task: asyncio.Task[None] | None = None

        # CR281 — slots configured (key/URL present) but outside
        # LLM_PROVIDER_ALLOWLIST. They are not registered below, so no routing,
        # tier, fallback, force-provider or review path can reach them. Names
        # only are ever logged or reported — never a key or URL.
        self._allowlist: tuple[str, ...] = tuple(settings.llm_provider_allowlist)
        self._blocked: tuple[str, ...] = tuple(blocked_slots(settings))
        self._log_allowlist_posture()

        if settings.vllm_base_url and "vllm" not in self._blocked:
            self._providers["vllm"] = VLLMProvider(
                base_url=settings.vllm_base_url,
                model_name=settings.vllm_model,
                api_key=settings.vllm_api_key or None,
                max_tokens_floor=settings.vllm_max_tokens_floor or None,
                timeout_seconds=settings.vllm_request_timeout_s,
                enable_thinking=settings.vllm_enable_thinking,
                thinking_max_tokens=settings.vllm_thinking_max_tokens or None,
                kind=settings.vllm_kind,
                # CR272 — a "vllm"-kind primary is retried only when there is a
                # backup to fall over to; with none, an on-prem outage would
                # just gain retry delay, and "no backup configured" must change
                # nothing. A hosted ("openai") primary always retries.
                max_retries=(
                    settings.llm_transient_retries
                    if settings.vllm_kind == "openai"
                    or (
                        settings.vllm_fallback_base_url
                        and FALLBACK_PROVIDER_NAME not in self._blocked
                    )
                    else 0
                ),
                retry_backoff_s=settings.llm_retry_backoff_s,
                extra_body_override=parse_extra_body(
                    "VLLM_EXTRA_BODY_JSON", settings.vllm_extra_body_json
                ),
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider="vllm",
                base_url=settings.vllm_base_url,
                model=settings.vllm_model,
                # CR211 — logged for the same reason Kimi's is: the floor
                # silently rewrites every caller's max_tokens, so which value
                # was in force has to be recoverable from the boot log.
                max_tokens_floor=settings.vllm_max_tokens_floor,
                # CR259 — same recoverability reason as the floor: thinking
                # rewrites every call's latency profile, so the boot log must
                # show whether it was in force.
                enable_thinking=settings.vllm_enable_thinking,
                thinking_max_tokens=settings.vllm_thinking_max_tokens,
                # DEF389 — same reason as the floor: which transport budget
                # was in force has to be recoverable from the boot log, since
                # exceeding it is silent at the call site.
                request_timeout_s=settings.vllm_request_timeout_s,
                kind=settings.vllm_kind,
            )
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="vllm",
                reason=self._skip_reason("vllm", "no VLLM_BASE_URL in env"),
            )

        # CR272 — the backup slot. Never in `_PREFERENCE`: it is reached only by
        # failover (a single call re-issued, or a Room restarted pinned to it).
        # Its own floor/thinking knobs are not borrowed from the primary for a
        # hosted ("openai") backup — those are tuned to the primary's model.
        if settings.vllm_fallback_base_url and FALLBACK_PROVIDER_NAME not in self._blocked:
            _fb_vllm_kind = settings.vllm_fallback_kind == "vllm"
            self._providers[FALLBACK_PROVIDER_NAME] = VLLMProvider(
                base_url=settings.vllm_fallback_base_url,
                model_name=settings.vllm_fallback_model,
                api_key=settings.vllm_fallback_api_key or None,
                max_tokens_floor=(
                    (settings.vllm_max_tokens_floor or None) if _fb_vllm_kind else None
                ),
                timeout_seconds=settings.vllm_request_timeout_s,
                enable_thinking=settings.vllm_enable_thinking if _fb_vllm_kind else False,
                thinking_max_tokens=(
                    (settings.vllm_thinking_max_tokens or None) if _fb_vllm_kind else None
                ),
                kind=settings.vllm_fallback_kind,
                name=FALLBACK_PROVIDER_NAME,
                max_retries=settings.llm_transient_retries,
                retry_backoff_s=settings.llm_retry_backoff_s,
                extra_body_override=parse_extra_body(
                    "VLLM_FALLBACK_EXTRA_BODY_JSON", settings.vllm_fallback_extra_body_json
                ),
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider=FALLBACK_PROVIDER_NAME,
                base_url=settings.vllm_fallback_base_url,
                model=settings.vllm_fallback_model,
                kind=settings.vllm_fallback_kind,
                role="failover only — not in the preference order",
            )
            if "vllm" not in self._providers:
                logger.warning(
                    "llm_gateway_backup_without_primary",
                    detail=(
                        "VLLM_FALLBACK_BASE_URL is set but VLLM_BASE_URL is not: "
                        "the backup is never chosen by preference order, so it "
                        "serves nothing unless another primary is configured"
                    ),
                )

        if settings.anthropic_api_key and "anthropic" not in self._blocked:
            self._providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
            logger.info("llm_gateway_provider_registered", provider="anthropic")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="anthropic",
                reason=self._skip_reason("anthropic", "no ANTHROPIC_API_KEY in env"),
            )

        if settings.kimi_api_key and "kimi" not in self._blocked:
            self._providers["kimi"] = OpenAICompatibleProvider(
                name="kimi",
                base_url=settings.kimi_base_url,
                model_name=settings.kimi_model,
                api_key=settings.kimi_api_key,
                max_tokens_floor=settings.kimi_max_tokens_floor,
                extra_body=parse_extra_body("KIMI_EXTRA_BODY_JSON", settings.kimi_extra_body_json),
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider="kimi",
                base_url=settings.kimi_base_url,
                model=settings.kimi_model,
                max_tokens_floor=settings.kimi_max_tokens_floor,
            )
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="kimi",
                reason=self._skip_reason("kimi", "no KIMI_API_KEY in env"),
            )

        # CR141 (build half of CR017 §3/§5 step 2): DeepSeek/Qwen/Gemini, all
        # OpenAI-compatible, registered the same way as Kimi above — none of
        # these are in `_PREFERENCE`, so registering them changes nothing
        # about which provider wins today; they only get selected via
        # `provider_policy.pick_provider` (not consumed by any live call site
        # yet) or a manual `LLM_FORCE_PROVIDER` override.
        if settings.deepseek_api_key and "deepseek" not in self._blocked:
            self._providers["deepseek"] = OpenAICompatibleProvider(
                name="deepseek",
                base_url=settings.deepseek_base_url,
                model_name=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
                extra_body=parse_extra_body(
                    "DEEPSEEK_EXTRA_BODY_JSON", settings.deepseek_extra_body_json
                ),
            )
            logger.info("llm_gateway_provider_registered", provider="deepseek")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="deepseek",
                reason=self._skip_reason("deepseek", "no DEEPSEEK_API_KEY in env"),
            )

        if settings.dashscope_api_key and "qwen" not in self._blocked:
            self._providers["qwen"] = OpenAICompatibleProvider(
                name="qwen",
                base_url=settings.qwen_base_url,
                model_name=settings.qwen_model,
                api_key=settings.dashscope_api_key,
                # CR017 §3: forces the fast/non-thinking response mode.
                extra_body={
                    "enable_thinking": False,
                    **parse_extra_body("QWEN_EXTRA_BODY_JSON", settings.qwen_extra_body_json),
                },
            )
            logger.info("llm_gateway_provider_registered", provider="qwen")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="qwen",
                reason=self._skip_reason("qwen", "no DASHSCOPE_API_KEY in env"),
            )

        # CR217 — GLM-5.3-Flash-NVFP4, candidate Room model under head-to-head
        # evaluation against the incumbent vLLM model. Deliberately absent from
        # `_PREFERENCE`: registering it must not change which provider serves
        # live traffic. It is reached only via `LLM_FORCE_PROVIDER=glm` (the
        # mechanism `_active_provider_name` documents for exactly this) or
        # `provider_policy.pick_provider`.
        if settings.glm_base_url and "glm" not in self._blocked:
            self._providers["glm"] = OpenAICompatibleProvider(
                name="glm",
                base_url=settings.glm_base_url,
                model_name=settings.glm_model,
                api_key=settings.glm_api_key or None,
                max_tokens_floor=settings.glm_max_tokens_floor or None,
                extra_body=parse_extra_body("GLM_EXTRA_BODY_JSON", settings.glm_extra_body_json),
            )
            logger.info(
                "llm_gateway_provider_registered",
                provider="glm",
                base_url=settings.glm_base_url,
                model=settings.glm_model,
                max_tokens_floor=settings.glm_max_tokens_floor,
            )
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="glm",
                reason=self._skip_reason("glm", "no GLM_BASE_URL in env"),
            )

        if settings.google_ai_api_key and "gemini" not in self._blocked:
            self._providers["gemini"] = OpenAICompatibleProvider(
                name="gemini",
                base_url=settings.gemini_base_url,
                model_name=settings.gemini_model,
                api_key=settings.google_ai_api_key,
                extra_body=parse_extra_body(
                    "GEMINI_EXTRA_BODY_JSON", settings.gemini_extra_body_json
                ),
            )
            logger.info("llm_gateway_provider_registered", provider="gemini")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="gemini",
                reason=self._skip_reason("gemini", "no GOOGLE_AI_API_KEY in env"),
            )

    def _skip_reason(self, slot: str, default: str) -> str:
        return "blocked by LLM_PROVIDER_ALLOWLIST" if slot in self._blocked else default

    def _log_allowlist_posture(self) -> None:
        """CR281 — degrade loudly. One error-level event naming every provider
        that is configured but not allowed (names only), so a re-enabled or
        forgotten vendor key is visible in the boot log instead of silent."""
        if self._blocked:
            logger.error(
                "llm_provider_blocked_by_allowlist",
                blocked=list(self._blocked),
                allowlist=list(self._allowlist),
                detail=(
                    "these providers have a key/URL configured but are NOT in "
                    "LLM_PROVIDER_ALLOWLIST; the gateway will not register or use them"
                ),
            )
        if self._allowlist and not any(
            s in self._allowlist and s != "mock" for s in configured_slots(settings)
        ):
            logger.error(
                "llm_allowlist_no_real_provider",
                allowlist=list(self._allowlist),
                detail=(
                    "LLM_PROVIDER_ALLOWLIST is set but none of its slots is "
                    "configured: the gateway has only the mock provider"
                ),
            )

    def has_real_provider(self) -> bool:
        """Is a non-mock provider REGISTERED.

        Registration is a config fact: a provider registers when its settings
        are present, never when it answers. DEF413 is what that costs when the
        two are conflated — the vLLM host lost its route and this kept
        returning True, so `/v1/llm/status`, `/v1/ready` and a promotion smoke
        check all read healthy with no model behind them. Kept as-is because
        callers that fall back to a scripted path (`agent_runner`,
        `brief_engine`, `portfolio_finding`) genuinely want "is one configured";
        `provider_liveness()` is the separate question of whether it answers.
        """
        return any(name != "mock" for name in self._providers)

    def note_transport_outcome(
        self, provider: str, *, ok: bool, error: str | None = None
    ) -> None:
        """Record what the wire just did, for `provider`.

        DEF413. The gateway sees every call's transport outcome already; this
        keeps the last one per provider so the fact survives to `status()`
        instead of dying in a log line. Deliberately NOT a health probe: no
        request is made on its behalf, so a health endpoint can never fan out
        to a GPU host, and nothing here runs on the read path.

        `ok` is a TRANSPORT judgement, not a quality one. A model that answers
        badly is reachable; only a failure to complete the exchange counts as
        unreachable, because the question this answers is "is anything there".
        """
        self._transport[provider] = {
            "ok": ok,
            "at": datetime.now(timezone.utc),
            "error": (error or None) if not ok else None,
        }

    def provider_liveness(self, provider: str | None = None) -> dict[str, object]:
        """What the last call to `provider` (default: the active one) did.

        Three states, and the third is the point: `ok` / `failed` / **`unknown`**
        — no call has been made since this process started, so the gateway has
        no evidence either way. `unknown` must never be read as healthy (that
        is DEF413 restated) and must never be read as broken either, or every
        cold container fails its own readiness gate before serving one request.
        The caller decides what an absence of evidence is worth; see
        `readiness._probe_llm`, which gates on `failed` alone.
        """
        name = provider or self._active_provider_name()
        seen = self._transport.get(name)
        if seen is None:
            return {"provider": name, "state": "unknown", "as_of": None, "error": None}
        return {
            "provider": name,
            "state": "ok" if seen["ok"] else "failed",
            "as_of": seen["at"].isoformat(),
            "error": seen["error"],
        }

    async def check_prefix_cache_at_startup(self) -> None:
        """CR077 Phase 0 second guard — no-op when vLLM isn't registered."""
        provider = self._providers.get("vllm")
        # CR272 — a hosted ("openai") slot has no `/metrics` to scrape.
        if isinstance(provider, VLLMProvider) and provider.kind == "vllm":
            await provider.log_prefix_cache_status()

    def has_backup_provider(self) -> bool:
        """CR272 — is the failover slot registered. Config fact, not liveness."""
        return FALLBACK_PROVIDER_NAME in self._providers

    async def discover_served_models(self, timeout_s: float = 5.0) -> None:
        """CR270 — one best-effort `GET /v1/models` per OpenAI-compatible slot.

        Each probe swallows its own failure (`discover_served_model`); the outer
        guard exists so that nothing here can ever surface to a caller.
        """
        probes = [
            p.discover_served_model(timeout_s)
            for p in self._providers.values()
            if isinstance(p, OpenAICompatibleProvider)
        ]
        if not probes:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*probes, return_exceptions=True),
                timeout=timeout_s + 3.0,
            )
        except Exception as exc:  # wait_for timeout, cancellation of a probe
            logger.warning("llm_served_model_discovery_failed", error=repr(exc)[:200])

    def start_served_model_discovery(self) -> None:
        """CR270 — kick the probe off as a background task so it can never delay
        or fail boot. Needs a running loop (called from the lifespan)."""
        self._discovery_task = asyncio.create_task(self.discover_served_models())

    def served_model(self, provider_name: str | None = None) -> str | None:
        """CR270 — the most specific model id for [provider_name] (default: the
        provider a call would hit now): the `/v1/models` root if it was read,
        else its id, else the configured model. Keyed on by WP-24's Room key."""
        name = provider_name or self._active_provider_name()
        provider = self._providers.get(name)
        return provider.static_model_identity() if provider is not None else None

    async def room_model_root(self, provider_name: str | None = None) -> str | None:
        """CR267 WP-24 — the model root a Room started now would run on (the
        active provider, or `provider_name` such as the failover slot), read from
        `/v1/models` and cached for `room_model_root_ttl_s`. None when it cannot
        be read: the caller then runs the Room unbanked and says so."""
        name = provider_name or self._active_provider_name()
        provider = self._providers.get(name)
        if provider is None:
            return None
        try:
            return await provider.read_served_root(float(settings.room_model_root_ttl_s))
        except Exception as exc:
            logger.warning(
                "room_model_root_read_failed",
                provider=name,
                error=f"{type(exc).__name__}: {str(exc)[:200]}",
            )
            return None

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

    def _review_desk(self) -> str:
        """The provider the CIO actually ran on: the slot a failed-over Room is
        pinned to (CR272), else the active provider."""
        state = _ROOM_FAILOVER.get()
        if state is not None and state.pinned_provider in self._providers:
            return state.pinned_provider  # type: ignore[return-value]
        return self._active_provider_name()

    def pick_review_provider(self) -> str | None:
        """CR247 Phase 4 — the provider a second-pass verdict review runs on.

        Preferably a DIFFERENT model than the CIO, so a model-correlated CIO
        error cannot silently repeat in its own audit (D18). Order, with
        `anthropic` and the mock never eligible (Saiful 2026-11-19: no Anthropic
        model anywhere in the app — enforced here, not by leaving the key unset;
        the mock answers nothing real, so auditing against it is theater):

        1. The first REGISTERED provider in `_PREFERENCE` other than the desk's
           (today: Kimi, when keyed).
        2. DEF493 — the CR272 backup slot (`vllm_fallback`), never in
           `_PREFERENCE`. Offered only if its model identity differs from the
           desk's; a backup on the same model is not an independent audit.
        3. DEF493 — the desk's own provider. A same-model audit is still a
           second, differently-prompted pass (on-prem Alpha has one model; a
           hosted Beta without a backup has one), but it is NOT an independent
           opinion: `review_is_independent` is False for it and the caller
           records and logs that, so it is never presented as one.

        A provider that tripped this Room's failover (`tripped_provider`) is
        just-failed and is not asked to audit it: a Room restarted on the
        backup is reviewed on the backup (step 3), not on the dead primary.

        None when no real, non-Anthropic provider is registered: the caller
        degrades loudly (error log + `skipped_reason` on the journal record,
        verdict unchanged) rather than skipping silently (CR040).
        """
        desk = self._review_desk()
        state = _ROOM_FAILOVER.get()
        tripped = state.tripped_provider if state is not None else None
        for name in self._PREFERENCE:
            if name in ("mock", "anthropic") or name == desk or name == tripped:
                continue
            if name in self._providers:
                return name
        if (
            desk != FALLBACK_PROVIDER_NAME
            and FALLBACK_PROVIDER_NAME in self._providers
            and FALLBACK_PROVIDER_NAME != tripped
        ):
            desk_provider = self._providers.get(desk)
            desk_identity = (
                desk_provider.static_model_identity() if desk_provider else None
            )
            backup_identity = self._providers[
                FALLBACK_PROVIDER_NAME
            ].static_model_identity()
            if backup_identity and backup_identity != desk_identity:
                return FALLBACK_PROVIDER_NAME
        if desk not in ("mock", "anthropic") and desk in self._providers:
            return desk
        return None

    def review_is_independent(self, review_provider: str) -> bool:
        """DEF493 — False when [review_provider] is the desk's own model (the
        same-model review of `pick_review_provider` step 3)."""
        desk = self._review_desk()
        if review_provider == desk:
            return False
        a = self._providers.get(review_provider)
        b = self._providers.get(desk)
        ia = a.static_model_identity() if a else None
        ib = b.static_model_identity() if b else None
        return not (ia and ib and ia == ib)

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
        backup_status: dict[str, object] = (
            {"backup_provider": FALLBACK_PROVIDER_NAME}
            if self.has_backup_provider()
            else {}
        )
        return {
            "providers_registered": sorted(self._providers.keys()),
            # CR281 — the allow-list in force ([] = unrestricted) and the slots
            # that are configured but kept out of the gateway by it.
            "allowlist": list(self._allowlist),
            "configured_but_blocked": list(self._blocked),
            "active_provider": active,
            **backup_status,
            "has_real_provider": self.has_real_provider(),
            # DEF413 — the second, separate fact. `has_real_provider` says a
            # provider is CONFIGURED; this says whether the last call to the
            # active one actually completed. They were one name for two claims,
            # and the operator surface read healthy through an outage because of
            # it. Never a call: this is the recorded outcome of traffic that
            # already happened.
            "active_provider_liveness": self.provider_liveness(active),
            "tier_to_model": tier_to_model,
        }

    def _pick_provider(
        self,
        locale: str,
        model_tier: ModelTier,
        plan: Plan | None = None,
        agent_id: AgentId | None = None,
    ) -> LLMProvider:
        """Pick a provider.

        CR141: when BOTH `plan` and `agent_id` are supplied, first consult
        `provider_policy.pick_provider` for a routing preference — but only
        ACT on it if the routed provider is actually registered (a missing
        key must never surface as an error, matching every other
        "presence of key turns it on" provider in this file). Falls through
        to `_active_provider_name()`'s existing fixed-order logic otherwise —
        the SAME logic this method used before CR141, unconditionally, when
        either argument is omitted. No caller passes `plan`/`agent_id` yet
        (see `provider_policy`'s module docstring for why), so this preserves
        today's behaviour exactly until a call site opts in — CR141
        acceptance 4.

        Local import breaks a circular dependency: `provider_policy` imports
        `ModelTier` from this module.
        """
        if plan is not None and agent_id is not None:
            from app.services.provider_policy import pick_provider as _pick_routed

            routed = _pick_routed(plan, agent_id, model_tier)
            if routed is not None and routed in self._providers:
                return self._providers[routed]
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
        plan: Plan | None = None,
        agent_id: AgentId | None = None,
        constraint: OutputConstraint | None = None,
        provider_name: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream one chat completion.

        CR247 Phase 4 — [provider_name] pins ONE call to a named provider (the
        second-pass verdict review uses it to run on the fallback provider, a
        different model than the CIO). The name must be REGISTERED: the only
        call site resolves it through `pick_review_provider()`, which returns
        registered names or None (the caller then skips loudly rather than
        calling here). An unregistered name is a programming error and raises,
        because falling through to the normal pick would audit a verdict on
        the very model it was meant to be independent of — silently, which is
        the failure the pin exists to prevent. None keeps today's behaviour
        exactly (`_pick_provider` decides).

        CR272 — failover. Only when a backup slot (`vllm_fallback`) is
        registered, and never for a call pinned by [provider_name]:

        - OUTSIDE a Room (1-on-1, Brief, Concierge, ...): a call whose provider
          fails before yielding a chunk (a transport error, or a non-200 after
          the provider's own retries) is re-issued ONCE on the backup. Logged
          `llm_failover`; `meta["failover"]` names from/to/reason, and the
          backup's own `llm_audit` row carries `provider="vllm_fallback"`.
        - INSIDE a Room (a `RoomFailoverState` is armed on the context): the
          call is NOT re-issued — one Room must never mix two models. The
          failure is reported to the state, the Room runner restarts the whole
          discussion pinned to the backup, and every call after that resolves
          to the backup here.
        """
        state = _ROOM_FAILOVER.get()
        if provider_name is not None:
            if provider_name not in self._providers:
                raise ValueError(
                    f"stream_chat: provider {provider_name!r} is not registered"
                )
            provider = self._providers[provider_name]
        elif state is not None and state.pinned_provider in self._providers:
            provider = self._providers[state.pinned_provider]  # type: ignore[index]
        else:
            provider = self._pick_provider(
                locale, model_tier, plan=plan, agent_id=agent_id
            )
        # DEF125: always give the provider somewhere to report the stop reason,
        # even when the caller did not ask for it — the length-stop warning below
        # is what makes a silent truncation visible on EVERY flow (room,
        # one-on-one, brief, Concierge), not only the ones that opted in.
        call_meta: dict[str, Any] = meta if meta is not None else {}
        call_kwargs: dict[str, Any] = dict(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=model_tier,
            locale=locale,
            max_tokens=max_tokens,
            audit_user_id=audit_user_id,
            audit_agent_id=audit_agent_id,
            audit_flow=audit_flow,
            call_meta=call_meta,
            constraint=constraint,
        )

        backup = self._providers.get(FALLBACK_PROVIDER_NAME)
        room_armed = (
            state is not None
            and provider_name is None
            and state.pinned_provider is None
        )
        can_failover = (
            state is None
            and provider_name is None
            and backup is not None
            and provider is not backup
            and provider.name != "mock"
        )
        if not room_armed and not can_failover:
            async with contextlib.aclosing(
                self._stream_chat_on(provider, **call_kwargs)
            ) as only:
                async for chunk in only:
                    yield chunk
            return

        yielded = False
        failure: str | None = None
        try:
            async with contextlib.aclosing(
                self._stream_chat_on(provider, **call_kwargs)
            ) as first:
                async for chunk in first:
                    status = call_meta.get("stream_error_status")
                    if not yielded and status is not None:
                        failure = f"HTTP {status}"
                        if room_armed:
                            assert state is not None
                            state.trip(
                                failure, provider=provider.name, agent_id=audit_agent_id
                            )
                        else:
                            # Drop the provider's `[AMI error: ...]` sentinel: it
                            # is the failed attempt's text, not the caller's reply.
                            break
                    yielded = True
                    yield chunk
        except asyncio.CancelledError:
            # The Room's per-desk guard (`wait_for`) cancelling a call that has
            # produced nothing is a provider that hung. Reported, not retried.
            if room_armed and not yielded:
                assert state is not None
                state.trip(
                    "no first chunk before the desk guard fired",
                    provider=provider.name,
                    agent_id=audit_agent_id,
                )
            raise
        except (httpx.HTTPError, OSError) as exc:
            if yielded:
                raise
            failure = f"{type(exc).__name__}: {str(exc) or 'no detail'}"[:200]
            if room_armed:
                assert state is not None
                state.trip(failure, provider=provider.name, agent_id=audit_agent_id)
                raise

        if failure is None or room_armed:
            return

        assert backup is not None
        logger.warning(
            "llm_failover",
            surface=audit_flow or "unknown",
            from_provider=provider.name,
            to=backup.name,
            reason=failure,
            agent_id=audit_agent_id,
        )
        call_meta.pop("stream_error", None)
        call_meta.pop("stream_error_status", None)
        call_meta["failover"] = {
            "from": provider.name,
            "to": backup.name,
            "reason": failure,
        }
        async with contextlib.aclosing(
            self._stream_chat_on(backup, **call_kwargs)
        ) as second:
            async for chunk in second:
                yield chunk

    async def _stream_chat_on(
        self,
        provider: LLMProvider,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: ModelTier,
        locale: str,
        max_tokens: int,
        audit_user_id: object,
        audit_agent_id: str | None,
        audit_flow: str | None,
        call_meta: dict[str, Any],
        constraint: OutputConstraint | None,
    ) -> AsyncIterator[str]:
        """One call on one provider: capability gate, stream, audit row.

        This is the body `stream_chat` always had; CR272 split it out so the
        failover wrapper can run it twice (once per provider) and each attempt
        still writes its own `llm_audit` row.
        """
        import time
        from app.services.audit import record_llm_call
        # CR158 — local, like the import above: prompt_version imports the
        # prompt builders, which import this module's GROUNDING_DIRECTIVE.
        from app.services.prompt_version import prompt_version_for


        # CR210 — the capability gate. A decoding grammar is either put on the
        # wire by a provider that enforces it, or it is DROPPED and said so out
        # loud. It is never sent to a provider that would ignore it: `guided_json`
        # proved that a field this server does not implement comes back HTTP 200
        # with a prose answer, which is indistinguishable from enforcement at
        # every layer above. There is no runtime fallback in this gateway — one
        # provider is picked per call — so "cannot enforce" cannot mean "try
        # someone else"; it means run unconstrained and record that fact.
        #
        # ABSENCE of the `constraint` key in `call_meta` means no grammar was
        # REQUESTED, never "requested and dropped". That is 'unsupported', and the
        # two must not read alike or "the PM verdict parsed" means two different
        # things depending on who answered.
        effective_constraint = constraint
        if constraint is not None:
            enforced = constraint.kind in provider.supported_constraints
            call_meta["constraint"] = {
                "name": constraint.name,
                "kind": constraint.kind,
                "provider": provider.name,
                "status": "enforced" if enforced else "unsupported",
            }
            if not enforced:
                effective_constraint = None
                logger.warning(
                    "llm_constraint_unsupported",
                    provider=provider.name,
                    constraint=constraint.name,
                    kind=constraint.kind,
                    agent_id=audit_agent_id,
                    flow=audit_flow,
                    detail=(
                        "the reply is UNCONSTRAINED; CR143's tolerant parser is "
                        "the only contract on this call"
                    ),
                )
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
        try:
            async for chunk in provider.stream_chat(
                system_prompt=effective_system_prompt,
                messages=messages,
                model_tier=model_tier,
                max_tokens=max_tokens,
                meta=call_meta,
                constraint=effective_constraint,
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
                    # CR210 — a CONSTRAINED call that hits the ceiling is a schema
                    # failure, not a slow success: the grammar guaranteed a shape
                    # the budget then made unreachable, so the reply is
                    # unparseable rather than merely short. Fields rather than a
                    # sibling event because it is the SAME physical event, and two
                    # names for one event makes "how often do we truncate" a
                    # two-query question with one of the two forgotten. The
                    # aggregate lives in llm_audit.constraint_status='truncated'.
                    constrained=effective_constraint is not None,
                    constraint=(
                        effective_constraint.name if effective_constraint else None
                    ),
                )
            # CR210 — settle the TRANSPORT half of the outcome taxonomy. The
            # gateway knows what happened on the wire; whether the reply also
            # satisfied the parser it was written for is only knowable at the call
            # site, and is logged there. Deliberately not written back to this row
            # afterwards: an audit row UPDATEd after the fact is a row whose
            # meaning depends on when you read it.
            constraint_meta = call_meta.get("constraint") or {}
            constraint_status = constraint_meta.get("status")
            if constraint_status == "enforced":
                if call_meta.get("stream_error"):
                    # DEF376's frame, on a call that carried a grammar. NOT
                    # sniffed out of the message text: "we sent a grammar AND the
                    # server refused in-band" is the whole signal, and the raw
                    # message reaches `error` below either way. String-matching
                    # "Grammar error:" would be a contract with a log line, which
                    # is not a contract.
                    constraint_status = "rejected"
                    logger.error(
                        "llm_constraint_rejected",
                        provider=provider.name,
                        constraint=constraint_meta.get("name"),
                        kind=constraint_meta.get("kind"),
                        agent_id=audit_agent_id,
                        flow=audit_flow,
                        error=str(call_meta.get("stream_error"))[:300],
                        detail=(
                            "the server refused the grammar and returned no "
                            "content — a code defect, not a runtime condition"
                        ),
                    )
                elif call_meta.get("finish_reason") == "length":
                    constraint_status = "truncated"
                constraint_meta["status"] = constraint_status
            # DEF376 — an in-band SSE error frame IS an error. Until this line it
            # reached `record_llm_call` as `error=None` with an empty response,
            # i.e. recorded as a clean answer the model simply had nothing to add
            # to. `error_str` is only overwritten when the call did not already
            # raise: a real exception is the more specific fact and keeps priority.
            if error_str is None and call_meta.get("stream_error"):
                error_str = f"stream_error: {str(call_meta['stream_error'])[:400]}"
            # DEF413 — settle the LIVENESS half. Recorded here rather than at
            # the `except` because a stream error is an in-band failure that
            # never raises (DEF376's frame), and both shapes mean the same
            # thing to this question: the exchange did not complete. `buf`
            # is not consulted — an empty-but-clean answer is a reachable
            # provider with nothing to say, which is a quality problem, not a
            # transport one, and conflating the two is how a working host gets
            # reported dead.
            self.note_transport_outcome(
                provider.name, ok=error_str is None, error=error_str
            )
            # CR141: whatever the provider wrote into call_meta["usage"] (see
            # AnthropicProvider / OpenAICompatibleProvider above). `.get()`
            # on a missing/partial dict yields None per field, never 0 — a
            # provider that never wrote `usage` at all (no frame, or every
            # frame malformed) records all four columns NULL, exactly like a
            # provider that reported some fields but not others records NULL
            # only for the ones it omitted (CR141 acceptance 2 + 3).
            usage = call_meta.get("usage") or {}
            # CR270 — who served it, and what it cost. Neither may break the
            # audit write: a failure here records NULL for both, loudly.
            served = None
            cost_usd = None
            try:
                from app.services.llm_spend import compute_cost_usd

                served = provider.resolve_model(call_meta)
                cost_usd = compute_cost_usd(
                    provider.price_keys(call_meta),
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                )
            except Exception:
                logger.exception("llm_cost_compute_failed", provider=provider.name)
            # CR158: stamp which prompt generation this call used, so a later
            # measurement can partition by it instead of reconstructing epoch
            # boundaries from git SHAs by hand — the manual step that put a
            # wrong reformatter rate into CR143. Cached per agent; None for a
            # non-agent flow (Concierge, the reformatter) and on any failure.
            await asyncio.to_thread(
                record_llm_call,
                user_id=audit_user_id if audit_user_id else None,
                agent_id=audit_agent_id,
                flow=audit_flow,
                tier=model_tier,
                provider=provider.name,
                locale=locale,
                system_prompt=effective_system_prompt,
                prompt_version=prompt_version_for(audit_agent_id),
                messages=[{"role": m.role, "content": m.content} for m in messages],
                response_text="".join(buf) if buf else None,
                latency_ms=latency_ms,
                error=error_str,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cache_read_tokens=usage.get("cache_read_tokens"),
                cache_write_tokens=usage.get("cache_write_tokens"),
                constraint_status=constraint_status,
                model=served,
                cost_usd=cost_usd,
            )


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def served_model(provider_name: str | None = None) -> str | None:
    """CR270 — the model id behind [provider_name] (default: the active one).

    Most specific identity known without a call; see `LLMGateway.served_model`.
    """
    return get_llm_gateway().served_model(provider_name)
