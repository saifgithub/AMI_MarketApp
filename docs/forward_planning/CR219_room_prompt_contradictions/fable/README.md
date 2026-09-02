# fable/ — Fable reviewer package for CR219

One of several independent reviewer takes on CR219's proposed enhancement plan, to be
combined with the other reviewers' packages before anything is built. Written 2026-09-02
by a Claude Fable 5 session against the parent folder's evidence and the live source.
**Docs only — nothing in code, prompts, personas, or tests was changed by this review.**

## What's here

| File | What it answers |
|---|---|
| [`01_review_of_findings.md`](01_review_of_findings.md) | Do the 17 findings hold up? What does the record miss? |
| [`02_generated_availability_design.md`](02_generated_availability_design.md) | The core structural recommendation: a generated, registry-backed "data boundary" block that cannot drift. |
| [`03_scope_recommendations.md`](03_scope_recommendations.md) | Per-finding resolutions and what else rides in CR219 (free fields, ATR, `primary_goal`). |
| [`04_acceptance_and_measurement.md`](04_acceptance_and_measurement.md) | Revised acceptance criteria and the trailing measurement. |
| [`05_further_improvements.md`](05_further_improvements.md) | Second pass beyond the contradictions: decision variance and decision inputs — 15 ranked items, incl. two live-verified findings (PM verdicts ~19.7% sampling noise at n=1; thinking mode off on the live model). |

## Decisions Saiful made during this review (treat as resolved, not open)

1. **Fix mechanism — generated availability section.** The per-agent "data you have /
   do not have" statement is *generated from the same code that renders the fact sheet*
   (single source of truth). Personas keep voice and method prose only; a guard bans and
   truth-checks any residual availability claim in free prose. Chosen over the CR's
   original "hand-fix the 8 denials + truth-checking guard" — prevention over detection,
   per CR038 (structural beats prose).
2. **Scope — one CR.** Everything that improves the Room's decision rides in CR219
   itself: the 17 findings, the guard, the zero-cost data fields ("the free ones"), and
   a `primary_goal` resolution. No sibling CR split.
3. **Class D — acknowledge, don't restrict.** The 8 downstream agents keep receiving the
   full sheet; their briefs are updated to say so. Lane restriction, if ever, is a
   separate measured change.
4. **AC4 trails.** The post-fix citation-rate re-measurement on Alpha traffic follows the
   merge (~1–2 weeks of traffic); it does not gate it. No movement = a new finding, not
   a revert.

Second round (2026-09-02, on the [`05`](05_further_improvements.md) items):

5. **CR210 diffs: committed with their evidence.** The four working-tree files plus the
   untracked 2026-08-27 arm artifacts were committed (`fix(CR210)…`, AT:R75 CR210) with a
   results note (`CR210_.../results/acceptance3_wrong_constraint_regressions.md`). Open
   item recorded there: the post-fix arm has never been re-run — do that before either
   constraint flag is enabled on Alpha.
6. **`h_short` harness artifact: disclosed in the parent now** — third item in
   `evidence/README.md`'s "does NOT support" section, so reviewers reading the arms today
   aren't misled.
7. **Infra split: eval harness stays inside CR219; the verdict-outcome ledger becomes its
   own CR** (to be minted at the combine step — not minted by this review track, one
   ID-minter rule).
8. **Outcome ledger is internal-only; revisit user-facing calibration at v1.0.**

## Bottom line

The research is right and unusually well-disciplined; the proposed scope is sound but
detection-shaped. The one structural improvement this review adds: stop hand-writing
availability claims at all. Generate them from the renderer, curate the absences in the
same registry with collision markers, and the entire failure class — including its
future recurrences — becomes impossible rather than merely caught.
