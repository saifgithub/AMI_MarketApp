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

## Closure — 2026-08-17 (AT:R70), status `done`

All six acceptance criteria were met at AT:R66 and audited COMPLETE (round 1, zero BLOCKER, zero
MAJOR). **None of them promised wiring into a call site**, and acceptance 4 in fact promises the
opposite: today's fallback order survives untouched for every input. So this CR closes on what it
scoped. Wiring is a separate decision, taken below and deferred.

### Gemini exercised for the first time

Saiful added a real Google key to `infra/alpha.env` on 2026-08-17. **It was stored under the wrong
name** — `GOOGLE_API_KEY=`, which nothing in this repo reads — so the provider would have gone on
skipping with `reason="no GOOGLE_AI_API_KEY in env"`. Renamed to `GOOGLE_AI_API_KEY=`, and filed as
**DEF328** with a derived guard, because a key that is present, correct and paid for while reaching
nothing is DEF038's and DEF063's outcome arrived at by a third route.

With the name fixed, measured rather than assumed (P24):

- Direct `curl` to `generativelanguage.googleapis.com/v1beta/openai/chat/completions` — **HTTP 200**,
  `gemini-2.5-flash`, 0.94s.
- A real stream through **our own** `OpenAICompatibleProvider`, unmodified — text returned, and
  CR141's usage capture populated: `input_tokens=17, output_tokens=1`, both cache fields **None**,
  not 0, exactly as acceptance 2 requires. httpx resolves our hardcoded `/v1/chat/completions` onto
  Google's base as `/v1beta/openai/v1/chat/completions`; the doubled segment looks wrong and is
  tolerated by Google's router — it returns 200 and streams. Noted, not "fixed", because it works
  and the fix would be untested churn.
- `_parse_openai_compatible_usage` already reads `prompt_tokens_details.cached_tokens`, which is
  Gemini's field name, so its implicit cache would be captured if a call ever gets big enough to hit
  one (Google quotes a ~1–2k-token minimum).

### What wiring would have moved — measured on live Alpha, 14 days to 2026-08-17

Only three providers are keyed on Alpha: **vLLM, Kimi, Gemini**. `anthropic` and `deepseek` are
absent, so two rows of `_ROUTING_TABLE` would silently fall back to vLLM if wired today.

| plan · tier | calls | input tok | table routes to | actually |
|---|---|---|---|---|
| trader · mid | 4,994 | 18.8M | gemini | **gemini** |
| trader · premium | 462 | 3.0M | gemini | **gemini** |
| floor_manager · premium | 612 | 2.2M | anthropic | unkeyed → vllm |
| floor_manager · cheap | 22 | 0 | gemini | **gemini** |
| floor_manager · mid | 14 | 0.1M | anthropic | unkeyed → vllm |
| floor_pass · all | 353 | 1.6M | vllm | vllm |

All 6,462 calls ran on vLLM, 1 error, **avg 8,093 ms**, usage captured on 6,292 (97.4%),
`cache_read_tokens` on **0** of them (that is DEF226/CR192, upstream, not ours). 5,548 of the paid
calls are `flow=room`, 504 `room_pm` — this is the Room, essentially in full.

So wiring the table as written moves **~85% of Alpha's LLM traffic** onto a metered API. At Google's
published rate ($0.30/M in, $2.50/M out, $0.03/M cached in — fetched 2026-08-17) the arithmetic on
those measured token counts is **~$10.50 per 14 days, ≈$23/month** at current volume. That is list
price × measured tokens, not an observed invoice.

### Two CR017 questions this measurement answers for free

- **§4.2 / §7's capacity-vs-cost inversion** ("route free users to a cheap API and reserve the
  on-prem GPU for paid users") is close to **moot at current volume**: floor_pass is 353 of 6,462
  calls, ~5%. The inversion was posed on an assumption of many free users contending for one GPU;
  Alpha's actual shape is the reverse, so the decision is worth far less than CR017 implies and
  should be re-derived from traffic if it is ever revisited.
- **The plan→level mapping (§4.4)** never became load-bearing, because the ruling below means no
  call site consults it. `_PLAN_TO_LEVEL`'s provisional guess stands, unexercised.

### Saiful's ruling, 2026-08-17: leave it dormant

Asked with the numbers above in hand — benchmark it first / wire the table now / PM-verdict band
only / leave dormant — he chose **leave dormant**. Gemini stays registered and reachable **only** via
`LLM_FORCE_PROVIDER=gemini` for manual testing and benchmarking. No automatic traffic, no spend, and
the fixed `vllm > anthropic > kimi > mock` order continues to serve every call.

That ruling promotes the override from a convenience to **the single path by which any Gemini call
can happen**, so it stopped being safe to leave it merely readable.
`test_cr141_provider_registration.py` already asserted the complement — registering Gemini must not
steal traffic — which on its own is satisfied by a Gemini that is unreachable through *every* path;
asserting only that half is how a provider ends up nominally available and inert (P21).
`test_force_provider_reaches_gemini_because_it_is_now_the_only_path` pins the positive half, and is
mutation-proven: neutering the `forced in self._providers` branch in `_active_provider_name` reds
that test and only that test. It also pins the degrade — a stale override on a deployment with no
key must fall back, never error.

So the code state after this CR is exactly the state the audit proved: the routing layer exists,
is table-driven and tested, and is consulted by nothing. **Wiring it later is a call-site change
plus a table edit** — `stream_chat` already accepts `plan=`/`agent_id=` and `_pick_provider` already
consults `provider_policy` when both are supplied, so the remaining work is passing those two kwargs
in `agent_runner.py` / `room_runner.py` (where `tier_policy.pick_tier` is already threaded) and
ruling on the mapping. That is a fresh CR when Saiful wants it, deliberately **not** filed as
`proposed` today — a proposed CR would resurface this question in every daily review after he has
just answered it.

**Still open, unchanged by this closure:** §5 step 0 (prompt-prefix reordering) remains the
highest-leverage deferred item, and remains blocked on the same thing — DEF226/CR192, because vLLM
still reports no cache field, so the reordering's payoff stays unmeasurable on the provider serving
100% of traffic.
