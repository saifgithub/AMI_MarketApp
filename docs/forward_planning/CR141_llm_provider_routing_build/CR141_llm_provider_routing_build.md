# CR141 — multi-provider routing + usage capture (the build half of CR017)

**Status:** in_progress · **Raised:** 2026-08-07 (AT:R66) · **Parent:** [CR017](../CR017_multiprovider_llm_routing/CR017_multiprovider_llm_routing.md)
· **Origin:** Saiful ruled "Start now" on CR017 in the 2026-08-07 daily review.

## Why this exists as a separate CR

CR017 is a **research spec** and says so in its own header: *"This is a research spec. No code
ships under CR017. Implementation, if approved, becomes a separate build CR."* Saiful's "start now"
is that approval, so this is that build CR. CR017 stays as the design record; CR141 carries the code.

One slice already shipped ahead of this, under CR130: `VLLMProvider` →
`OpenAICompatibleProvider(name, base_url, model, api_key, extra_body)`, done to register Kimi. So
CR017 §5 step 1 is **already complete** and is not re-done here.

## Scope — CR017 §5 steps 2, 3 and 4

### In

1. **Usage capture (§2.4, step 3) — the prerequisite for everything else.**
   `stream_chat` yields text and drops the terminal usage frame, so today *we cannot measure a cache
   hit rate for any provider from our own data*. CR017's 18.5% vLLM figure came from the vLLM
   server's `/metrics`, not from us. Fix: `"stream_options": {"include_usage": true}` on the
   OpenAI-compatible path, `message_delta.usage` on the Anthropic path, surfaced through the
   **existing `meta` dict** the gateway already threads to providers for DEF125's `finish_reason` —
   then into `record_llm_call`. Needs new nullable columns on `llm_audit` and an Alembic revision.

2. **Provider registration from settings (§3, step 2).** DeepSeek, Qwen and Gemini instantiated
   when their keys are present. `deepseek_api_key` and `google_ai_api_key` already exist in
   `config.py`; `dashscope_api_key` is new and must be forwarded in `docker-compose.yml` or
   `test_config_compose_parity.py` fails the build (CR040/P1). Absent key = provider simply not
   registered, matching the existing vLLM/Anthropic pattern.

3. **Provider routing layer (§4, step 4).** New `provider_policy.pick_provider(plan, agent_id,
   tier)` beside `tier_policy`, consumed by `LLMGateway._pick_provider`, which today ignores tier
   and locale entirely and returns a fixed `vllm > anthropic > mock` preference order. **That order
   stays as the fallback** whenever the routed provider is unconfigured — so a missing key degrades
   to today's behaviour rather than to an error.

### Out, and why

- **§5 step 0 — prompt-prefix reordering.** CR017 calls it the highest-leverage item and it is, but
  it changes the prompt every one of the 12 agents receives, and its entire payoff (a cache-hit-rate
  move off 18.5%) is only observable on melehost, which is unreachable today (DEF224) — and only
  observable *at all* once item 1 above lands. Shipping a blind behaviour change to every agent to
  chase an unmeasurable gain is the wrong order. **This is the next slice**, and item 1 is what makes
  it measurable.
- **§5 step 5 — Anthropic `cache_control` markers.** Only pays on the max/ultra premium band, which
  routes to Anthropic; Alpha runs on-prem vLLM, so it would ship untested and unused.
- **Plan→level mapping (§4.4).** CR017 leaves the four assumed levels (`free/pro/max/ultra`) mapped
  to real SKUs as an open decision, and it is a pricing call. `provider_policy` is built to take the
  mapping as data so the decision lands as a table edit.
- **The §4.2 capacity-vs-cost inversion** (route free users to a cheap *API* to reserve vLLM for
  paid users) is Saiful's open call in CR017 §7. The default table here follows CR017's stated
  recommendation — free on the on-prem GPU — and is one dict away from the inverse.

## Acceptance

1. A completed OpenAI-compatible stream records non-null input/output token counts on `llm_audit`;
   an Anthropic stream does the same via `message_delta.usage`.
2. A provider that reports cache fields records them; one that does not records null — **never 0**,
   because a zero cache-read is a measurement and a missing one is not (CR040).
3. Usage capture failing (absent frame, malformed frame) never breaks the stream — the text still
   yields and the audit row still writes.
4. `pick_provider` returns today's `vllm > anthropic > mock` result for every input where the routed
   provider is unconfigured, so an unkeyed deployment behaves exactly as it does now.
5. `dashscope_api_key` is forwarded in `docker-compose.yml`; `test_config_compose_parity.py` green.
6. Routing is table-driven and unit-tested across every (plan, agent-band) pair.
