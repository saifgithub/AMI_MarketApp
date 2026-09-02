# GLM/ — reviewer package for CR219

One of several independent reviewer takes on CR219's proposed enhancement plan, combined
with the other reviewers' packages before anything is built. Written 2026-09-02 by a
GLM session against the parent folder's evidence and the live source. **Docs only —
nothing in code, prompts, personas, or tests was changed by this review.**

TRACK: K · ROLE: GLM · INSTANCE: - · Session tag: AT:K2

## What's here

| File | What it answers |
|---|---|
| [`01_review.md`](01_review.md) | Do the 17 findings hold? Do the three reviewer packages agree? Where do they conflict? |
| [`02_improved_plan.md`](02_improved_plan.md) | The phased enhancement plan with Saiful's five rulings folded in. |
| [`03_target_prompt_set.md`](03_target_prompt_set.md) | The target prompt architecture — what the Room's prompt set looks like after the fix, and the principles that make it the best at evaluating a ticker. |

## Saiful's rulings (2026-09-02, this session) — treat as resolved

These answer the forks the three reviewer packages left open, and supersede any
prior reviewer decision they touch:

| # | Question | Ruling |
|---|---|---|
| R1 | Fix mechanism | **Hand-fix + guard** — correct the 8 denials by hand, add a truth-checking guard that scans the whole persona against the rendered sheet. Not the generated data-boundary block (fable), not a static contract block (antigravity). |
| R2 | `primary_goal` rendered but inert | **Wire as weighted guidance** — goal-specific overlay lines per agent; PM keeps holistic gatekeeping, no hard-coded filter gates. |
| R3 | Class D — the 8 downstream briefs | **Name the sheet + numbers rule** ("quote the sheet's figures; do not re-derive"). |
| R4 | Data additions scope | **All in CR219** — free fields first, then ATR, historical median multiples, debt split, earnings revisions; each with persona lines + guard entries in the same commit. |
| R5 | PM-only thinking-mode experiment | **In CR219, measured** — Phase 4, alongside the benchmark. |

Note on supersession: fable's README records "generated availability section" as its
resolved decision #1 and "Class D — acknowledge, don't restrict" as #3. R1 and R3 above
replace both. Kimi's D1 (name + numbers rule) is confirmed by R3; kimi's D2/D4/D5/D6
rulings are confirmed by R2/R4/R5.

## Bottom line

The investigation is sound and the findings stand — I verified the load-bearing claims
in source, not from the doc. The three reviewer packages disagree on the fix mechanism
and on two facts; the rulings above resolve the forks, and the fact conflicts resolve
in kimi's favour (the CR doc's "defaults to 1" and "uncommitted hunk" lines are stale).
The plan in [`02`](02_improved_plan.md) is kimi's skeleton with the rulings folded in,
plus fable's collision-marker idea stolen into the guard design — the one piece of the
rejected generated-block approach worth keeping.
