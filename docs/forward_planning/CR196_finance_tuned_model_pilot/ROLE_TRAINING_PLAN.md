# CR196 §2c.4 — role-behaviour training: build plan

Written 2026-08-21 while run 1 trains (step ~900/3212). Covers everything between here and
a run-2 dataset. Run 1 is untouched by all of it — the GPU is busy, this work is CPU/network
on the Mac.

---

## A. Done and probed

| Recipe | Role | Probe yield | Verifiable label |
|---|---|---|---|
| 12 | `bear_researcher` | 6/12 | names 2–3 computed risks, never a 4th; downside quantified off the 52-wk low; stance envelope present |
| 13 | `bull_researcher` | 9/16 | attributes to the fact sheet (no invented analyst); concedes the top computed weakness; states a break level |
| 14 | `research_manager` | 11/20 | 3-part shape; picks the evidence-grounded side; **never says "short"** (asserted per example); grounded side alternates ~50/50 by hash |

All three render targets **from computed findings only**, and `assert_grounded()` raises if any
money or percentage token in a finished target was not computed by the generator. That guard has
already earned itself once: it caught `str.capitalize()` silently turning `$2.71B` into `$2.71b`.

Shared machinery: `role_common.py` (live role prompts + live `_STANCE_FORMAT` off a real
`room_prompts` load), `factsheet.py` (real filings + prices → computed `weaknesses`/`strengths`).

---

## B. First build step — cache the fact sheets (do this before anything else)

Recipes 12/13/14 each sweep the full universe independently. Adding 16 and 17 makes that five
sweeps of identical yfinance data. **Measured: 0.41 s/ticker at 6 workers → ~10 min per sweep**
(24/24 usable in the sampled batch; a longer sweep may hit rate limits, absorbed by
`common.yf_backoff` at 30 s × attempt).

Change: `factsheet.py` gains a disk cache (`out/factsheets/<TICKER>.json`) with a pull-date
manifest, and every recipe reads the cache. One sweep, five consumers, and the build becomes
reproducible — a rerun renders identical data without touching Yahoo, which is also what makes
the eval in §F honest.

Cost: ~1 hour of work. Saves four sweeps now and every re-render later.

---

## C. Recipe 16 — `trader` (Execution Desk)

The strongest verifiable contract in the set, because it is arithmetic.
`content/agents/trader.md` fixes the output block (Instrument / Side / Size / Entry / Target /
Stop / Time horizon / R:R) and forbids four specific things. Checkable labels:

1. **R:R is computed, not asserted** — `(target − entry) / (entry − stop)`, exact match. CR201's
   row records this arithmetic class failing four separate times
   (DEF066 → DEF235 → DEF241 → CR166 Tier-D). This recipe trains the one number that class keeps
   getting wrong.
2. **Size ≤ the cap implied by `risk_score`** — computed from the real mandate schema, the same
   source recipe 7 already imports. The prompt says plainly the floor does *not* catch this:
   "a size over the cap is not stopped here, it is simply wrong when you write it."
3. **Side ∈ BUY | HOLD | WAIT**, never a short when `long_only=true`.
4. **Stop-loss always present** — "Skip the stop-loss" is an explicit DO-NOT.
5. **No citing the Risk Officers** — they speak after the Trader, so referencing them is a
   provable hallucination.

Mandates come from the same generator recipe 7 uses; prices and levels from the cached fact sheet,
so entry/stop/target are real levels rather than invented ones.

*Cross-lane note, not mine to fix:* `trader.md` currently names "The Risk Officers (Aggressive,
Conservative, Balanced)" — copy that CR201 will need to revisit. Flagged once here, dropped.

## D. Recipe 17 — `risk_officer` JSON (replaces the cancelled recipe 15)

Targets `build_risk_officer_instruction()` in `backend/app/services/risk_officer.py`. Checkable
without an LLM judge: exactly one entry per handed size · no invented size · `recommended` ∈ the
handed sizes · `key_number` quoted from evidence, never computed · no self-authored drawdown or
cap figure · `confidence` genuinely separating.

**Gated on CR201, deliberately.** The officer is landed but `ROOM_RISK_OFFICER_ENABLED` is off and
arm v8 has not been re-run against the production assembly. Building training data against a
contract that may still move is how you get a stale dataset. **Recommendation: hold 17 until
CR201 enables**, and ship run 2 with 12/13/14/16 if that has not happened. Nothing else depends
on it.

---

## E. Build execution

1. Cache sweep (§B) — ~10 min measured, one time.
2. Render 12, 13, 14, 16 from cache — CPU only, seconds.
3. Expected volume, from probe rates against 1,437 tickers: ~700 (12) + ~800 (13) + ~790 (14)
   + ~700 (16) ≈ **3,000 role examples**, against ~8.6k Tier A and ~17.5k Tier B in run 1.
   That is 10–11% of a combined mix — proportionate for a behaviour that is 5 of 13 roles, and
   in line with the per-recipe density of Tier A.
4. Through `mix_and_qc.py` unchanged: dedup, decontamination hard-fail, deterministic 2% hash
   val split, manifest. **The decontamination check is not optional here** — every role recipe
   draws from the same `train_universe.txt`, and the 71 frozen `eval_tickers.txt` exclusions are
   what make §F a real held-out test.

## F. Role-behaviour eval — closes a real gap in CR196 §5

CR196's acceptance list has an eval for the basis rubric and none for role behaviour. Because
every label here is programmatic, **the generator code is also the scorer**: render the same
briefs against the 71 held-out eval tickers, run the model, and score its output with the
identical checks that produced the training labels. No LLM judge, no human grading.

Reportable numbers, per role: risks-named recall and fabrication rate (12) · attribution and
break-level compliance (13) · grounded-side accuracy and short-language rate, which must be 0 (14)
· R:R exact-match rate, cap violations, missing stops (16).

Baselines: vanilla Fastino and Qwen3.6, the same two the basis rubric uses. This is where "did
role training work" gets answered with a number rather than a reading.

## G. Run 2 assembly and sequencing

- **Fresh LoRA from the Fastino base**, not a continuation of run 1's adapter. Continuing would
  add substrate steps as well as role data and confound the comparison; fresh-from-base on the
  combined mix makes run1-vs-run2 a clean read of what the roles bought.
- Run 2 also carries §2c.1–3 (exact-format rendering, `llm_audit` prompts, measured prompt
  compression) — all still open, none blocked by this.
- **Sequencing constraint, from CR201 §9.3:** do not enable `ROOM_RISK_OFFICER_ENABLED` and swap
  the `:8000` model in the same window, or neither effect is attributable. Same argument CR201 §8
  already makes for `PM_OPTION_LADDER_ENABLED`.
- Nothing here touches run 1, the adoption gate, or production.

## H. Decisions for Saiful

1. **Recipe 17 — hold for CR201, or build against the current contract and accept rework?**
   Recommend hold.
2. **Recipe 16's mandate spread** — reuse recipe 7's distribution, or weight toward the
   near-cap cases where the arithmetic actually bites? Recommend the latter; that is where the
   four recorded defects live.
3. **Run 2 timing** — start assembling as soon as run 1's eval reads out, or wait for the
   adoption-gate decision first? Recommend assembling early; the data build is free of the GPU.
