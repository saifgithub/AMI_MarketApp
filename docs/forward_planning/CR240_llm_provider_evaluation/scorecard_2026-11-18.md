# CR240 hosted-model scorecard for Beta — 2026-11-18 (CR267 WP-10)

**Status: PARTIAL. The DeepInfra account hit its own limit mid-run (HTTP 402), not the $80 cap.**
At 18:37:14Z every DeepInfra call began failing with `HTTP 402 "You need positive balance to do inference"`, all four models in the same second. DeepInfra's `/payment/checklist` then showed `suspended: true, suspend_reason: balance, stripe_balance: -4.37, limit: 25.0`. Our work billed **$4.38** (DeepInfra usage API); the rest of the $25 limit was spent before today. No new DeepInfra run was launched after the first 402. Consequences:

1. Each DeepInfra model has **82–98 valid Rooms of the planned 120**. Rooms that took a 402 are excluded from every number below (30 / 34 / 38 / 22 contaminated Rooms for Qwen / DSV4 / GLM / Ling-general). The missing Rooms are the alphabetically late tickers (about SO–XRX), so coverage is not uniform.
2. The DeepInfra side arms (temperature 0 vs server default) were **not run**. Only Ling-Fin has them.
3. Ling-Fin (our own host) was unaffected: full 120 + 20 Rooms.
4. **Alpha's DeepInfra backup slot uses the same key** (hash-compared, key never printed). Until the account is topped up, Alpha's failover to DeepInfra returns 402.

Raw data: `melehost:~/cr267_wp10/out/<label>/{smoke,smoke2,main,side_t0,side_default}/` (`runs_*.jsonl`, one record per Room), logs in `~/cr267_wp10/logs/`.

## 1. Scorecard

Setup for every row: production prompts (backend default, CR252 heuristics already in all 12 personas), veto and resurrection reviews ON, thinking OFF, frozen `cr265-30` profiles, R2 and R4, 2 reps. "Valid" = no HTTP 402 in any call of the Room. Gate = `scoring.gate_report` via `room_contract_gates` (truncated turn, missing STANCE envelope, unparseable PM or Risk Officer JSON).

### 1a. Measured

| Model | 1. Contract-gate failures (Rooms with ≥1 finding) | 2. Grounding: sheet-figure notes | 3. Minutes per Room, median / p90 | 4. Cost per Room, median (billed-equivalent / list price) | 5. Error rate | 6. Verdict flips between reps, R2 / R4 (diagnostic) |
|---|---|---|---|---|---|---|
| Qwen3.8-Flash | 3/90 (3.3%): 3 × `MISSING_STANCE` (MO R2, SLB R4 ×2) | 30.6% of desk turns; 89/90 Rooms ≥1 note | 3.25 / 3.86 | 1.0¢ / 1.8¢ | 0 call errors, 0 scripted Rooms; **64 HTTP 429 retries** (all recovered) | 0/23, 3/22 |
| DeepSeek-V4-Flash | **0/86** (95% upper bound 3.5%) | 29.2%; 81/86 | 3.48 / 3.95 | 1.1¢ / 1.3¢ | 0 call errors, 0 scripted | 2/22, 5/21 |
| GLM-5.3-Flash | **0/82** (95% upper bound 3.7%) | 28.4%; 79/82 | 3.68 / 4.18 | 1.8¢ / 2.3¢ | 0 call errors, 0 scripted | 0/21, 4/20 |
| Ling-3.0-flash (general, DeepInfra, extra arm) | 1/98 (1.0%): Risk Officer JSON unparseable + truncation (BAC R4) | 29.8%; 95/98 | 3.05 / 3.42 | 0.9¢ / 1.0¢ | 0 call errors, 0 scripted | 6/25, 5/24 |
| Ling-3.0-flash-Fin (own host) | 5/120 (4.2%): PM JSON ×3, truncation of trader / market analyst / PM (see §4) | 29.7%; 120/120 | **8.03 / 11.79** (7.7 median at 4 concurrent; 6.2 min alone, smokes) | $0 marginal | 0 call errors, 0 scripted | 7/30, 9/30 |

Column notes:

1. Gate failures are counted per Room. The per-finding total equals the Room count except Ling-Fin (7 findings in 5 Rooms) and Ling-general (2 in 1).
2. Grounding is **not** Jev-scored (no Jev call was made). It is the backend's own `annotate_sheet_mismatches` note ("AMI checked “X” against the fact sheet: the sheet's own figure is Y…") counted in the stored Room transcript: share of agent turns carrying ≥1 note. It flags a labelled figure that disagrees with the fact sheet. It is a mismatch-detector hit rate, not a truth score, and it only sees labelled restatements of sheet fields. The rate is nearly flat across models (28–31%), so it does not discriminate between them. R:R-geometry notes ran 1.5–2.3 per Room (Qwen 1.49, DSV4 1.85, GLM 2.21, Ling-general 1.94, Ling-Fin 2.04).
3. Minutes are the harness's wall time for the whole convene, including the Room's own typewriter pacing (see §3). DeepInfra models ran 3 Rooms at a time each, all four at once. Ling-Fin ran 4 at a time, and 8 at a time for the first 26 Rooms (median 11.0 min under that load).
4. Billed-equivalent = measured tokens priced with DeepInfra's cached-input rate on the cached share. This reproduces DeepInfra's own usage bill within about 3% per model (§6). List price = all input at the full rate, which is what the gateway's WP-12 accounting does (an over-estimate). All prices are DeepInfra's catalogue: Qwen 0.113/0.382, DSV4 0.09/0.18, GLM 0.15/0.50, Ling 0.06/0.18 per 1M in/out, cached input 0.014 / 0.018 / 0.03 / 0.012. Median tokens per Room: about 140–155k in, 5.3–6.6k out, 15 calls (Ling-Fin 7.3k out).
5. "Error" = a provider call that came back as an error. 429s are retried by the harness wrapper (up to 6 attempts) and never reached a scripted fallback.
6. Flip = the two reps of one (ticker, risk) cell disagree on APPROVE vs PASS, among cells with both reps valid. Diagnostic only. Qwen approved 0/46 Rooms at R2 and 5/44 at R4, so its low flip count mostly reflects an almost constant PASS, not stability. The models ran at different temperatures (§1b), so flips are not comparable across rows.

### 1b. Configuration, licence, hosting

| Model | 7. Thinking-off method (probed) | 8. Temperature and source | 9. Licence and commercial use | 10. Where served |
|---|---|---|---|---|
| Qwen3.8-Flash | `chat_template_kwargs: {"enable_thinking": false}` → 0 reasoning tokens. Default: 68–428 reasoning tokens depending on the probe task (348–428 on the harder one). | **0.7**, [Qwen3.8-Flash-Next card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) instruct/non-thinking mode (the card says Qwen3.8-Flash is the official build of Flash-Next; Flash has no card of its own) | **Not clear.** No public weights and no licence file for Qwen3.8-Flash (HF repo not public; DeepInfra page states no licence). The open sibling Flash-Next is under [Qwen Community License 1.0](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/main/LICENSE): commercial use allowed, but a "Model as a Service" business needs a separate licence. We did not read DeepInfra's hosted-model terms. | DeepInfra, `api.deepinfra.com` |
| DeepSeek-V4-Flash | Nothing sent: DeepInfra serves non-think by default (0 reasoning tokens in every probe except `reasoning_effort: "low"`, which turned reasoning on: 112). | **1.0**, [model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) ("temperature = 1.0, top_p = 1.0", stated for local deployment, not per mode) | **Clear.** MIT, [LICENSE](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/blob/main/LICENSE) (Copyright DeepSeek) | DeepInfra |
| GLM-5.3-Flash | `reasoning_effort: "low"` (lowest level the card documents). **Cannot be fully switched off:** 0 reasoning tokens in 3 of 5 probes, 40–52 in the other 2. `enable_thinking:false` and `reasoning_effort:"none"` made it worse (96–230). | **0.3** (default: [card](https://huggingface.co/zai-org/GLM-5.3-Flash) gives no recommendation, only benchmark-run settings of 0.95–1.0) | **Clear.** MIT, [LICENSE](https://huggingface.co/zai-org/GLM-5.3-Flash/blob/main/LICENSE) (Copyright Z.AI) | DeepInfra |
| Ling-3.0-flash (general) | `chat_template_kwargs: {"enable_thinking": false}` → 0 reasoning tokens. Default: 75 on the first probe. | **0.6**, [card](https://huggingface.co/inclusionAI/Ling-3.0-flash) default parameters (thinking mode is the card's default) | MIT declared in the [card metadata](https://huggingface.co/inclusionAI/Ling-3.0-flash); **no LICENSE file in the repo**. | DeepInfra |
| Ling-3.0-flash-Fin (fp4 build) | `enable_thinking:false` via the standard vLLM slot → 0 reasoning tokens (on: 507 on the same task). | **1.0**, [card](https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin) ("strongly recommend temperature=1.0, top_p=0.95, top_k=20"; written for the thinking-default mode, no non-thinking value given) | MIT declared in the card metadata of [Fin](https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin) and [Fin-fp4](https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin-fp4); **no LICENSE file in either repo**. Needs the licence check Saiful ruled on before go-live. | Our Tailscale host `100.98.142.64:8004`, vLLM, model id `ling-3.0-flash-fin-fp4`, root `/models/Ling-3.0-flash-Fin-fp4` |

Only `temperature` is sent; the gateway has no `top_p` / `top_k` setting, so the cards' other sampling values were not applied. Thinking-off probes were one tiny call each (n = 2–9 per variant), run from the Mac against `api.deepinfra.com` before the matrix; a reasoning count is `usage.completion_tokens_details.reasoning_tokens`.

## 2. Recommendation against the bars

Bars: zero gate failures; under 2 minutes per Room; at most 5¢ per Room; licence clear.

| Model | Zero gate failures | < 2 min per Room | ≤ 5¢ per Room | Licence clear | Bars met |
|---|---|---|---|---|---|
| DeepSeek-V4-Flash | yes, 0/86 | no (3.48) | yes (1.3¢) | yes (MIT file) | 3 of 4 |
| GLM-5.3-Flash | yes, 0/82 | no (3.68) | yes (2.3¢) | yes (MIT file) | 3 of 4 |
| Qwen3.8-Flash | no, 3/90 | no (3.25) | yes (1.8¢) | **no** (unclear) | 1 of 4 |
| Ling-3.0-flash (general) | no, 1/98 | no (3.05) | yes (1.0¢) | partly (MIT in metadata only) | 1 of 4 |
| Ling-3.0-flash-Fin | no, 5/120 | no (8.0) | yes ($0, own host) | partly (MIT in metadata only) | 1 of 4 |

1. **DeepSeek-V4-Flash is the best fit on the evidence**, GLM-5.3-Flash second. Both had zero gate failures over 86 and 82 valid Rooms (95% upper bounds 3.5% and 3.7%, rule of three, so "zero" is not yet proven at the 120-Room scale), both have an MIT licence file, both cost under 2.5¢. DSV4 is cheaper (1.1¢ vs 1.8¢ billed), needs no thinking switch, and its thinking is off by default; GLM's cannot be switched fully off.
2. **No model meets the 2-minute bar on wall-clock**, and model choice does not fix it (§3).
3. Qwen3.8-Flash is dropped on licence uncertainty plus 3 gate failures plus a rate-limit problem (64 retries at only 3 Rooms in flight). Ling-Fin is dropped for Beta on speed (8 min, 5.2 min of it model time) and 4.2% gate failures; it also needs a Tailscale link from the Beta VPS.
4. This is a partial result. Before S2 is decided, finish the remaining 30–38 Rooms per model after the account is topped up (§7).

## 3. Where the time goes

Every model misses 2 minutes, so here is the split per phase. Phase wall time = this phase's last call end minus the previous phase's last call end (from `llm_audit.created_at`), median per Room, minutes:

| Model | Analysts (4 parallel) | Debate (bull → bear → research mgr) | Trader (+repair) | Risk Officer | PM (5 samples parallel) | Reviews | Total median |
|---|---|---|---|---|---|---|---|
| Qwen3.8-Flash | 0.17 | 1.62 | 0.31 | 0.29 | 0.49 | 0.10 | 3.25 |
| DeepSeek-V4-Flash | 0.16 | 1.81 | 0.29 | 0.35 | 0.48 | 0.10 | 3.48 |
| GLM-5.3-Flash | 0.18 | 1.70 | 0.34 | 0.39 | 0.74 | 0.10 | 3.68 |
| Ling-general | 0.11 | 1.51 | 0.32 | 0.26 | 0.49 | 0.11 | 3.05 |
| Ling-Fin (4 concurrent) | 0.87 | 3.92 | 0.84 | 0.84 | 1.26 | 0.10 | 8.03 (all) |

1. **Model time is only part of it.** Summing each Room's LLM latency along its critical path (slowest analyst, then bull + bear + research manager + trader + risk officer in sequence, slowest PM sample, reviews) gives a median of **1.18 / 1.19 / 1.49 / 0.78 min** for Qwen / DSV4 / GLM / Ling-general. All four are under 2 minutes of model time. Ling-Fin: 5.2 min.
2. **The rest is the Room's typewriter pacing.** `room_runner._stream_agent_text` replays every finished turn character by character with a 4–12 ms delay (`_CHAR_DELAY_MIN/MAX`). Estimated at 8 ms × the characters of each Room's agent turns, that is **about 1.7–2.0 min per Room** (Ling-Fin 2.3). Model critical path plus typewriter comes to 2.7–3.4 min against a measured 3.05–3.68, leaving about 0.2–0.4 min for market-data fetch, database writes and phase gaps. The estimate is labelled as such; it was derived from transcript length, not timed directly. It is a UX constant in production code, so a model swap cannot remove it; only a pacing decision can.
3. The debate phase is the largest block (1.5–1.8 min on DeepInfra): three sequential turns, each with the longest texts, so it carries most of the typewriter time too.

## 4. Ling-3.0-flash-Fin vs Ling-3.0-flash (general)

Same family, different build, host, temperature (1.0 vs 0.6) and concurrency, so the comparison is confounded.

1. Gates: Fin 5/120 Rooms (PM JSON unparseable ×3, truncation of trader ×1, market analyst ×1, PM ×2 — all 3 PM-JSON Rooms ended PASS), general 1/98. Not significantly different (4.2% vs 1.0%), but the PM-JSON failures only occurred on Fin.
2. Grounding: 29.7% vs 29.8% of turns carry a sheet-mismatch note. **No measurable difference from the finance tuning.**
3. Speed: Fin 8.0 min (6.2 alone) vs general 3.05 min. This is host capacity (a single vLLM box, 8 concurrent Rooms pushed it to 11 min) as much as the model.
4. Flips: Fin 7/30 and 9/30, general 6/25 and 5/24 — similar.
5. Side arm (Fin only, 10 Rooms R4, 8 concurrent): temperature 0 vs server default (1.0) — gates 0/10 and 0/10, grounding 25.8% vs 26.7%, 11.2 min both. Approvals at R4: 2/10 vs 6/10 (diagnostic only; 10 Rooms cannot support a conclusion).
6. Conclusion: on these measures the finance-tuned build is not better than the general one. In October's runs Fin was best-calibrated; this scorecard does not measure the approval curve, so it neither confirms nor refutes that.

## 5. How the runs were set up (and where they differ from production)

1. **Harness, production code.** Runs used `docs/tools/room_investigation_V2/tools/room_benchmark.py` inside a throwaway `docker compose run` container (promoted `alpha-2026-11-18-2` image, repo mounted read-only), launched by `tools/wp10_run.sh`. Production prompts, veto and resurrection reviews ON, `ROOM_JSON_CONSTRAINTS_ENABLED` / `ROOM_TRADER_REGEX_ENABLED` as Alpha has them, real market data, no failover slot, no spend ceiling. The live `ami_api_alpha`, Postgres, Redis and tunnel were not touched; outputs went to `~/cr267_wp10/` only.
2. **Harness changes (new in this work):** `DEEPINFRA_EXTRA_BODY_JSON` hook in `library/provider_gateway.py` (the DeepInfra provider had no way to send a thinking-off body), and the harness DeepInfra provider now advertises `json_schema` constraints like the `vllm_kind=openai` slot WP-14 ships. Without that the PM and Risk Officer JSON constraints would be "unsupported", unlike production. No `backend/` file changed.
3. **Reviewer model.** Verdict reviews must run on a *different* registered provider. Every arm used the on-prem `ami-llm` as reviewer (DeepInfra arms reach it as the registered `vllm` slot; the Ling-Fin arm via the `kimi` slot pointed at the on-prem host, with `ANTHROPIC_API_KEY` cleared so no Anthropic call could be made). Review calls are 1 per Room, about 4 s, and sit in the "Reviews" column.
4. Frozen `benchmarks/snapshots/cr265-30` profiles for all 30 tickers, so market data does not drift between models. Harness floors: `max_tokens` ≥ 5000 per call, agent timeout 300 s (600 s for Ling-Fin).
5. The harness wrote real `room_runs` / `llm_audit` rows to Alpha's Postgres under synthetic uuid5 users (about 630 Rooms in total including smokes). They are separable by `provider = 'deepinfra'` (or the Ling-Fin model id) and the batch user ids in `out/*/users_*.json`. Exclude them from any tester-activity count.
6. Jev was never called.

## 6. Spend (measured)

1. **DeepInfra's own usage API: $4.38** for November, entirely this work plus a few cents of probes. Account is now `suspended`, balance −$4.37 against a $25 limit.
2. From `llm_audit` (successful calls only): cache-aware **$4.34** (Qwen 0.94, DSV4 1.00, GLM 1.55, Ling-general 0.86), list price **$5.96**. Cache-aware agrees with the bill per model within about 3%.
3. The $80 limit set for this work was never approached.

## 7. To finish the scorecard

1. Top up the DeepInfra account (also restores Alpha's failover slot).
2. On melehost, per model: move the 30–38 contaminated arm records out of `out/<label>/main/runs_cr240-wp10-main.jsonl` (they are listed as `contaminated_keys` by `tools/wp10_analyze.py`) and re-run `wp10_driver.sh <label> 3 3 <proj> 1` with `~/cr267_wp10/STOP` removed. Resume skips completed arms. Then the 20-Room side arms. Estimated cost for all four models together: under $3 (an estimate from the measured per-Room cost).

## 8. Findings that change WP-14

1. **The production DeepInfra slot (`vllm_kind=openai`) sends no thinking-off field.** Qwen3.8-Flash and Ling-general reason by default on DeepInfra (68–428 and 75 reasoning tokens on tiny tasks). Moving to either model through the slot as built would run them with thinking ON. A per-slot extra-body setting is needed; DSV4-Flash does not need one, GLM cannot be switched off anyway.
2. **Verdict reviews on Beta.** `pick_review_provider` only considers `vllm → anthropic → kimi`. On Beta there is no on-prem model, and the primary is the `vllm` slot, so unless an Anthropic or Kimi key is registered the review is skipped with `no_fallback_provider` (logged ERROR, verdict unchanged). The scorecard's review column therefore describes a configuration Beta does not have unless this is addressed.
3. Alpha's backup slot is currently dead (402), see the top of this document.

## 9. Files

1. `docs/tools/room_investigation_V2/benchmarks/cr240-wp10-{smoke,main,side}.yaml`
2. `docs/tools/room_investigation_V2/tools/wp10_{run,models,driver,smoke}.sh`, `wp10_analyze.py` (scoring; read-only SQL over ssh)
3. `docs/tools/room_investigation_V2/library/provider_gateway.py` (`DEEPINFRA_EXTRA_BODY_JSON` hook, `json_schema` constraint)

## 10. Re-score on the current image (2026-11-19)

Why: Saiful asked to test Ling-3.0-flash as a cheaper Beta backup. WP-10's Nov 18 image is gone from melehost, so the two cheapest candidates were re-run on today's image.

**Setup.**

1. Image `ami-trade-local-api-alpha:latest` = `sha256:6c93c41ea59e1cabc78e617678caf1edcb43bddf9cd1a51e4a793cd83fc604ae` (built 2026-11-19 10:15Z, deploy #7 `alpha-2026-11-19-5`). Checked at the start, between the smoke and the matrix, and at the end (12:20Z): it did not change, so **every Room below ran on that one image**.
2. Same harness and settings as §5: `room_benchmark.py` in a throwaway `docker compose run --rm --no-deps`, repo read-only at `/harness`, the `DEEPINFRA_EXTRA_BODY_JSON` overlay, production prompts, veto and resurrection reviews ON (reviewer = on-prem `ami-llm`), frozen `cr265-30` profiles, 3 Rooms in flight per model, both models at once. Ling: temperature 0.6, `{"chat_template_kwargs":{"enable_thinking":false}}`. DSV4: temperature 1.0, no extra body. The only script change is key loading (`tools/rescore_run.sh`: key from the caller's environment, never written to disk).
3. Bench `benchmarks/cr240-ling30-rescore.yaml`: the **first 20 arms of WP-10's main matrix** in its ticker-major order = AAPL, APD, BA, BAC, BGS × R2, R4 × 2 reps. Identical for both models. n = 20 Rooms per model (Ling had one extra smoke Room, AAPL R4, not in the table).
4. "WP-10 same 20" = the same 20 arm keys taken from WP-10's own runs (Nov 18 image), re-scored with the same analyzer, for like-for-like context. None of those 20 were 402-contaminated.

### 10a. Metrics (n = 20 Rooms per model, all completed, 0 failed arms)

| Metric | Ling-3.0-flash, today | DSV4-Flash, today | Ling, WP-10 same 20 | DSV4, WP-10 same 20 |
|---|---|---|---|---|
| Contract-gate failures (Rooms with ≥1 finding) | **0/20** | **0/20** | 1/20 (Risk Officer JSON unparseable + truncation, BAC R4) | 0/20 |
| Valid Rooms (no HTTP error in any call) | 20/20 | 20/20 | 20/20 | 20/20 |
| Call errors / scripted Rooms | 0 of 301 calls / 0 | 0 of 306 calls / 0 | 0 / 0 | 0 / 0 |
| Grounding: desk turns with a sheet-mismatch note | 76/240 = 31.7%; 20/20 Rooms ≥1 | 81/240 = 33.8%; 20/20 | 82/240 = 34.2%; 20/20 | 74/240 = 30.8%; 20/20 |
| Wall-clock per Room, median / p90 (min) | **1.31 / 1.49** | **1.84 / 2.29** | 3.04 / 3.38 | 3.43 / 3.74 |
| Model-only critical path, median (min) | 0.72 | 1.23 | 0.78 | 1.17 |
| Cost per Room, median, billed-equivalent (cache-aware) | **0.70¢** | **1.06¢** | 0.87¢ | 1.06¢ |
| Cost per Room, median, list price (gateway accounting) | **0.94¢** | **1.30¢** | 0.99¢ | 1.31¢ |
| Median tokens per Room, in / out | 139.9k / 6.3k | 134.9k / 5.4k | 145.1k / 6.7k | 136.8k / 5.4k |
| Cached share of input tokens | 35.6% | 24.7% | 21.1% | 28.0% |
| Verdict flips between reps, R2 / R4 (5 cells each) | 0/5, 1/5 | 0/5, 0/5 | 0/5, 1/5 | 0/5, 0/5 |
| Approvals R2 / R4 (of 10 each) | 0/10, 1/10 | 0/10, 2/10 | 0/10, 1/10 | 0/10, 2/10 |

Notes:

1. **Wall-clock fell by more than half on both models, and the model is not why.** The model-only critical path is unchanged (Ling 0.72 vs 0.78, DSV4 1.23 vs 1.17 min). The drop comes from the Room's typewriter pacing: `room_runner._CHAR_DELAY_MIN/MAX` was 4–12 ms per character on the Nov 18 image and is now configurable (CR277) with defaults of 1.5–3.5 ms (`ROOM_CHAR_DELAY_MIN_MS` / `_MAX_MS` in `docker-compose.yml`). So today's minutes are not comparable with §1a's minutes; they are comparable between the two models (same image, same pacing). Phase split today, median minutes, Ling / DSV4: analysts 0.08 / 0.15, debate 0.57 / 0.79, trader 0.13 / 0.14, risk officer 0.13 / 0.28, PM 0.20 / 0.25, reviews 0.12 / 0.11.
2. Cost is `llm_audit` tokens priced at DeepInfra's catalogue (Ling 0.06 / 0.18, DSV4 0.09 / 0.18 per 1M in / out; cached input 0.012 / 0.018). With n = 20 the Ling-vs-WP-10 cost difference (0.70¢ vs 0.87¢) is a cache-hit difference (35.6% vs 21.1% cached), not a price change.
3. Flips and approvals are diagnostic only: 5 cells per risk level cannot support a conclusion. Both models gave the same verdict profile as in WP-10 on these 20 Rooms.
4. p90 over 20 Rooms is the 19th value; treat it as a rough upper edge.
5. Gate result: 0/20 for each model gives a 95% upper bound of about 14% (rule of three). Combined with WP-10 (Ling 1/98), Ling's gate record is 1 finding-Room in 118 across two images; that pooling mixes images and is a reading aid, not a measurement.

### 10b. Leak and thinking check (Ling)

1. Smoke (1 Room, AAPL R4, 12:02Z, 16 calls, 0 errors). Probe: three direct DeepInfra calls with the Ling body returned `usage.reasoning_tokens = 0` and no `reasoning_content` text. The same prompt with the body omitted returned `reasoning_tokens = 227` of 369 completion tokens, so the switch works and thinking is on by default. `reasoning_tokens` is not stored in `llm_audit`, so inside the Rooms the check is indirect.
2. Inside the Rooms: visible characters per output token were 3.21 on average for Ling and 3.67 for DSV4. A hidden-reasoning model would show far fewer visible characters per billed output token.
3. Text scan of every Ling and DSV4 `response_text` since 12:00Z for `<think`, `</think`, `reasoning_content`, "okay, let", "let me think", "thinking process", `<reasoning`: **0 hits** in 296 Ling calls and 286 DSV4 calls, and 0 hits in the stored Room transcripts of the smoke.
4. One residual to know about: a looser scan for "wait," flagged 2 of 296 Ling calls where the model corrected itself mid-answer in the visible text ("… — wait, the sheet's own-history median is **56.7x** …", bear researcher; "— wait, that's below; the point is …", fundamentals analyst). These are visible self-corrections in the final text, not a leaked reasoning block. DSV4 had none. (The other "wait" hits are the trade word WAIT in the Execution Desk's recommendation.)

### 10c. Spend (measured)

1. `llm_audit`, provider `deepinfra`, since 12:00Z, successful and errored calls, tokens × catalogue price at list: Ling **$0.2020** (296 calls, 2.97M in / 133k out), DSV4 **$0.2605** (286 calls, 2.68M in / 107k out). Total **$0.4625 at list price**; about **$0.36 cache-aware** (Ling 0.1424 for the 20 Rooms plus about $0.01 for the smoke, DSV4 0.2125). The five direct probes in 10b cost under $0.001.
2. Hard cap was $2.00. Zero DeepInfra call errors, including no 402.
3. Not measured: DeepInfra's own usage-API bill for these runs (not queried).

### 10d. Files

1. `docs/tools/room_investigation_V2/tools/rescore_run.sh` (copy of `wp10_run.sh`, key from the environment), `tools/wp10_analyze.py` (unchanged from a96b1123, used for scoring).
2. `docs/tools/room_investigation_V2/benchmarks/cr240-ling30-rescore.yaml`, `cr240-ling30-smoke.yaml`.
3. Raw data: `melehost:~/cr267_wp10/out/{linggen,dsv4flash}/main/runs_cr240-ling30-rescore.jsonl`, smoke in `out/linggen/smoke/runs_cr240-ling30-smoke.jsonl`, logs `~/cr267_wp10/logs/rescore_*.log`. `~/cr267_wp10/STOP` left in place; the WP-10 `wp10_*.sh` scripts untouched.
