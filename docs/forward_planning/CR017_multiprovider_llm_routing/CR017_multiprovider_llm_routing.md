# CR017 — Multi-provider LLM routing + per-provider caching mechanics (research)

**Status:** proposed (research/design spec — no code) · **Session:** AT:R53 · **Date:** 2026-07-10
**Source:** Saiful — *"(1) CR008 using cache — check if the code needed to use cache is different for each provider. (2) Look at how we can use the LLM from other providers — DeepSeek V4 Flash, Qwen Flash [+ Gemini]. Include routing capability based on user level (assume 4: free / pro / max / ultra)."*
**Linked to:** [CR008 — Convene the Room token estimation & prompt caching](../CR008_convene_room_prompt_caching/CR008_convene_room_prompt_caching.md)

---

## 0. How this relates to CR008

CR008 answered the **economics** question: how many tokens a Convene run costs, and the $/month at 30k runs across candidate models. This CR (CR017) answers the two **engineering** questions CR008 left open:

1. **Is the caching *code* different per provider?** (§2)
2. **How do we actually wire additional providers** — DeepSeek V4 Flash, Qwen Flash, Gemini — into our gateway, and route them **by user level**? (§3–§5)

It also logs three factual corrections to CR008 that change the strategy (§6).

This is a **research spec.** No code ships under CR017. Implementation, if approved, becomes a separate build CR.

---

## 1. Where the code stands today

The gateway ([`backend/app/services/llm_gateway.py`](../../../backend/app/services/llm_gateway.py)) has:

- A provider interface `LLMProvider.stream_chat(system_prompt, messages, model_tier, max_tokens) -> AsyncIterator[str]` — **yields text only; discards token usage.**
- Three concrete providers: `MockProvider`, `AnthropicProvider` (direct Anthropic Messages API), `VLLMProvider` (on-prem, **OpenAI-compatible** `/v1/chat/completions`).
- `LLMGateway._pick_provider()` — **ignores `model_tier` and `locale` entirely**; returns the first available provider in a fixed preference order `vllm > anthropic > mock`. So when vLLM is up, *everything* routes to vLLM regardless of tier.
- `tier_policy.pick_tier(plan, agent_id)` — picks a *tier* (`cheap`/`mid`/`premium`), but since `_pick_provider` ignores the tier for provider selection, tier only affects the Anthropic model alias, and is a no-op on vLLM.

**Two structural facts that drive this CR:**
- **Provider selection is by availability, not by tier/plan/agent.** Any "route cheap agents to a cheap provider" scheme requires a *new* provider-routing layer (§5), not just a new provider class.
- **Usage is never captured.** We cannot measure a cache-hit rate for *any* provider until the streaming path reads the terminal `usage` block. Prerequisite for all caching telemetry (§2.4).

---

## 2. Q1 — Is the caching code different per provider? **Yes — in three layers, not one.**

> **Correction (AT:R53).** An earlier pass framed this as a binary — "Anthropic writes marker code; everyone else is automatic, zero work." That is misleading. "Automatic" means *no cache markers*, **not** *no work*. Every provider here is a **prefix cache** (matches from token 0 to the first differing byte), so all of them require prompt-structure discipline to get hits, and their hit-thresholds differ. The difference between providers is real and bigger than "markers or not."

**Live evidence that automatic ≠ done.** Our on-prem vLLM has prefix caching enabled, yet its live `/metrics` show only an **18.5% hit rate** (`prefix_cache_hits_total` 1,701,952 ÷ `prefix_cache_queries_total` 9,181,908, sampled AT:R53). Caching is *on* and barely helping — because our prompts aren't ordered for it (each agent's unique base prompt sits at the front of the prefix). That gap is Layer 2 below, and no provider gives it to us for free.

### 2.1 The three layers of "using cache"

**Layer 1 — Marker code (cache directives in the request body).** Anthropic **only**. Everyone else takes no markers.

**Layer 2 — Prompt-structure discipline (required by ALL, us-owned, not done today).** A prefix cache only reuses the leading run of identical tokens. To benefit, the prompt must be ordered **stable-prefix-first, volatile-suffix-last**: `[agent base + mandate + alpaca snapshot]` then `[ticker + timestamp + transcript]`. Our current builder puts per-agent content at the front → the 18.5% vLLM number. This work is provider-agnostic and applies to DeepSeek exactly as much as Anthropic.

**Layer 3 — Hit conditions + telemetry differ per provider** — so the *same* prompt yields different savings, and the *optimal* structure differs (see §2.2):

| Provider | Markers? | Min prefix | Write fee | Cached read | TTL | Usage field |
|---|---|---|---|---|---|---|
| **Anthropic** | **Yes** | **1,024** (Sonnet/Opus) / **2,048** (Haiku) | **+25%** | ~10% | 5 min (1 h beta) | `cache_read_input_tokens` |
| **DeepSeek** | No | **0** (64-tok blocks) | **none** | ~10% | hours (disk) | `prompt_cache_hit_tokens` |
| **vLLM** (live) | No | ~16-tok block | n/a (on-prem) | free | LRU eviction, per-instance | *(only in `/metrics`, not the API response)* |
| **Gemini 2.5** | No (implicit) | ~1,024 (Flash) / ~2,048 (Pro) | none | ~25% | opportunistic | `prompt_tokens_details.cached_tokens` |
| **Qwen** (DashScope) | No (implicit) | model-dependent | none | discounted | short | usage cache fields |

### 2.2 The min-prefix threshold changes what code you write
This is where the per-provider difference bites. On **Anthropic** you must *engineer* a ≥1,024-token cacheable block to cache anything at all. On **DeepSeek (0 min)** and **vLLM (16-tok blocks)**, the small **~450-token context shared across all 12 agents in one run** — which CR008 §Opportunity C dismissed as "too small to cache" — **is cacheable.** So the same restructuring buys DeepSeek/vLLM a within-run win that Anthropic simply can't take. DeepSeek is the most forgiving of the set: 0-token min, no write surcharge, hours-long disk TTL vs Anthropic's 5 minutes. **You (Saiful) were right — DeepSeek definitely caches, and more usefully than Anthropic for our prompt sizes.**

### 2.3 What the Anthropic marker code looks like (Layer 1, Anthropic-only)

```python
"system": [
    {"type": "text", "text": static_prefix,
     "cache_control": {"type": "ephemeral"}},   # ← cached (base+mandate+alpaca)
    {"type": "text", "text": dynamic_room_addition},  # ← not cached
]
# + read usage.cache_creation_input_tokens / cache_read_input_tokens from SSE.
```

DeepSeek/Qwen/Gemini-implicit/vLLM take **no** equivalent — but they still need Layer 2, and Gemini has an *optional* explicit `cachedContents` handle API (more code) if we ever want guaranteed (non-opportunistic) caching.

### 2.4 Prerequisite gap: usage capture (blocks measuring ALL of the above)
Our `stream_chat` yields text and drops the final usage frame, so we can't measure a hit rate on any provider (the 18.5% above came from vLLM's server metrics, not our app). Fix: send `"stream_options": {"include_usage": true}` (OpenAI-compat) or parse Anthropic's `message_delta.usage`, and thread `input / output / cache_read / cache_write` into `record_llm_call`. One-time change; unblocks all cache telemetry and the Layer-2 tuning loop.

---

## 3. Q2 — Wiring DeepSeek Flash, Qwen Flash, and Gemini

**All three are OpenAI-compatible.** Our `VLLMProvider` is *already* an OpenAI-compatible client — the SSE parser (`choices[0].delta.content`) and body shape are identical. So adding these providers is **generalizing one class into `OpenAICompatibleProvider(name, base_url, model, api_key, extra_body)`** and instantiating it N times, not writing N new providers.

| Provider | OpenAI-compat base URL | Model id (confirm at build) | Auth | Config key | Quirk |
|---|---|---|---|---|---|
| **DeepSeek V4 Flash** | `https://api.deepseek.com` | `deepseek-chat` (→ V4 Flash pointer) | `Bearer $DEEPSEEK_API_KEY` | ✅ `deepseek_api_key` exists ([config.py:57](../../../backend/app/core/config.py#L57)) | none material |
| **Qwen Flash** | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `qwen-flash` | `Bearer $DASHSCOPE_API_KEY` | ❌ new `dashscope_api_key` needed | may need `extra_body={"enable_thinking": false}` for fast/non-thinking mode |
| **Gemini 2.5 Flash / Flash-Lite** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash`, `gemini-2.5-flash-lite` | `Bearer $GOOGLE_AI_API_KEY` | ✅ `google_ai_api_key` exists ([config.py:56](../../../backend/app/core/config.py#L56)) | safety-setting defaults differ; native SDK optional but not needed |

**Takeaway:** the OpenAI-compatible endpoint means Gemini fits the *same* provider class as DeepSeek/Qwen/vLLM — no native-Gemini `contents`/`parts` code needed. The only per-provider divergence is small `extra_body` quirks (Qwen `enable_thinking`), which is exactly why the class takes an `extra_body` param. This *reinforces* §2's answer: "OpenAI-compatible" is not "identical" — each provider carries a small tail.

Provider layer effort estimate: **~40 LOC** (generalize class + register 3 instances from settings) + 1 new config key + usage capture (§2.4).

---

## 4. Provider routing by user level (free / pro / max / ultra)

The new capability Saiful asked for. Two dimensions compose:

- **User level** (assumed 4: `free`, `pro`, `max`, `ultra`) — the willingness-to-pay / quality band.
- **Agent role band** (from `tier_policy`): *Analysts & Debators* (cheap), *Synthesis / Research Mgr / Trader* (mid), *PM / Verdict* (premium).

### 4.1 Proposed routing matrix

| User level | Analysts & Debators | Synthesis / RM / Trader | PM / Verdict | Est. $/1-round run¹ |
|---|---|---|---|---|
| **free** | vLLM (Gemma, on-prem) | vLLM | vLLM | **~$0** (on-prem sunk cost) |
| **pro** | DeepSeek V4 Flash | Gemini 2.5 Flash | Gemini 2.5 Flash | **~$0.005** |
| **max** | Gemini 2.5 Flash | Claude Sonnet | Claude Sonnet | **~$0.02** |
| **ultra** | Gemini 2.5 Flash | Claude Sonnet | Claude Opus | **~$0.05–0.08** |

¹ Per CR008's ~17.58k input / 840 output tokens per 1-round Convene. Indicative July-2026 rates; confirm at build. Assumes automatic caching where available (see §4.3).

### 4.2 The design rationale — free on our own GPU, paid on metered APIs
Putting **free users on vLLM** (the on-prem Gemma box) is economically clean: the GPU is a **flat/sunk cost**, so free-tier marginal cost is ~$0 and non-payers can never generate an external API bill. Paid tiers spend real per-call money that their subscription covers, buying progressively better judgment (DeepSeek Flash → Gemini Flash → Sonnet → Opus).

**Open decision:** the inverse is also defensible — route *free* to the cheapest **API** (Qwen/DeepSeek Flash, ~$0.001–0.003/run) to reserve scarce vLLM capacity for **paid** users who need low LAN latency. This is a capacity-vs-cost call for Saiful. Recorded as an open item (§7).

### 4.3 Routing and caching interact — routing shrinks the *marker*-code surface, but not the Layer-2 work
Because free/pro/max analysts route to **automatic-cache** providers (vLLM / DeepSeek / Gemini), those calls need **no cache *marker* code** — the only place we'd write Anthropic-style `cache_control` (CR008 §4) is the **max/ultra premium band** (Sonnet/Opus). So routing shrinks the *marker*-code surface to just the top tiers. **Caveat (per §2):** the Layer-2 prompt-prefix ordering is still required on *every* tier — automatic caches only pay off once the stable content is a literal prefix, which our builder doesn't do today (the live vLLM 18.5% hit rate is the proof). Sequence: (1) fix prompt ordering [helps all providers], (2) provider routing, (3) Anthropic markers for the top band only.

### 4.4 Mapping to current plans
Current code plans are `FLOOR_PASS / TRIAL_TRADER / TRADER / FLOOR_MANAGER`. The 4 assumed levels are a **forward model**; a build CR must decide the mapping (e.g. `free=FLOOR_PASS`, `pro=TRADER`, `max=FLOOR_MANAGER`, `ultra=`new top SKU). Left open — this CR designs the routing *mechanism*, not the pricing SKUs.

---

## 5. Implementation sketch (NOT built — for the future build CR)

0. **Prompt-prefix reordering (Layer 2 — highest leverage, provider-agnostic).** Restructure the prompt builders (`room_prompts` / `agent_prompts`) so the stable block (agent base + mandate + alpaca snapshot) is a literal prefix and volatile content (ticker, timestamp, transcript) comes last. Helps *every* provider's automatic cache — including the live vLLM currently at 18.5%. Do this first; it needs no provider or routing change.
1. **Generalize the provider.** `VLLMProvider` → `OpenAICompatibleProvider(name, base_url, model, api_key, extra_body=None)`. Keep `VLLMProvider` as a thin alias for back-compat. (~40 LOC.)
2. **Register providers from settings.** DeepSeek / Qwen / Gemini instances when their keys are present, mirroring the existing vLLM/Anthropic registration blocks. Add `dashscope_api_key`.
3. **Capture usage.** Add `stream_options.include_usage` (OpenAI-compat) + Anthropic `message_delta.usage` parsing; thread `input/output/cache_read/cache_write` into `record_llm_call`. (Prereq for any caching KPI.)
4. **Provider routing layer.** New `provider_policy.pick_provider(level, agent_id, tier) -> (provider_name, model)` beside `tier_policy`. `_pick_provider` consumes it instead of the fixed preference order, with the current `vllm > anthropic > mock` order as the fallback when a chosen provider is unconfigured.
5. **(Top tiers only) Anthropic `cache_control`** per §2.2 + CR008 §4, gated to the max/ultra premium band.
6. **Config/env:** `dashscope_api_key`, per-level routing table (env or a small policy module), keep provider keys optional so absence = graceful skip (matches today's pattern).

**Rough effort:** provider layer + usage ≈ 0.5 session; routing layer ≈ 0.5–1 session; Anthropic cache-control ≈ 0.5 session. All backend → each needs a `/promote-to-alpha` (Saiful's call).

---

## 6. Corrections to CR008 (factual, they change the plan)

1. **Anthropic Haiku min cache = 2,048 tokens, not 1,024.** CR008 §2 assumes 1,024 for Haiku. The Convene static prefix is only ~1,005 tokens → it **would not cache on Haiku at all**, and only barely on Sonnet. This materially weakens "cache on Anthropic Haiku" and strengthens "route cheap traffic to DeepSeek (0-token min) / Gemini (auto)."
2. **Qwen-Flash caching exists.** CR008 lists it as "No public context caching"; DashScope has since shipped implicit context caching. Stale row.
3. **Gemini 2.5 implicit caching lowers the 32k barrier.** CR008 dismisses Gemini on a 32,768-token explicit-cache minimum. Gemini **2.5 implicit** caching is automatic with a ~1–2k-token minimum — usable for our 1–2k prompts. Gemini is back in scope (as reflected in §3–§4).
4. **We run vLLM today, which already caches for free.** For the *current* stack the caching-cost question is moot — caching only becomes a $ lever once we route to a paid API.

---

## 7. Open decisions / acceptance criteria

**Open decisions (Saiful):**
- [ ] Free-tier placement: on-prem vLLM (≈$0, §4.2) **vs** cheapest API (reserve vLLM for paid low-latency)?
- [ ] The 4-level → current-plan SKU mapping (§4.4).
- [ ] Which paid tiers may touch Anthropic (the only providers with a write-surcharge and the only cache-code cost).
- [ ] Whether to keep vLLM as universal fallback when a routed provider is unconfigured/500s.

**Acceptance criteria (this research CR):**
- [x] CR017 registered in `cr_list.md`, linked to CR008.
- [x] Per-provider caching-code difference documented (Anthropic explicit vs vLLM/DeepSeek/Qwen/Gemini automatic).
- [x] DeepSeek Flash, Qwen Flash, Gemini integration paths documented (all OpenAI-compatible; config keys identified).
- [x] User-level routing matrix (free/pro/max/ultra × agent band) with indicative per-run cost.
- [x] CR008 corrections logged.
- [ ] Saiful's routing decisions captured before a build CR is opened.
