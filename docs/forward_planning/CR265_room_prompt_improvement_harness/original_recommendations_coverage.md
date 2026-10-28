# Original stability-review recommendations — test coverage register

Purpose: prevent the 900-room lane experiment being mistaken for validation of
the whole original stability review. The 900 rooms test only lane-specific
briefs and the removal of the shared CFA block from three analyst desks, within
a same-model production control.

## Original prompt recommendations

| # | Recommendation | Evidence so far | Status / next action |
|---:|---|---|---|
| 1 | Lane-specific reasoning briefs | T003/T004 and current T011 Ling lane arm. R4 Ling improved, but current cross-risk flips increased. | **Partially tested; no general GO.** Complete T011 before deciding. |
| 2 | Remove generic CFA from non-lane roles | Same lane arm. Current affected-desk instability worsened (Fundamentals 7→11, Market 5→11, News 6→9; Social 3→2). | **Confounded, not CFA-only.** Run a clean CFA-only R4 ablation with all other text unchanged. |
| 3 | Fixed evidence census | CR256 filing enforcement reached ICC 0.868 on dsv4; not tested as a binding PM decision path in this programme. | **Not tested as proposed.** Implement lane-specific typed census and test evidence agreement before verdicts. |
| 4 | Cards-first vs stance-first | Only discussed. | **Untested.** Small A/B with identical cards and constraints. |
| 5 | Bounded, falsifiable Bull/Bear analysis | Included only in the rejected combined suite; no isolated arm. | **Not isolated.** Separate Bull-only and Bear-only R4 arms. |
| 6 | Research Manager as adjudicator | Included only in the rejected combined suite; RM instability increased in T003 and T004. | **Not isolated.** RM-only R4 arm. |
| 7 | Thesis direction vs execution timing | T002 and T004. T004 `ami-llm`: approvals 24→18/60, unstable 10→12/30. | **Tested, NO-GO.** Do not advance current variant. |
| 8 | Risk Officers as option generators | Included only in the rejected combined suite; no isolated three-role arm. | **Not isolated.** Test the risk trio as one arm, not three simultaneous new ideas. |
| 9 | One PM policy and clearer definitions | T002: agreement 80/20/60% on ami/Ling/Sonnet; no model improved. | **Tested, NO-GO.** Retire current wording; address vote boundary structurally. |
| 10 | AR/MS localisation recipe | RES009 instruction-last succeeded on 20 PM calls; not part of the current English stability programme. | **Previously validated narrowly, not current priority.** Broader language review later. |

## Original application recommendations

| # | Recommendation | Evidence so far | Status |
|---:|---|---|---|
| 1 | Structured evidence and computed constraints | CR256 channel ICC 0.868 on dsv4. No per-model production verdict gate yet. | **Main unfinished structural item.** |
| 2 | Separate educational transcript from binding decision | Natural-language transcript still drives the PM. | **Untested architecturally.** |
| 3 | Freeze and hash inputs | `freeze_lab` now works for 30 profiles; all valid earlier rooms shared the expected rendered hash. | **Implemented and working.** |
| 4 | True production controls and feature-flag parity | Earlier Sonnet flag mismatch was caught and rerun. T003/T004/T011 use reviews OFF and identical profiles. | **Working, but must remain an acceptance check.** |
| 5 | Quarantine incomplete rooms | TMO and LEVI replacements run and preserved with original artifacts. | **Working as experiment hygiene.** |
| 6 | Show uncertainty and what changed | PM votes and flips are analysed, but no user-facing product change. | **Not implemented.** |
| 7 | Independent quality labels | MarketBeat human consensus captured for all 30 and joined preliminarily by rating. | **Partial; not broker-independent or outcome truth.** |
| 8 | T=0 as hygiene | Ling T=0 previously reduced but did not eliminate flips; no new T=0 arm in this 900-room run. | **Not a stability fix; optional later ablation.** |
| 9 | Reduce decision-relevant generative stages | Not tested; current full Room remains. | **Untested.** |
| 10 | Canonical experiment registry | Ledger, hashes, run IDs and contamination replacements now documented; older duplicate/canonical-R3 issues remain historical. | **Improved, ongoing discipline.** |

## Corrected experiment sequence

1. Complete T011 and preserve its negative findings; do not call the lane arm a
   general success merely because its curve is more monotone.
2. Run the clean CFA-only R4 ablation: original prompts versus deletion of only
   the CFA block, no other edits.
3. Run isolated Bull-only, Bear-only, RM-only and Risk-trio arms, each with a
   same-model control and no bundled changes.
4. Test cards-first versus stance-first, then the lane-specific typed census as
   the PM's binding evidence input.
5. Address the PM vote boundary and test typed decision records separately from
   the educational transcript.
6. Only then consider Sonnet confirmation or any production fold-in.
