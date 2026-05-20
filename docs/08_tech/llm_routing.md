# LLM Routing

Model selection per tier × locale × operation type. OpenRouter as meta-gateway + direct provider keys for premium operations.

## Routing strategy

```
Request arrives at LLM Gateway
     ↓
Identify:
  - user.plan (Floor Pass / Trader / Floor Manager)
  - operation type (1-on-1 / Room / Concierge / wrapper / etc.)
  - mandate.locale
     ↓
Resolve routing rules:
  1. Tier-mapped quality bar (cheap / mid / premium)
  2. Locale-specific preferences (Arabic → Gemini)
  3. Cost cap per request type
     ↓
Pick provider via OpenRouter OR direct key
     ↓
If provider fails: fallback chain
     ↓
Return response
```

## Routing table

| Tier | Operation | Default model | Backup 1 | Backup 2 | AR override |
|---|---|---|---|---|---|
| **Floor Pass** | 1-on-1 | Haiku 4.5 | GPT-4o-mini | Gemini Flash | Gemini Flash |
| Floor Pass | Room | Haiku 4.5 | GPT-4o-mini | Gemini Flash | Gemini Flash |
| Floor Pass | Concierge | Haiku 4.5 | GPT-4o-mini | Gemini Flash | Gemini Flash |
| Floor Pass | Lesson wrapper | Haiku 4.5 | (cache mostly) | — | Gemini Flash |
| **Trader** | 1-on-1 | Sonnet 4.6 | GPT-5.4-mini | Gemini 3 Pro | Gemini 3 Pro |
| Trader | Room | Sonnet 4.6 | GPT-5.4-mini | Gemini 3 Pro | Gemini 3 Pro |
| Trader | Concierge | Haiku 4.5 | (same tier as Floor Pass) | — | Gemini Flash |
| Trader | Brief Your Agent | Sonnet 4.6 | GPT-5.4-mini | — | — |
| **Floor Manager** | 1-on-1 | Sonnet 4.6 | GPT-5.4-mini | — | Gemini 3 Pro |
| Floor Manager | Room (premium) | **Opus 4.7** | GPT-5.4 | Gemini 3 Ultra | Gemini 3 Ultra |
| Floor Manager | Concierge | Sonnet 4.6 | GPT-5.4-mini | — | Gemini 3 Pro |
| Floor Manager | Brief Your Agent | Opus 4.7 | GPT-5.4 | — | — |

## Why this routing

| Decision | Rationale |
|---|---|
| **Concierge on Haiku across all tiers** | Concierge is tool-use heavy, not deep-reasoning. Haiku is fast + cheap and tool-use is mature. Quality difference vs Sonnet is small for this workload. |
| **Arabic routed to Gemini** | Google has invested heavily in Arabic. Empirically (will validate) Gemini 3 Pro/Ultra produces more natural Arabic than Claude or GPT for finance content. |
| **Opus reserved for Floor Manager Rooms** | Opus is the most expensive — premium tier pays for it. The multi-round debate showcase truly benefits from deepest reasoning. |
| **Backup chain via OpenRouter** | OpenRouter abstracts provider switching. If Anthropic is rate-limited, our request transparently routes to GPT-5.4-mini. Users notice nothing. |

## OpenRouter vs direct provider keys

| Approach | When |
|---|---|
| **OpenRouter** | Floor Pass + Trader 1-on-1s and Rooms — high volume, cost-sensitive, benefits from routing flexibility |
| **Direct Anthropic** | Floor Manager Rooms — Opus volume is lower; direct gives us SLA + caching control |
| **Direct Google AI** | Arabic-specific routes — direct beats OpenRouter latency for region-routed calls |
| **Direct OpenAI** | Currently rarely used; kept as a backup |

We can shift between OpenRouter and direct on a per-route basis without app changes.

## Cost monitoring

Every LLM call records:

```python
LLMCall(
    id: uuid,
    user_id: uuid,
    operation_type: str,      # "convene_room" / "one_on_one" / "concierge" / etc.
    provider: str,            # "anthropic" / "openrouter" / "google"
    model: str,               # "claude-opus-4-7" etc.
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,          # computed from provider pricing
    latency_ms: int,
    success: bool,
    error: str | None,
    started_at: datetime,
    finished_at: datetime,
)
```

This drives:
- Real-time cost dashboards in PostHog
- Per-user LLM-cost tracking (for credit reconciliation)
- Monthly aggregate cost by tier/operation/provider
- Anomaly alerts (e.g., a sudden 3× spike in Sonnet usage → investigate)

## Caching

| Cache | Hit rate target | TTL |
|---|---|---|
| Lesson AI-tutor wraps | 85%+ | 24h |
| Daily challenges | 99% (one per locale per day) | 24h |
| Morning briefings | 95% (one per user per day, cached after generation) | 18h |
| Concierge product help (FAQ-style) | 50% | 1h |

Caching saves us 60–80% of LLM cost vs no-cache baseline. The cache is Redis (Cloud Memorystore) keyed by `(operation_type, input_hash, model, locale)`.

## Streaming

All LLM calls use streaming where applicable:
- 1-on-1 chat: stream tokens to client via Supabase Realtime
- Convene the Room: stream per-agent contributions to client
- Lessons / briefings (non-interactive): no stream; cached

Streaming reduces perceived latency dramatically. User sees "Bull Researcher: Strong fundamentals..." within 1.5s, instead of waiting 30s for the full output.

## Rate limits per tier

| Operation | Floor Pass | Trader | Floor Manager |
|---|---|---|---|
| 1-on-1 messages/min | 6 | 30 | 60 |
| Convene per hour | 2 (capped by credits anyway) | 5 (capped by credits) | 8 (capped by credits) |
| Concierge messages/min | 12 | 30 | 60 |
| Brief Your Agent saves/hour | 1 (caps + edit limit) | 10 | 30 |

Rate limits prevent abuse and protect against runaway-loop bugs. Returned via standard 429 with `Retry-After` header.

## Future considerations

| When | Move |
|---|---|
| At 50K MAU | Negotiate direct enterprise deals with Anthropic / OpenAI; bypass OpenRouter for top providers |
| At 100K MAU | Consider self-hosting open-weights models (Llama, Qwen, DeepSeek) for the cheap tier |
| New model launches (every 3–6 months) | Re-benchmark all tier defaults; promote new best-in-class |
| Locale expansion | Re-evaluate locale-specific routing (e.g., adding Indonesian routes via Sea Lion or Indo-LLM) |

## Cross-references

- Unit economics (cost math): [`docs/06_monetization/unit_economics.md`](../06_monetization/unit_economics.md)
- Mandate-overlay-driven model selection: [`docs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
- TradingAgents wrapper that uses these: [`tradingagent_integration.md`](tradingagent_integration.md)
