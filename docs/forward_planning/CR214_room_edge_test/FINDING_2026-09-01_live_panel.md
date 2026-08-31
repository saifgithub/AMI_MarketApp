# The live-Room panel cannot carry the edge test — and one of its numbers was overstated

**Date:** 2026-09-01 · **CR214 Step 4** · zero convenes spent

## What was checked

The approved plan's Step 4 calls the forward arm "the one that eventually
matters", on the grounds that the live Room is the un-ablated Room — news,
social and analyst consensus are `UNAVAILABLE` under as-of and present live —
and that `weekly_room_retro.py` accrues scored runs for free. Nothing had ever
pooled those weekly files or run CR164's controls over them. This did, through
the *same* estimator functions `backtest_report.py` uses (extracted to module
level for exactly this reason), so the numbers are comparable by construction.

## Correction: the panel is 162 runs, not 303

`weekly_room_retro.py`'s output is **cumulative, not incremental**. Measured:

| file | runs | unique |
|---|---|---|
| `scored_2026-W34.jsonl` | 141 | 141 |
| `scored_2026-W35.jsonl` | 162 | 162 |
| **overlap** | **141 of 141** | W34 ⊂ W35 |

Globbing the directory double-counts every earlier run and reports **303 runs
over 46 dates** where the truth is **162 over 28**. Every clustered interval is
computed against a date count, so the inflation is not cosmetic. The pooling
scorer now reads the newest file alone and a test pins the refusal.

## The numbers

Un-ablated live Room, 162 runs, approve rate **26.5%** (vs the as-of backtest
Room's ~9-10% — that gap is the ablation).

| arm | horizon | estimate | 95% CI | dates |
|---|---|---|---|---|
| within-date paired | 1w | **−1.09%** | −5.11 … +2.88 | 8 |
| within-date paired | 4w | **+1.19%** | −1.63 … +3.83 | 4 |
| placebo-adjusted | 1w | **−0.42%** | −2.01 … +1.09 | 16 |
| placebo-adjusted | 4w | **+0.30%** | −0.32 … +1.09 | 12 |

**The +1.19% figure previously carried as live corroboration rests on 4 dates.**
On the placebo arm — which RES001 mandates, because any selector looks good if
it merely selects fewer, and which here has 3× the dates — the same panel gives
**+0.30%**, with a *tight* interval. At 1w both arms are negative. So the live
panel does not corroborate the +5.09% backtest finding; it is closer to a
well-bounded nothing at 4w and a mild negative at 1w.

That is not a contradiction of the headline — different horizon (4w vs ~13w),
different Room (un-ablated vs ablated), different panel — but the four-positive-
estimates story is weaker than recorded, and the honest count is three.

Two further caveats the report prints rather than averages away:

- **The panel spans more than one prompt generation** — 67% `unversioned`, 33%
  `mixed:…`. Every figure above is an average over versions of the Room.
- **The live scorer stops at 20 trading days**, so the ~13-week cell where the
  backtest finding lives has no live counterpart yet. Not zero — absent.

## Why this arm cannot be fixed by waiting

| horizon | dates with both buckets | runs per date |
|---|---|---|
| 1w | 8 of 44 | 3.6 |
| 4w | 4 of 28 | 2.6 |

A within-date spread needs both legs on the same day. Organic convenes do not
supply them: **2.6 runs per date** means most dates are single-bucket, so 24 of
28 scored dates contribute nothing to the paired arm. This was initially
misread as a price-coverage problem — 20-day scoring is 100% complete through
2026-07-25 and 0% from 2026-07-30, which looks exactly like a stale price store.
It is not. Bars are present (`entry` 99%, `excess5` 98%); the recent dates
simply have not aged 20 trading days at the time the last weekly run scored
them, and they will score themselves on the next run. The date count will grow;
**the 2.6 runs per date will not**, because it is a property of how one user
convenes, not of elapsed time.

## What follows

The plan already names the fix and this is the evidence for it: roll the budget
into a **pinned weekly live slate** (`room_benchmark.py` runs ~150 names on one
date) rather than relying on the free retro accrual. ~100 names on ONE date
supports a within-date estimator; 2.6 names on 28 dates does not. The retro
panel stays valuable as a cheap monitor and as the only un-ablated signal we
have — it is not an instrument for detecting a 1-5 point effect.

## Provenance

- Scorer: `backend/scripts/live_retro_pool.py`, on `backtest_report.py`'s own
  `paired_spread` / `placebo_effect` / `clustered_ci`.
- The extraction of those three from `main()` was verified behaviour-preserving:
  re-running `r70-outcome-2` reproduced the committed report with **zero numeric
  differences** and a byte-identical `scored_*.jsonl`; the only diff is the
  DEF388 prose change.
- Report: `backtest_results/weekly_retro/pooled_2026-W35.md` (melehost).
