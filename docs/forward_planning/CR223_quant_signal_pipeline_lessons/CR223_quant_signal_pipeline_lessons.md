# CR223 — The alpha-extraction pipeline, taught as QUANT 13–15

**Filed** 2026-09-13 · **Status** done · **Session** AT:R76

## What prompted this

Saiful surfaced a 12-equation framework — "A Unified Framework for Alpha Extraction and
Signal Combination" — and asked a single question: *do we use these steps?*

The answer was no, with one exception worth knowing about. The audit:

| Steps | Status in AMI Trade |
|---|---|
| 1–2 (time-series demean, variance) | Partial — EWMA-weighted, in `backend/app/trading_math/portfolio_risk.py:188-200`, for risk reporting rather than signal construction |
| 3, 4, 6, 7, 8, 9 (z-score, truncate, expected return, normalise, orthogonalise, inverse-vol weight) | Absent. No `lstsq`, `polyfit` or `numpy.linalg` anywhere in `backend/` |
| 5 (cross-sectional demean) | Absent — zero occurrences in `backend/` |
| 10 (Σ\|w\| = 1) | Partial — holdings-share normalisation for HHI, a different role |
| 11 (weighted composite signal) | Absent **and** against a standing decision — "No composite score" (CR136) |

## Why this became lessons rather than a refusal document

The first plan for this work was a research-lane document recording the refusal. That was
the wrong shape, and Saiful redirected it: *"we should add this to the knowledge base that
we give to the users in one or more lessons."*

He was right. The reasoning behind the refusal is genuinely useful to a learner, and it
was scattered across four internal documents that no user can read and that no single
session reads together:

- `CR136_portfolio_health_metrics.md:69-110` — mean returns are not estimable at retail
  horizons; mean-numerator metrics excluded permanently.
- `docs/Research/benchmark/claude/09_rejected_approaches.md` R1 — portfolio construction
  for the purpose of making risk-adjusted return measurable.
- `docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md:130-175` — we ran the
  cross-sectional test and the edge vanished.
- `docs/initial_specs/11_decisions/rejected_features_register.md:19` — R1's one-row summary.

None of them is about *signal construction*, which is why the middle of this pipeline had
never been refused in writing and stayed re-proposable. Teaching it closes that gap in the
place where it does the most good: a CEO-analyst handed this framework can now name each
step and ask the right question of it, instead of being impressed by the notation.

## What shipped

Three lessons, `quant_methods` track, **new module 27**, Level 12:

| id | code | Lesson |
|---|---|---|
| 400 | QUANT 13 | Standardising a signal before you combine it (steps 1–5) |
| 401 | QUANT 14 | Combining signals: orthogonality and weights (steps 6–11) |
| 402 | QUANT 15 | Capstone: why a clean pipeline still fails |

**Every worked number is reproducible by hand.** The three hypothetical series were chosen
symmetric so each standard deviation is a whole number (2, 5, 1); the z-scores are 4, 1, 1;
the cross-sectional mean is 2; the demeaned values are +2, −1, −1 and sum to exactly zero.
In 401, correlation 0.8 gives R² = 0.64 and a 36% residual, and inverse-volatility weights
from an identical 0.6 signal at volatilities 1, 2, 2 normalise to exactly +50%, −25%, +25%
with Σ|w| = 1. No CR046 module covers z-scores or cross-sectional demeaning, so these were
hand-computed and independently recomputed before authoring.

### Why module 27 and not M21

`test_every_capstone_is_the_last_lesson_in_its_module` keys on `l.meta.module`, not on
track. Appending to M21 would have made 402 outrank shipped capstone 346, forcing a rename
of `346_capstone_stress_testing_a_strategy_claim` — which carries AR and MS siblings and
appears throughout `content/i18n/lesson_confidence_log.json`. A new module leaves 346 and
its translations untouched. The track (`quant_methods`) is unchanged, so no track wiring
moved.

### The Tier 4 registry change

Lesson 402's strongest reason is our own measurement, and `source_registry.md` had no tier
for first-party work — its standing rule is "AI-generated text is never a source of fact."
Rather than teach the principle with invented figures while the real measurement sat in an
internal doc, this CR admits a deliberately narrow **Tier 4 — First-party measurement**:

- **Null and negative results only.** A first-party *positive* result is a performance
  claim and remains inadmissible at any tier (D-004).
- **Reproducible from committed artifacts.**
- **Always cited with its universe and window**, and stated in the lesson body as our
  result on that data — never as a general law.

Lesson 402 states the 0.5528 → 0.5055 (p=0.62) collapse as AMI's finding on 32 large-caps
over 2,891 trading dates, and says explicitly that a different universe, horizon or data
source can give a different answer. That hedge is flagged as load-bearing for translation.

## What this CR does NOT do

- **No product behaviour changes.** No backend code, no new metric, no pipeline built. The
  refusal stands; this documents it in the curriculum.
- **No register or decision-log entry.** Saiful's call: long-form teaching content only,
  no `D-071` and no rejected-features row.
- **No AR/MS.** EN only, `locale_versions: ["en"]`, flagged for the i18n lane in
  `content/_authoring/cr223_quant_pipeline_translate.md`.

## Verification

```
cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py \
  tests/unit/test_cr054_canon_sourcing_spine.py tests/unit/test_lessons_service.py -q
→ 56 passed
```

Beyond the suite: every worked figure recomputed independently; the CR136 standard-error
table reproduced from σ÷√years and σ÷√(2T) (40.0 / 20.0 / 8.9 / 4.5 pp against 1.78 / 0.89
/ 0.40 / 0.20 pp) rather than copied; the DEF065 option-index regex run over all quiz
surfaces *and* lesson prose, which caught two ambiguous prose phrasings the test's
quiz-only scope would have allowed; quiz answer positions spread across indices 1, 2 and 3
per CR042; `locale_staleness_check.py` confirms the three new ids report as EN-only rather
than stale.

`LESSON_COUNT_FLOOR` bumped 372 → 380 (377 on disk + 3). It stays a `>=` floor, per
`test_cr054_guard_capstone_floor_pin.py`.
