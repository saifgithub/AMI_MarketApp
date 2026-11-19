# CR267 gate S11 — hosted-LLM implementation plan (for discussion)

**What this is:** the implementation plan for the LLM-side work packages (WP-15, WP-10 … WP-14),
written for Saiful to discuss and approve before any LLM change (gate S11). **Why:** Saiful,
2026-11-18: *"before you start making changes for JEV and the LLM, please pause so we can discuss
implementation plans, since it is very significant change."* Code facts come from a survey of
`beta/cr267` on 2026-11-18. File:line references are to that branch.

---

## 1. What the code does today (facts that change the plan)

1. **Only one provider per call; no failover anywhere.** `llm_gateway.py:1374` says so. A provider
   error becomes an `[AMI error: …]` sentinel, and the Room swaps in a scripted desk turn
   (`room_runner.py:9596`).
2. **"Configuration only" will not quite hold for DeepInfra.** The `vllm` slot already sends a
   Bearer key and expects a base URL without `/v1`, so DeepInfra fits its URL and auth. But on every
   call it also sends vLLM-only fields: `chat_template_kwargs.enable_thinking` (`llm_gateway.py:894`)
   and, for some calls, a `structured_outputs` regex constraint (`:904`). DeepInfra may reject or
   ignore these. The research harness already reached DeepInfra through a separate, plain
   OpenAI-compatible provider (`library/provider_gateway.py:50-90`), which is why those runs worked.
3. **No temperature is sent anywhere** (`grep temperature backend/app` finds nothing). Every desk
   runs at the server default, usually 1.0.
4. **`llm_audit` records the provider name but not the model** (`db/models.py:966`). It does store
   input/output token counts from the provider. **No cost is computed anywhere.**
5. **No per-user Room concurrency cap.** Dedup is per (user, ticker) only. A `ConcurrencyLimiter`
   exists for 1-on-1 and Brief (`rate_limit.py:274`) but not for the Room.
6. **No output text guard exists.** The natural seam is right after a desk's text is assembled
   (`room_runner.py:9594`), with matching seams in the 1-on-1 and Brief paths.
7. **CR252's smoke test injected the section into all 12 agents**, not the 4 evidence desks.
8. **The DeepInfra key lives only in the Mac's root `.env`, as `DEEPINFR_API_KEY` (misspelt).**
   It is not in `infra/alpha.env` or on melehost. The account was loaded with $25 on 2026-09-26
   (CR240).

## 2. Proposed design, per work package

### WP-15 — CR252 heuristics section (setting-gated)
1. A `room_heuristics_section_enabled` setting, threaded into `build_room_messages` exactly like
   the CR256 `cards_envelope` parameter. When it is OFF, prompts are byte-identical to today.
2. The section text is `production_section.md` as committed.
3. **Decision A:** which agents get it (see §3).

### WP-11 — Pin sampling
1. Settings: `llm_desk_temperature` (all Room desks, 1-on-1, Brief) and `llm_judge_temperature`
   (default 0, used later by WP-22). Applied in the gateway request body for every provider. The
   desk default follows the chosen model card's recommended value for non-thinking mode, else 0.3.
2. The harness gets the same plumbing, so WP-10 measures the production setting.

### WP-12 — Spend ceiling and one Room per user
1. **Model identity.** Add a `model` column to `llm_audit` (one Alembic migration) holding the
   served model's `root` from `/v1/models`, read once at startup and on failover, never the alias.
   This also serves WP-14's acceptance and WP-24's room key.
2. **Cost.** An `llm_prices_json` setting: per-model input and output price per million tokens,
   copied from the vendor page at cut-over. Spend = Σ tokens × price over `llm_audit`, cached for
   60 s. A model missing from the price table fails loudly at boot.
3. **Ceiling.** `llm_daily_spend_ceiling_usd` ($10 Beta, $5 Alpha), counting primary and fallback
   together. The day is UTC, matching vendor billing. On breach, new Rooms, 1-on-1 and Brief
   requests get an honest "AMI is temporarily unavailable" state; Rooms already running finish, so
   nobody is stranded mid-debate with credits spent. An alert fires once per breach (log
   ERROR + Sentry event; Beta alerting is wired in WP-44).
4. **One Room in flight per user, across tickers.** A database check for any `running` run by the
   same user, in the same place as dedup tier 1. It survives restarts, unlike an in-memory limiter.
   Message: "You already have a Room in session. It will finish first."

### WP-13 — Output text guard
1. A deterministic checker over user-visible agent text, in three lists:
   1. **Personalised-advice phrasing**, e.g. "you should buy", "I recommend you", "guaranteed
      return", "can't lose".
   2. **Unsafe content** (a short slur/abuse list).
   3. **Off-topic** detection cannot be done deterministically with honest precision. Proposed:
      drop it, and rely on the hosted (non-abliterated) model plus prompts.
2. Scope: Room desk turns, CIO narration, 1-on-1, Brief.
3. On a hit in a Room, the desk turn takes the existing scripted-fallback path: it is labelled and
   counted like a transport failure, so it cannot carry an argument into the verdict. In 1-on-1 or
   Brief, the reply becomes a labelled "AMI withheld this reply" message. Every hit is logged with
   the matched rule.
4. Rollout: log-only first. The hit rate is measured by replaying stored text from `llm_audit`
   (Alpha has had almost no traffic since 2026-10-30). Enforcement switches on before go-live.

### WP-14 — Provider slots and automatic failover (D-078)
1. **Slot kind.** Add `vllm_kind` = `vllm` | `openai`. `openai` drops the vLLM-only body fields
   (`chat_template_kwargs`, `structured_outputs`) and advertises JSON-schema `response_format`
   only. This keeps "switch the primary by configuration" true for DeepInfra.
2. **Fallback slot.** `vllm_fallback_base_url`, `_model`, `_api_key` and `_kind`, registered as a
   second provider. On Beta, a second DeepInfra model (kind `openai`). A boot check refuses a
   LAN/private address in either slot when `ENV=beta`. Alpha keeps on-prem as its primary; see item
   5 and decision 8.
3. **Retry, then fail over.** Port the harness's `_RetryTransient` into the gateway: retry 429/5xx
   and connect errors up to 3 times with backoff, before the first streamed chunk only. If that
   fails:
   1. **Room:** **restart the whole Room on the fallback** from the beginning, so one Room never
      mixes two models' arguments. The stream says so ("AMI switched to its backup model"), and the
      stored record carries the fallback model.
   2. **1-on-1 / Brief:** the single call fails over.
4. **Both down:** the "temporarily unavailable" state, no verdict, credits refunded through the
   existing CR039 refund path.
5. **Alpha stays on on-prem** (Saiful, 2026-11-18: *"keep use on-prem until we actually move to
   beta"*). Alpha's primary remains the on-prem vLLM, so there is **no Alpha cut-over**. The hosted
   model becomes primary only on the Beta host, set in `infra/beta.env` (WP-41) at go-live. Until
   then, DeepInfra is used only by the harness for measurement (WP-10, WP-20, WP-22, WP-26).
   - The key moves to a correctly spelled `DEEPINFRA_API_KEY` in `infra/alpha.env`, so the harness
     on melehost can read it. The Alpha gateway does not use it.
   - The slot-kind and failover code still ships in WP-14 and is tested on Alpha with a forced
     failure, without changing Alpha's primary.

### WP-10 — Model scorecard (runs on melehost, through the harness)
1. **Order.** WP-15 and WP-11 code first, because the harness imports the backend from the
   mounted repo and must measure the production prompts and temperature.
2. **Shortlist** (to confirm against DeepInfra's live catalogue): Qwen3.8-Flash (non-abliterated,
   the current model family), DeepSeek-V4-Flash, GLM-5.3-Flash. All three already ran on DeepInfra
   in October (stocktake row 12, about 90 rooms, never promoted).
3. **Matrix per model.** 30 tickers × R2 and R4 × 2 reps = 120 rooms, plus a 10-ticker side arm at
   temperature 0 and at the server default. About 160 rooms per model, about 480 in all.
   - At the 5¢ bar that is about $24, an estimate, not measured.
   - Before the full matrix, a 1-ticker smoke per model measures cost and minutes.
   - The harness stops itself at $80 (the $100 programme cap less margin).
4. **Scorecard:** contract gates, figure grounding, minutes per Room, cost per Room from usage, and
   error rate. Saiful picks the model at S2.

## 3. Decisions for Saiful

1. **CR252 scope:** the 4 evidence desks (fundamentals, bull, bear, research manager), or all 12
   agents as in its smoke test? *Recommended: the 4 desks.* That keeps the prompt-length and
   latency hit off the other 8 calls under the 2-minute bar.
2. **Failover granularity:** restart the whole Room on the fallback, or switch mid-Room?
   *Recommended: restart.* One model per Room keeps the verdict explainable.
3. **Ceiling day:** UTC, or Asia/Riyadh midnight? *Recommended: UTC.*
4. **Ceiling breach:** let running Rooms finish? *Recommended: yes.*
5. **Output guard:** drop the off-topic check (not deterministic)? *Recommended: drop it.*
6. **Shortlist:** Qwen3.8-Flash, DeepSeek-V4-Flash, GLM-5.3-Flash. OK, or swap one?
   **Ling-3.0-flash-Fin** (Ant Group, finance-trained) was the best-calibrated model in October:
   - curve 4/11/19/29/27 at 9.1 min/Room;
   - T011 on 2026-10-29: 22% flips over 600 rooms.

   It was never production, though. It was served from a Tailscale host (`100.98.142.64:8004`),
   recorded "paused on model availability" on 10-29, with its licence unconfirmed. It enters WP-10
   only if:
   (a) a hosted provider serves it (I'll check DeepInfra's catalogue first), or
   (b) that host is available again and Saiful accepts Beta depending on it. That would also need a
       private link from the Beta VPS and a licence check.

   Which host serves Ling, and is it ours to use?
7. **DeepInfra key:** move it into `infra/alpha.env`, which ships to melehost. Confirm, and top up
   the account toward the $100 measurement cap (it held $25 in September).
8. **Consequence of on-prem Alpha, to confirm.** The Room's decision work must be tuned and
   accepted on the model Beta will run, not on Alpha's.
   1. WP-20 (baseline), WP-22 (bake-off) and WP-26 (acceptance) therefore run **through the harness
      against the chosen DeepInfra model**.
   2. Alpha testers meanwhile see the on-prem (abliterated) model with the old CIO vote, until the
      new decision rule ships behind its setting.
   3. On Alpha, should the fallback slot point at DeepInfra (*recommended*: Alpha then exercises
      the failover path before Beta), or stay empty?

## 3a. Saiful's rulings (2026-11-18)

1. **CR252 scope:** **all 12 agents** (not the recommended 4).
2. **Failover:** restart the whole Room on the backup.
3. **Ceiling:** UTC day; running Rooms finish.
4. **Text guard:** personal-advice and abusive-language rules enforce. The **"is this about
   markets?" check is also built, log-only, never blocking**, so its behaviour can be seen.
5. **Ling:** the Tailscale host is **ours and usable**. Ling joins the WP-10 shortlist, served from
   that host.
   - If it wins, Beta needs a private (Tailscale) link from the VPS to that host, plus a licence
     check on Ling-3.0-flash-Fin before go-live.
   - The Beta boot check must then allow that one Tailscale address in place of "no private
     addresses".
6. **Alpha backup:** DeepInfra (it counts against Alpha's $5/day ceiling). Alpha's primary stays
   on-prem until Beta.
7. **DeepInfra key:** move it into `infra/alpha.env` as `DEEPINFRA_API_KEY`. Saiful tops up the
   account toward the $100 cap.
8. **Still open:** decision 8.1, tuning the Room on the Beta model through the harness. It follows
   from "Alpha stays on-prem" and is treated as accepted unless Saiful objects.

## 3b. Saiful's rulings (2026-11-19)

1. **Alpha:** on-prem only. Primary `ami-llm` (192.168.20.74:8000); backup **Ling-3.0-flash-Fin** on our own host (`100.98.142.64:8004`, model `ling-3.0-flash-fin-fp4`, kind `vllm`, no key, thinking off). Live from deploy #8 (`alpha-2026-11-19-6`). No DeepInfra, Anthropic, Kimi or Gemini on Alpha.
2. **Beta:** primary `deepseek-ai/DeepSeek-V4-Flash`; backup **`inclusionAI/Ling-3.0-flash`** on DeepInfra (chosen over GLM-5.3-Flash after the re-score on the current image: 0/20 gate failures, 0.70¢ vs 1.06¢ per Room, 0.72 vs 1.23 min model time; scorecard §10). Ling needs `chat_template_kwargs.enable_thinking=false` in the request body: CR281's per-slot extra-body setting. Licence: MIT declared in the model card only, no LICENSE file; flagged for counsel.
3. **Model swaps are configuration only** (CR281): base URL, model, kind, optional API key (sent only when set), per-slot extra body; providers enforced by `LLM_PROVIDER_ALLOWLIST`, never by commenting keys out.

## 4. Order of work after S11

1. **In parallel (Sonnet workers, each verified by me):**
   - WP-15 (heuristics section);
   - WP-11 (temperature);
   - WP-12 (model column, cost, ceiling, Room cap);
   - WP-13 (guard, log-only);
   - WP-14's slot-kind and failover code, with the switch left OFF.
2. Promote to Alpha (primary still on-prem), then run WP-10 through the harness on melehost.
3. **S2:** Saiful picks the Beta model. It is used by the harness for WP-20 onward, and becomes
   primary only on the Beta host at go-live.
