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
| 1 | Structured evidence and computed constraints | CR266 implements the normalized 20-card record, computed action/size and fail-closed controls. Gate remains OFF pending real-model acceptance. | **Implemented; integration and V2 acceptance in progress.** |
| 2 | Separate educational transcript from binding decision | Typed evidence now binds action and size while the PM narrates the decision. Review/re-run paths must enforce the same constraints. | **Implemented; bypass regression tests in progress.** |
| 3 | Freeze and hash inputs | `freeze_lab` works for 30 profiles; all valid earlier rooms shared the expected rendered hash. | **Implemented and working.** |
| 4 | True production controls and feature-flag parity | Earlier Sonnet flag mismatch was caught and rerun. T003/T004/T011 use reviews OFF and identical profiles. | **Working, but must remain an acceptance check.** |
| 5 | Quarantine incomplete rooms | TMO and LEVI replacements ran and original artifacts remain preserved. | **Working as experiment hygiene.** |
| 6 | Show uncertainty and what changed | CR266 mobile models, contested card and next-convene card are implemented; old verdicts fabricate no state. | **Implemented; final backend/mobile contract verification in progress.** |
| 7 | Independent quality labels | MarketBeat consensus is captured for all 30. The real outcome report covers 6,743 banked rows but has zero scored outcomes. | **Partial; no outcome-quality or consensus-alignment claim is possible yet.** |
| 8 | T=0 as hygiene | Ling T=0 previously reduced but did not eliminate flips; no new T=0 arm in the 900-room run. | **Not a stability fix; optional later ablation.** |
| 9 | Reduce decision-relevant generative stages | CR266 removes generative control over final action and size; it does not remove the educational desk stages or PM narration. | **Partially implemented; full-stage reduction was not assumed necessary without new evidence.** |
| 10 | Canonical experiment registry | Ledger, hashes, run IDs and contamination replacements are documented; CR266 adds per-model pilot and acceptance records. | **Implemented as ongoing experiment discipline.** |

## Corrected experiment sequence

1. Complete CR266 integration and close any path that can bypass typed action
   or size constraints. Preserve T011's negative findings; lane-only is not a
   general prompt rollout.
2. Run the 30-ticker, two-repetition R4 cards-ON/gate-OFF pilot on `ami-llm` and
   Ling. Require normalized evidence ICC ≥0.85 and complete machine channels.
3. Fit provider-plus-model thresholds from real registry-backed card evidence,
   then run fresh 30×5 acceptance with final verdict, flip, discrimination and
   holdout gates. No fit or pilot result is a production claim by itself.
4. Keep failed configurations OFF. Use Sonnet only to confirm a configuration
   that has earned it through the preceding steps.
5. Only if structural work still leaves a measured prompt problem, run the clean
   CFA-only, Bull-only, Bear-only, RM-only, Risk-trio and cards-first ablations
   separately. Those prompt ideas are not falsely marked as covered by CR266.
