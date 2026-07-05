# LLM Routing

Model selection per (plan, agent). **This doc mirrors the routing
shipped in `backend/app/services/llm_gateway.py` + `tier_policy.py`.**
The OpenRouter aggregation + per-locale routing + multi-model backup
chains that earlier drafts described are the **MVP target** — listed
at the bottom under "Not yet delivered".

## The gateway, today

```
Request arrives at LLMGateway.stream_chat(...)
     ↓
Inputs:
  - model_tier (cheap | mid | premium)
  - locale     (currently a no-op — see "Not yet delivered")
  - flow / agent_id / user_id (for audit row, not routing)
     ↓
_pick_provider() returns the first available from the preference order:
  1. vllm        (on-prem Gemma 4 31B at 192.168.20.74:8000)
  2. anthropic   (Claude, dated alias per tier)
  3. mock        (deterministic; final fallback)
     ↓
Provider.stream_chat(...) yields tokens as SSE
     ↓
On completion (or error) → llm_audit row written
   (provider, tier, locale, prompt, response, latency, error)
```

The preference is **environment-driven**, not request-driven. Today on
melehost, the vLLM URL is set, so every call routes there regardless of
tier (single hosted model). Anthropic + mock are the failure fallbacks.

## Tier mapping

`TIER_TO_MODEL` in `llm_gateway.py` (used only when Anthropic is the
active provider; vLLM serves one model and ignores tier):

| Tier | Anthropic model |
|---|---|
| `cheap` | `claude-haiku-4-5` |
| `mid` | `claude-sonnet-4-6` |
| `premium` | `claude-opus-4-7` |

When vLLM is the active provider, tier is recorded in `llm_audit`
for analytics but does not affect the chosen model.

## Per-(plan, agent) tier policy

`tier_policy.pick_tier(plan, agent_id)` is the single source of truth:

| Plan | Default | Concierge | Portfolio Manager | Trader |
|---|---|---|---|---|
| `floor_pass` | cheap | cheap | mid | cheap |
| `trial_trader` | mid | cheap | premium | mid |
| `trader` | mid | cheap | premium | mid |
| `floor_manager` | premium | mid | premium | premium |

**Safety floor wiring**: `Portfolio Manager` runs at `mid` or `premium`
regardless of the user's plan — the PM verdict gates trade execution
through the deterministic compliance check, so we never want a cheap-tier
PM. The check itself is uncoachable (the LLM cannot soften it); the tier
choice is an additional belt-and-braces measure.

**Concierge stays cheap** (`mid` only for Floor Manager): the onboarding
interview is scripted V0 today; even after the LLM-driven swap-in, the
flow is tool-use heavy, not deep-reasoning, so `haiku` is sufficient.

**Trader scales with plan**: `cheap → mid → premium` across plans —
Trader is the agent that actually produces the entry/stop/target
numbers and benefits most from larger-model judgment when the user is
paying for it.

## Audit row shape

Every gateway call writes to `llm_audit` (see [`data_model.md`](data_model.md)):

```python
LLMAuditRow(
    id: UUID,
    created_at: datetime,
    user_id: UUID | None,
    agent_id: str | None,
    flow: str | None,         # 'room' | 'brief' | 'one_on_one' |
                              # 'onboarding' | 'translate' | ...
    tier: str,                # 'cheap' | 'mid' | 'premium'
    provider: str,            # 'vllm' | 'anthropic' | 'mock'
    locale: str | None,
    system_prompt: str,
    messages: list[dict],
    response_text: str | None,
    latency_ms: int | None,
    error: str | None,
)
```

This drives:
- Per-user provider/tier audit (which models served which conversation)
- Latency analytics (where is the gateway slow?)
- Cost reconciliation **deferred**: vLLM is on-prem, fixed cost; Anthropic
  fallback usage is reconciled by exporting `llm_audit` rows and pricing
  them client-side. No `cost_usd` column in Alpha.

## Streaming

All gateway calls use SSE token-streaming. The provider's `stream_chat`
returns an async iterator over chunks; the API endpoint emits each
chunk as an `event: token\ndata: <chunk>\n\n` block to the caller.

Used by:
- `/v1/room/stream` — agent tokens during a Room run
- `/v1/brief/message` — agent reply during a Brief conversation
- `/v1/agents/one_on_one/message` — agent reply during a 1-on-1
- `/v1/llm/translate` — internal helper (accumulates the stream and
  returns the joined string; used by `scripts/translate_arb.py`)

Supabase Realtime is the MVP target — see "Not yet delivered" in
[`architecture.md`](architecture.md).

## Caching

**No LLM-response cache in Alpha.** Redis (`ami_redis` in the Compose
stack) is provisioned but not wired to gateway results. Every call
hits the provider.

Specced caches (lesson wraps 24h, daily challenges 24h, morning
briefings 18h, Concierge FAQ 1h) are MVP scope — they pre-suppose
the daily-briefing + dynamic-lesson-wrap features, neither of which
ships in Alpha.

## Rate limits

**Not enforced server-side in Alpha.** The numbers in
[`api_design.md`](api_design.md) are advisory; client respects them.
Server-side enforcement is a B-tier adversarial audit follow-up.

## Not yet delivered

Specced but not running today. Each is gated on the listed dependency.

### Provider variety

| Provider | Status | Note |
|---|---|---|
| `OpenAIProvider` | Deferred | Class commented as "Coming later (W4+)" in `llm_gateway.py`. |
| `GoogleProvider` | Deferred | Same. Blocks D-048 Arabic-to-Gemini routing. |
| OpenRouter (meta-gateway) | Deferred | Architecture has space for it (`_PREFERENCE` tuple) — needs a new `OpenRouterProvider` class. |

### Routing by locale

`_pick_provider()` accepts a `locale` parameter and records it on the
`llm_audit` row, but never uses it for provider selection. D-048's
Arabic-to-Gemini routing depends on `GoogleProvider` existing first.

When that lands:

```python
def _pick_provider(self, locale: str | None, model_tier: ModelTier) -> Provider:
    if locale == "ar" and "google" in self._providers:
        return self._providers["google"]
    for name in self._PREFERENCE:
        if name in self._providers:
            return self._providers[name]
    raise NoProviderAvailable()
```

### Cost reconciliation

`cost_usd` column on `llm_audit` (or a separate `credit_transactions`
table). Deferred — vLLM is on-prem with fixed cost, and Anthropic
fallback volume is low enough in Alpha to reconcile by hand.

### Aspirational routing table

The MVP design called for per-tier model variety + an OpenRouter
backup chain + Arabic overrides:

| Tier | Default | Backup 1 | Backup 2 | AR override |
|---|---|---|---|---|
| **Floor Pass** | Haiku | GPT-4o-mini | Gemini Flash | Gemini Flash |
| **Trader** | Sonnet | GPT-5.x-mini | Gemini Pro | Gemini Pro |
| **Floor Manager Room** | Opus | GPT-5.x | Gemini Ultra | Gemini Ultra |

This stays in the doc as the MVP target. Until then: Anthropic-tier
fallback only, no locale override, no OpenRouter.

### Caching

| Cache | TTL | Status |
|---|---|---|
| Lesson AI-tutor wraps | 24h | Deferred — dynamic wraps not yet a feature |
| Daily challenges | 24h | Deferred — static manifest today |
| Morning briefings | 18h | Deferred — briefings not shipped |
| Concierge FAQ | 1h | Deferred — Concierge is scripted V0 |

### Future considerations

| When | Move |
|---|---|
| At 50K MAU | Direct enterprise deals with Anthropic; bypass OpenRouter for top providers |
| At 100K MAU | Consider self-hosting open-weights for the cheap tier (today's on-prem vLLM is already a step in this direction) |
| New model launches | Re-benchmark all tier defaults; promote new best-in-class |
| Locale expansion | Re-evaluate per-locale routing (Indonesian via Sea Lion or local) |

## Cross-references

- Backend services overview: [`architecture.md`](architecture.md)
- Audit row schema: [`data_model.md`](data_model.md) `llm_audit` section
- Mandate overlay composition (per-agent prompt assembly): [`../02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
- TradingAgents wrapper internals: [`tradingagent_integration.md`](tradingagent_integration.md)
- Unit economics (will need re-validation when multi-provider lands): [`../06_monetization/unit_economics.md`](../06_monetization/unit_economics.md)
