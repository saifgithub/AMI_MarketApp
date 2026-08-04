# Audit run 2026-08-04 run-01 — CR136-M04, round 4

Auditor track U. Round 3 closed COMPLETE with zero findings; this round is not a
fix to a finding but the deferred half of §5.4 — **DEF213's guard** — plus an M07
comment correction parked here because M07 is closed.

Audited at **`20d8268f`** (code fix `b335bfb4`) in a detached, clean worktree
`.claude/worktrees/audit-m04r4`.

Verdict: **COMPLETE (round 4)** — zero BLOCKER, zero MAJOR, 2 non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M04.auditor.md`.

## What the guard is

`window_days / n_observations > GRID_DENSITY_MAX (1.65)` sets
`insufficient_cause: sparse_grid` on every Σ-derived block. The engine already
computed and published both numbers in every block; it never compared them.
`short_window` is checked first and wins.

## The derivation reproduces exactly — re-run live, not read

`def213_guard_threshold.py` against live Yahoo:

```text
worst clean-book ratio anywhere:                     1.4921
worst incl. constructed closures (L=5, 126 returns): 1.5556
mean clean ratio:                                    1.4535
```

All three match §7 to the digit. 1.65 clears the constructed worst case by 6.07%
and the observed one by 10.6%; `1.4535 / 1.65` puts the firing point at 11.91%
of one holding's days missing. The script measures the clean **maximum**, not the
mean — the right statistic for a false-fire budget.

## MUT-3, self-reported and correctly fixed

Tightening 1.65 → 1.45 (below the measured clean maximum of 1.4921) originally
passed all 44, because `_dates` builds weekdays only so every fixture sat at
exactly 7/5 = 1.40. The repair reproduces both measured densities as fixtures
rather than asserting about them. Re-performed at 1.45 / 1.50 / 1.55 — dies at
all three.

Third time in CR136 a guard held only on a calendar or clock production does not
use (round-1 QA-C, M07's `TZ`, this).

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| `test_cr136_metrics_engine.py` | 44 | **44 passed, 2.32s** | exact |
| full `tests/unit/` | 2290 | **2290 passed, 284.20s** | exact |
| `flutter test` | 502 | **502 passed** | exact |
| `flutter analyze` | 6 issues, 0 errors | **6 issues, 0 errors** | exact |
| MUT-1…6 | 2/1/1/1/1/1 | **2/1/1/1/1/1, names match** | exact |
| threshold script | 1.4921 / 1.5556 | **1.4921 / 1.5556** | exact |

11 mutations run in total (his 6 + MUT-3′ at three levels + my AUD-1/AUD-2 +
a 4-point bisect); tree clean after every one.

## MINOR m1 — the justification is contradicted by its own adjacent numbers

`GRID_DENSITY_MAX`'s comment, DEF213's row and CR139's row all say the line sits
just past where the bias overtakes the estimator's error bar (F17: 6.29–6.37%),
"so below the line a gap costs less than the sampling noise." His own measured
points: +6.1% at 5% missing (inside), **+7.9% at 10% missing (outside)**, guard
fires at 11.9%. Crossover is ~5–6%; the line is ~2× further out.

My independent 12-seed measurement — one true path per seed generated on the full
grid then **subsampled**, so the asset is identical and only reported days change
— gives **+9.1% mean bias at ratio 1.6439**, immediately below the threshold.

Not graded higher: nothing user-facing is wrong and 1.65's placement is not in
question, being forced from below by the false-fire budget. §7's attack list says
exactly that — *"1.65 is a false-fire budget, not a correctness threshold"* — and
that honest sentence reached none of the three durable documents. It matters
because CR139's stated priority rests on the claim verbatim.

## MINOR m2 — pinned tightly from below, loosely from above

```text
AUD-1  1.65 -> 1.60   44 passed  SURVIVED
AUD-2  1.65 -> 2.20   44 passed  SURVIVED
bisect: pinned to (1.5558, 2.3311)
```

The upper bound is `_book_thinned(500, 300)`'s own ratio (697/299 = 2.3311) — a
fixture built to demonstrate the branch, not a chosen bound. Tightening slack
5.7%; loosening slack **41.3%**, at which point the guard fires only above 37.6%
missing days, admitting books measured at ~+29% overstated σ. The tightening
direction is the one he found and fixed; the loosening direction — the one that
reopens the defect — is the loose one.

## Not graded — the ratio is shape-blind (recorded for CR139)

Same 75 missing days, same resulting ratio, two arrangements, 12 seeds:

```text
ratio 1.6439, 424 observations
  contiguous (one 75-session halt)   mean bias  +0.2%   [-0.0%, +1.1%]
  even thinning (75 scattered days)  mean bias  +9.1%   [-0.4%, +17.8%]
```

~45× difference in harm at an identical guard reading. Variance is additive: a
return spanning k days carries the variance of all k, so a contiguous gap loses
almost nothing while scattered gaps convert many multi-day moves into "daily"
ones and √252 over-scales each.

Contiguous sweep — the guard does not fire until L=90, and at L=75 the σ it is
on the verge of refusing is overstated by 0.7% (single seed) / 0.2% (12-seed
mean):

```text
hole L=20  ratio 1.4551  sufficient  +0.0%
hole L=60  ratio 1.5877  sufficient  +0.1%
hole L=75  ratio 1.6439  sufficient  +0.7%
hole L=90  ratio 1.7042  REFUSED  sparse_grid
```

Not a defect: the guard errs conservatively on the contiguous side, and the
diffuse case below the line is deferred CR139 territory under Saiful's
"guard now, correct later". Recorded because CR139's scope says the guard must
be "re-derived or retired" once annualisation fits the grid — this is the
argument for **retired**. No single value of a shape-blind ratio separates a
+0.2% book from a +9.1% one; re-annualising by realised period length does, by
construction.

## Checked and accepted

Ordering (MUT-4 kills the short-vs-sparse test; the `private=` fixture change it
forced is a real subtlety). The card path — a sparse grid sets the cause on all
four core blocks, so `_allInsufficient` holds and `_InsufficientState` names the
feed rather than the book; `_notes` correctly never runs. The ARB carries
`retranslate:[ar,ms]`. MUT-6 did not need performing: the DEF210 parity test
failed on the commit that minted the seventh cause, before the card had seen it
— that guard firing on its first real occasion is the strongest single item in
the submission. DEF213 `done` is correct and its row says why in the right words.

## Probes preserved

`m04r4_mut.sh` (mutation battery), `m04r4_probe.py` (contiguous-vs-even shape
comparison), `def213_thresh.txt` (live re-run of the threshold script).
