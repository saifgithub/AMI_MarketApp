# CR214 — Testing the Room for an edge: a rebuilt backtest, then forward tracking

Filed 2026-08-31 (AT:R74). Status: in_progress. Plan approved by Saiful in-session 2026-08-31.

## Why

CR164 Phase B is on record as *"no outcome edge is demonstrated."* Read literally that is
wrong. It did not find zero — it found **nothing**:

| | 4w excess vs SPY |
|---|---|
| APPROVE (n=40) | +1.40% |
| PASS (n=406) | +0.25% |
| **spread** | **+1.15%** |
| date-clustered 95% CI | **−2.05% … +4.43%** |
| random-pick null | p = 0.3010 |
| **effective n** | **18 as-of dates** |

An instrument with ±3.2 points of resolution cannot resolve a 1-point effect.
`RETEST_RECIPE.md:115` already says as much — *"the baseline does not establish edge, it
establishes a measurement."* Phase B's own headline is stronger than its numbers support,
and this CR exists because the distinction between **no edge** and **no measurement** is
the whole question.

Every Room outcome measurement we hold has the same disease — **1–4 approved names per
date**, so per-date idiosyncratic noise swamps everything:

| Batch | signal names | dates | names/date | 95% CI on the spread |
|---|---|---|---|---|
| CR164 pilot | 13 APPROVE | 71 | 0.2 | −4.98 … +14.26 |
| CR164 Phase A | 9 APPROVE | 71 | 0.1 | −1.48 … +13.69 |
| CR164 Phase B | 40 APPROVE | 18 | 2.2 | −2.05 … +4.43 |
| CR157 live retro (pooled 2026-08-31, this CR) | 69 BUY | 28 | 2.5 | −9.78 … +5.68 |

The last row was measured for this CR by pooling the two committed
`weekly_retro/scored_*.jsonl` files (303 live runs, 46 as-of days, 2026-05-14 → 2026-08-21;
120 scoreable at 20 trading days). Per-name 4-week excess SD is **13.0%**, so a date-mean of
two stocks carries ~9 points of noise on its own. **More dates cannot fix that.** The fix is
more signal names per date plus a lower-variance estimator.

Three power leaks, all fixable inside the existing budget:

1. **The verdict is ~12–20% coin flip.** No `temperature`/`seed` exists anywhere in
   `llm_gateway.py`, and `pm_self_consistency_samples` defaulted to **1**. Three
   byte-identical replays of 136 convenes disagreed on 26 of 132. At a 9–28% approve rate a
   large share of APPROVEs are sampler noise, which dilutes a true effect toward zero.
2. **91% of compute lands in the PASS bucket.** The verdict is binary, so only the approving
   minority carries signal; 406 of Phase B's 446 convenes bought almost nothing.
3. **18 of the available Fridays used.** The window is fixed by the cutoff probe, and Phase B
   spent 25 convenes each on only 18 dates. Effective n *is* dates, so the rest were left on
   the table.

## What

Turn the verdict into a **0–5 graded score**, spend the batch on **~100 names × ~30 dates**,
and score by **per-date rank correlation** so every convene contributes — then keep the
instrument running forward.

Projected resolution from the measured 13.0% per-name SD. **This is a projection, not a
measurement**, and is re-checked against achieved numbers at the Step 3 gate:

| Design | signal/date | detectable |
|---|---|---|
| Phase B as built (25 × 18, bucket) | 2.2 | spread ≳ 3.2 pt |
| Rebuild (100 × 30, bucket) | ~10 | spread ≈ 1.2 pt |
| Rebuild (100 × 30, **rank on 0–5 votes**) | 100 | IC ≈ 0.036 |

Published cross-sectional ICs run 0.02–0.05, so the rank arm is the first version of this
test that sits where a real signal would be visible at all.

## Scope

**Step 1 — turn the noise floor down (this commit).**
`pm_self_consistency_samples` 1 → 5, in `config.py` **and** in `docker-compose.yml`, which
pinned `:-1` and would otherwise have kept Alpha at one sample however the code read (CR040).
`Verdict` gains `approve_votes` + `samples`; `room_runs.verdict` is JSONB so **no migration**.
The count is of APPROVE/MODIFY draws regardless of which side won — the existing agreement
string counts the *winner*, so it collapses 2-of-5-approve and 0-of-5-approve into the same
PASS. Separating them is the point.

Uncovered on the way in and fixed here as **DEF383**: the vote branch had never executed in
production, and `room_runner.py` logged `verdict.action.value` on a `use_enum_values=True`
field — an `AttributeError` that would have taken down the PM phase of every convene the
moment this CR's default landed.

**Step 2 — fix the estimator (no convenes).** In `backtest_report.py`: per-date
Spearman(`approve_votes`, forward excess) with the existing date-clustered bootstrap;
within-date paired spread instead of the pooled difference (cancels the market factor
exactly); a **matched-random placebo** arm (RES001's binding rule — any selector looks good
if it merely selects fewer); a 90-day cell beside the 20-day one, since stated horizons have
a median of 90 days and *"the four-week numbers grade name selection, not whether these
theses worked"*. Fold in CR213's distance-normalised geometry while the file is open.

**Step 3 — pre-register, then sweep.** Pinned `--pairs-file`, `tickers_142_no_splits.txt`,
~100 names × the available Fridays, definition/holdout split with the holdout **disjoint from
the 18 dates in `pairs_r70-outcome-1.jsonl`**. One shot. Interim read at ~half the dates is
**descriptive only** — achieved CI width, no verdict; optional stopping on the point estimate
would burn the test.

> **Window corrected 2026-08-31 — see [DEF385](../../defect/_registry/DEF385.row.md).** The
> served model changed under this CR (CR211: Qwen3.6 → `qwen3.8-flash-next`, the alias
> `ami-llm` reused across the swap). A fresh cutoff probe moves `window_start`
> **2025-02-28 → 2025-08-01**: price-collapse 2024-08 → 2025-01, last recalled event
> 2025-01 → 2025-06. **Usable Fridays: 52** (2025-08-01 → 2026-07-27) at the 20-day horizon,
> **~43** at the ~90-day one — the sweep planner confirms 52. Had this not been caught, ~3,000
> convenes would have run with every date before 2025-08-01 inside the model's own memory.
> The power arithmetic survives: 100 names × 52 dates resolves a rank IC of **≈0.028**,
> slightly better than the 100 × 30 projection above.

**Step 4 — track forward.** `weekly_room_retro.py` is already on melehost cron and accrues
~150 live runs/week at zero marginal cost during the sweep; what is missing is **pooling** —
each weekly report is small-n alone and nothing has combined them under the CR164 controls.
After the sweep the budget rolls into a pinned weekly live slate via `room_benchmark.py`
(`baseline150fix-2026-07-20`, n=144, is week 0 and already banked).

## Acceptance

1. `pytest backend/tests/unit/ -q` green, including `test_config_compose_parity.py`.
2. DEF383 regression: no `.action.value` survives anywhere in `room_runner.py` (AST-level
   guard, since the crash is at a call site with no unit seam).
3. `approve_votes` distinguishes a split PASS from a unanimous one, survives the JSONB round
   trip, and is `None` — never `0` — when the knob is off. Absence is absence.
4. Flip-rate gate **before any sweep spend**: 26-pair repeat batch shows the floor actually
   moved. If it did not, stop — the sweep is not worth running.
5. Scorer stays byte-reproducible; re-running `r70-outcome-2` reproduces every existing cell
   exactly, with only new cells added.
6. Live check that self-consistency is on in Alpha, not merely in config.

## Kill criteria (stated now, so a null is readable as a null)

- Placebo-adjusted IC interval contains zero **and** achieved CI ≤ pre-registered width ⇒
  **no edge**, reported as a result.
- Placebo-adjusted IC interval contains zero **and** achieved CI wider than planned ⇒
  **underpowered**, reported as a non-measurement. Say which.
- Definition set positive, holdout negative ⇒ **no edge.** One shot.

## Limits to carry into any write-up

- **Tested Room ≠ shipped Room** — news, social and analyst consensus are `UNAVAILABLE`
  under as-of, which is why the backtest approves ~10% against the live Room's 24–37%.
- **52 Fridays is the ceiling** on the current model, fixed by the cutoff probe and shrinking
  as the model gets newer. Not extendable. Re-probe whenever the serve changes — nothing ties
  `--window-start` to the model actually answering (DEF385).
- `tickers_142_no_splits.txt` excludes 8 names *because they split*, and splits correlate
  with appreciation. It hits both buckets, so the spread should be near-unbiased — but say it.
  DEF335's root fix (`auto_adjust=False` re-backfill, 119,311 rows / 201 tickers) stays deferred.
- **Long-only, no portfolio** ⇒ selection edge only. No Sharpe, ever (Lo 2002).
- Convene-time reference price is not persisted; every scorer uses prior close.

## Out of scope

- Changing agent behaviour on the strength of results (evidence-gated, a later CR).
- Any Sharpe, portfolio or alpha claim.
- Reporting a re-test as evidence the Room improved — `RETEST_RECIPE.md`'s standing rule.

Related: CR164 (the harness), CR157 (the live-run scorer), CR197 (the vote machinery),
CR213 (level geometry), DEF383, DEF335.
