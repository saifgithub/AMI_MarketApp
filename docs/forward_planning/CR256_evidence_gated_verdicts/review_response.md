# CR256 — Review response (track K)

**Responds to:** `Opus_review/CR256_review_opus.md` (reviewed spec at 48d46ea0)
**Date:** 2026-10-13 · **Disposition:** accept 14 items, accept-with-modification 3,
reject 0. The review is accepted as a whole; three items are shaped before adoption.

## Accepted in full

| Item | Disposition | Pros | Cons / cost of accepting |
|---|---|---|---|
| B1 — AC4 circular; needs independent label | ACCEPT | Makes the acceptance test mean something; kills tautology | Creates dependency on CR257's decision label + a hand-audited stratified sample (~20 rooms, jev_review protocol). Acceptance cannot complete before CR257 lands. |
| B2 — target/holdout contradiction; holdouts as code predicates with absent-datum branch; published holdout list pre-fit | ACCEPT | AC1/AC3 become jointly feasible; holdouts falsifiable in advance | Requires Saiful decision: R5 re-anchored to investable universe (or per-level tolerance net of holdouts). Reopens a policy he already locked. |
| B3 — determinism bullets wrong (seeded=False IS fixed-order; temperature unplumbed) | ACCEPT | Removes two unimplementable directives; my spec error, corrected | Temperature pinning deferred → one stability lever not in v1 (but it was never measured to help; direct_call replay first). |
| B4 — sign cards by `direction`, never desk; stance_only is the baseline to beat | ACCEPT (crown jewel) | stance_signed rep-to-rep r=+0.84 vs desk-signed −0.11…+0.25; explains WHY the single-metric bar died (no reliable sign, ties secondary) | Proxies are STANCE-envelope+Jev, not real cards — card pilot still mandatory (review's own §7.1). |
| M1 — census overclaim; PM unanimous on 15/26–24/40 flip-pairs | ACCEPT | Correct target: card-level direction/grade test-retest becomes the Layer-1 acceptance metric | Reframe cost: flips are debate-direction changes, so Layer-1 (cards) is the right layer but must prove direction stability, not just coverage. |
| M2 — lane-specific checklist items; drop/normalize factor_coverage | ACCEPT | catalyst/technical/mandate-fit enter the census where decisions actually happen; kills the ticker-constant penalty | Slightly larger card schema; coverage normalization needs the fact-sheet field registry (see M3). |
| M3 — data_present/objection-resolution/catalyst computed in code; self-grades tie-break only | ACCEPT | Closes the gate-gaming surface; aligns with decision_record_spec's "computed or explicitly LLM-reported, never both silently" | Fact-sheet field registry + resolution-matching logic are real build items; objection-resolution rule (opposite-direction card, grade ≥) needs care. |
| M4 — catalyst_proximity out of evidence_score | ACCEPT | Keeps evidence quality unmixed with timing preference; catalyst becomes an explicit policy rule | One fewer fitted dimension (good); a separate catalyst policy rule must still be written. |
| M5 — fit objective (test-retest r + independent-label agreement), ticker-held-out CV, monotone T ladder, fresh tickers at acceptance | ACCEPT | Curve cannot identify weights (any weight vector hits the targets) — this is the correct objective | Held-out ticker set = more rooms at acceptance (necessary spend). |
| M6 — gate failure semantics (uncomputable → PASS; gate-before-PM; disallowed action → overridden_from_llm) | ACCEPT | DEF059-consistent; reuses existing fail-safe and schema fields | None material. |
| M7 — debator turns missing from llm_audit/Jev as explicit prerequisite; reconcile with CR257 question freeze | ACCEPT | Objections (a gate input) currently unauditable; root cause upstream of the scorer | DB investigation into what llm_audit records for debator turns; CR257 coordination needed. |
| M8 — AC2 precision; add test-retest r ≥ 0.85 leading indicator + CIs | ACCEPT | AC2 at 10% with n=150 pairs is borderline (CI ±5pt); a pilotable leading indicator de-risks | One more metric to instrument. |
| §4 corrections (all seven) | ACCEPT | "Failure mode A stated too strongly" is the important one: the PM DOES follow the debate's direction (stance_only r=+0.55…+0.78) — the no-discrimination finding is the *metric's* property. This strengthens the CR: the gate will mostly agree with the PM and fix stability/calibration/monotonicity, not fight the debate. Also: lift is +10pts at R3/R4 (not 0) — failure concentrated at tails; drop ATR from sub-cap v1; wording fixes. | Corrects claims in my own analysis docs (analysis_r6 quotes the point value; will annotate, not rewrite history). |
| §5 answers (all four) | ACCEPT | Self-grades tie-break only; structural number verification (NOT Jev figures_consistent — 0.46–0.65 on clean turns); monotone ladder fit + bootstrap T(1) + reps spent on held-out tickers; continuous monotone sub-cap map from T upward | figures_consistent's weakness noted for the Jev review session follow-up. |
| §6 revised sequence | ACCEPT | Step 0 (proxy-gate simulation = the retroactive feasibility, no rooms burned) is exactly right; card pilot before any matrix is the correct gate | Sequencing adds a review/decision checkpoint (Saiful: R5 anchor + holdouts + vote-bar policy) before build. |

## Accepted with modification

| Item | Modification | Why |
|---|---|---|
| B5 — existing CR228 vote bar (4/4/3/2/2 of 5) | **Freeze-and-record during measurement; retirement decided at production fold-in, not before.** The review offered retire-or-freeze; I choose freeze. | On ami the vote bar binds (R4: bar=1 would give 24 approvals vs 10 actual) — retiring it would change ami's curve for reasons independent of the gate, confounding the model comparison. Two changes at once also breaks attribution on dsv4. Decision record gains `samples` + vote outcome (review's own fix bullet). |
| B2 feasibility arithmetic | Note: with AC1's ±8 tolerance and exactly 7 SBC-barred tickers, R5 = 53 max approvals sits inside the tolerance band (52–68) — borderline feasible, not strictly infeasible. **Adopt the re-anchor anyway**: a top level that means "approve every non-barred name" is a degenerate policy. | Precision; the review's direction stands on the policy merits. |
| §6.7 / CR257 metric note | Adopt, and extend: CR257's evaluation should use a direction-aware reference *and* CR256's ticker-held-out protocol, so both CRs share one evaluation harness. | Avoids two inconsistent verdicts on the same arms. |

## Rejected

None. The review's own caveats (§7 — proxies are not cards; simulated flips are
in-sample; gate re-expresses the debate so *correctness* remains unmeasured
until B1's independent label exists) are adopted as standing limitations in the
spec.

## Decisions required from Saiful before build

1. **R5 anchor:** re-anchor to investable universe (≈23 names → R5 ≈ 46/60) or
   keep 60/60 with holdout-adjusted tolerance? (B2)
2. **Holdout predicates:** approve the explicit code predicates + the published
   7-name list (APD, BA, FCEL, RIOT, RIVN, SNAP, SPCE) with its absent-datum
   branch. (B2)
3. **Vote-bar policy:** confirm freeze-and-record for the measurement phase. (B5)
4. **CR257 coordination:** shared direction-aware evaluation harness. (mod above)
