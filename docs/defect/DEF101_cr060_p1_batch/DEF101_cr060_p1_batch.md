# DEF101 — CR060 P1 batch: mis-grading quiz keys + non-genericizable false facts

**Status:** open — apply-ready, routed to the `noncoder.edu` education lane.
**Filed:** 2026-07-24 (AT:R64 CR060). **Owner split:** CR060 (Claude) verifies + produces the
fix list; the education lane edits the `.mdx`.

## What this is

The processed P1 output of the CR060 content-quality sweep (334/334 lessons measured, 293
findings). A finding is **P1** when it either:

1. **poisons a graded quiz** — the keyed answer is not the one a learner reasoning from reality
   would pick, so the assessment marks the correct learner wrong or certifies a false value; or
2. **states a false fact no illustrative framing can rescue** — a wrong ticker, definition,
   regulator, attribution, market mechanic, or product field.

150 lessons after re-validation (QUANT 9/343 dropped as an AI false-positive on dual-pass).

## The deliverable

**`content/_authoring/cr060_phase3_fix_list.md`** — per lesson: the exact `old → new` string, the
quiz key to correct, and the primary-source citation backing the new value. The education lane
applies it with **zero research**. Raw per-row provenance (verify + refute verdicts) in
`content/_authoring/cr060_phase3_results.json`.

## How the values were verified (not trusted)

The classification manifest's proposed corrections were treated as **leads only**. A 284-agent
dual-pass established every correct value: a verify agent sourced it from a primary source /
computation / the repo, then an **independent adversarial refute agent** re-derived it from
scratch. 126 confirmed, 15 refuted (owner-triaged in the fix list), 1 already fixed.

**It mattered — nine leads were wrong** and would have swapped one unverified value for another:
AMZN 2→4 splits and $180→$235; a 20%-drawdown recovery of ~22 months mislabelled "under a year";
a "+18%" that is actually +8.7%; $173 called an all-time high when it is a measured-move target.
And QUANT 9 was dropped when refute showed the quiz option was correctly keyed all along.

## Carve-outs (NOT in this batch)

- **DEF098** — 30 lessons teaching phantom Mandate fields — is the code-truth sub-batch. Its
  class-A rows fix uniformly to the `risk_score`-derived cap; its 6 class-B "SCOPE" lessons are
  **blocked** on the richer-Mandate build-or-remove decision (Saiful).
- **11 legal/Sharia escalations** — SME-only, never auto-fixed (294, 296, 297, 299, 347, 351,
  353, EDGE 23, FUND 25, EDGE 15, SHARIA 6).
- **P2 genericize/soften tail** — CR086.

## Definition of done

Every P1 lesson's quiz key is the reality-correct answer and every false fact is corrected to its
sourced value; `backend/tests/unit/` stays green; the DEF064/065 quiz invariants hold; and the
`repo_truth_check.py` guard (DEF098) is promoted to a corpus pytest once the phantom-field cohort
clears.
