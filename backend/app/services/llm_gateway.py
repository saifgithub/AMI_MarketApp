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
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import settings
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
        self._extra_body = extra_body or {}
        # CR130: reasoning-style providers (Kimi) spend `max_tokens` on
        # invisible chain-of-thought before any visible content, so the
        # Room's per-agent budgets (tuned for vLLM, a non-reasoning model)
        # starve them. A floor here raises whatever the caller requests up
        # to at least this value for THIS provider instance only — every
        # other provider is unaffected.
        self._max_tokens_floor = max_tokens_floor
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
        constraint: OutputConstraint | None = None,
    ) -> AsyncIterator[str]:
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
    ) -> None:
        super().__init__(
            name="vllm",
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            # CR211 — see `Settings.vllm_max_tokens_floor`. None when the
            # setting is 0, so a non-reasoning server carries no floor at all
            # rather than a floor of zero that reads as one.
            max_tokens_floor=max_tokens_floor,
            # CR210 — both verified live against `ami-llm` on vLLM
            # 0.23.1.dev0+g0fc695fc6 on 2026-08-25, under `stream: true`:
            # `response_format` json_schema held a float enum against a direct
            # user instruction to leave it, and `structured_outputs.regex`
            # produced a conforming Trader money block. This set is a claim about
            # a SERVER, not about a class, so it moves only when the server is
            # re-verified — see `_constraint_request_fields` for why an
            # unverified claim here is worse than no claim.
            supported_constraints=frozenset({"json_schema", "regex"}),
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
                max_tokens_floor=settings.vllm_max_tokens_floor or None,
                timeout_seconds=settings.vllm_request_timeout_s,
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
                # DEF389 — same reason as the floor: which transport budget
                # was in force has to be recoverable from the boot log, since
                # exceeding it is silent at the call site.
                request_timeout_s=settings.vllm_request_timeout_s,
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
                max_tokens_floor=settings.kimi_max_tokens_floor,
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
                reason="no KIMI_API_KEY in env",
            )

        # CR141 (build half of CR017 §3/§5 step 2): DeepSeek/Qwen/Gemini, all
        # OpenAI-compatible, registered the same way as Kimi above — none of
        # these are in `_PREFERENCE`, so registering them changes nothing
        # about which provider wins today; they only get selected via
        # `provider_policy.pick_provider` (not consumed by any live call site
        # yet) or a manual `LLM_FORCE_PROVIDER` override.
        if settings.deepseek_api_key:
            self._providers["deepseek"] = OpenAICompatibleProvider(
                name="deepseek",
                base_url="https://api.deepseek.com",
                model_name="deepseek-chat",
                api_key=settings.deepseek_api_key,
            )
            logger.info("llm_gateway_provider_registered", provider="deepseek")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="deepseek",
                reason="no DEEPSEEK_API_KEY in env",
            )

        if settings.dashscope_api_key:
            self._providers["qwen"] = OpenAICompatibleProvider(
                name="qwen",
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                model_name="qwen-flash",
                api_key=settings.dashscope_api_key,
                # CR017 §3: forces the fast/non-thinking response mode.
                extra_body={"enable_thinking": False},
            )
            logger.info("llm_gateway_provider_registered", provider="qwen")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="qwen",
                reason="no DASHSCOPE_API_KEY in env",
            )

        if settings.google_ai_api_key:
            self._providers["gemini"] = OpenAICompatibleProvider(
                name="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                model_name="gemini-2.5-flash",
                api_key=settings.google_ai_api_key,
            )
            logger.info("llm_gateway_provider_registered", provider="gemini")
        else:
            logger.info(
                "llm_gateway_provider_skipped",
                provider="gemini",
                reason="no GOOGLE_AI_API_KEY in env",
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
    ) -> AsyncIterator[str]:
        import time
        from app.services.audit import record_llm_call
        # CR158 — local, like the import above: prompt_version imports the
        # prompt builders, which import this module's GROUNDING_DIRECTIVE.
        from app.services.prompt_version import prompt_version_for

        provider = self._pick_provider(locale, model_tier, plan=plan, agent_id=agent_id)
        # DEF125: always give the provider somewhere to report the stop reason,
        # even when the caller did not ask for it — the length-stop warning below
        # is what makes a silent truncation visible on EVERY flow (room,
        # one-on-one, brief, Concierge), not only the ones that opted in.
        call_meta: dict[str, Any] = meta if meta is not None else {}

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
            # CR141: whatever the provider wrote into call_meta["usage"] (see
            # AnthropicProvider / OpenAICompatibleProvider above). `.get()`
            # on a missing/partial dict yields None per field, never 0 — a
            # provider that never wrote `usage` at all (no frame, or every
            # frame malformed) records all four columns NULL, exactly like a
            # provider that reported some fields but not others records NULL
            # only for the ones it omitted (CR141 acceptance 2 + 3).
            usage = call_meta.get("usage") or {}
            # CR158: stamp which prompt generation this call used, so a later
            # measurement can partition by it instead of reconstructing epoch
            # boundaries from git SHAs by hand — the manual step that put a
            # wrong reformatter rate into CR143. Cached per agent; None for a
            # non-agent flow (Concierge, the reformatter) and on any failure.
            record_llm_call(
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
            )


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
