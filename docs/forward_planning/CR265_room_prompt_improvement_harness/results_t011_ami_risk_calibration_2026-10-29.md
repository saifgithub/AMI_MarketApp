# T011 — `ami-llm` production R1–R5 calibration, 2026-10-29

Production prompts only: 30 frozen tickers × five risk levels × two repetitions
= 300 canonical rooms. Reviews OFF, thinking OFF, five PM samples, native
temperature. No candidate advanced from T004.

## Decision

**Use this as the `ami-llm` production control for CR266, not as a stability
success.** The curve is monotone but too conservative relative to policy, flips
remain above objective, and every flip involves a split PM vote. This supports
the typed-evidence/computed-decision work rather than another global prompt
rollout.

## Final risk curve

| Risk | Approvals | Target / 60 | Difference |
|---|---:|---:|---:|
| R1 | 0/60 = 0.0% | 5 | −5 |
| R2 | 1/60 = 1.7% | 15 | −14 |
| R3 | 11/60 = 18.3% | 30 | −19 |
| R4 | 19/60 = 31.7% | 45 | −26 |
| R5 | 34/60 = 56.7% | 46 | −12 |
| **Total** | **65/300 = 21.7%** | 161 | −96 |

The production control is more conservative than the locked policy curve at
every level. It is not target-calibrated, despite the monotone shape.

## Stability and uncertainty

1. **27/150 pairs flipped = 18.0%**, Wilson 95% CI **12.7–24.9%**. The <10%
   objective is not met.
2. **All 27 flip pairs involved split PM votes; zero had unanimous PMs in
   opposite directions.** The PM vote boundary is the consistent amplifier.
3. Five tickers are nonmonotone across R1–R5:

| Ticker | R1 | R2 | R3 | R4 | R5 |
|---|---:|---:|---:|---:|---:|
| BAC | 0 | 0 | 1 | 0 | 1 |
| DHR | 0 | 0 | 2 | 2 | 1 |
| V | 0 | 1 | 1 | 0 | 2 |
| WFC | 0 | 0 | 2 | 0 | 2 |
| WU | 0 | 0 | 0 | 1 | 0 |

4. Mean room duration: **9.12 minutes**.

## Human-consensus alignment

| Human rating | Approvals | Approval rate | Flips |
|---|---:|---:|---:|
| Buy | 4/10 | 40.0% | 2 |
| Moderate Buy | 43/150 | 28.7% | 11 |
| Hold | 14/80 | 17.5% | 10 |
| Reduce | 4/50 | 8.0% | 4 |
| Sell | 0/10 | 0.0% | 0 |

AMI is more conservative than the Street across every rating category. It does
not simply mirror consensus. The three low-coverage names—BGS (3 analysts),
XRX (4) and SPCE (7)—received zero approvals.

This is calibration context, not evidence of correctness or independence:
consensus is partly present in the Room fact sheet, ratings and target upside
are different measures, and the outcome ledger currently has no scored rows.

## Holdout review

The seven predeclared exclusion names received **8 approvals**, all at R4/R5:

1. BA: 2 (both R5)
2. FCEL: 1 (R5)
3. RIOT: 1 (R5)
4. RIVN: 2 (one R4, one R5)
5. SNAP: 2 (one R4, one R5)
6. APD and SPCE: 0

Current production therefore does **not** satisfy CR266's zero-holdout-approval
acceptance condition. That condition applies to the new structural gate, not a
claim that the existing control already had it.

## Contract and contamination record

1. All 300 original rooms completed; **294 passed** their original contract
   gates. Six failed: APD R1, BA R1, BGS R2, LEVI R4, LEVI R5 and SPCE R5.
2. XRX R3 rep1 also carried a scripted Bear fallback and was quarantined.
3. Each of those seven ticker/risk pairs was replaced as a pair: **14
   replacement rooms, 14/14 gates passed**. Original artifacts are preserved.
4. The canonical 300-room dataset, with only those exact arms substituted,
   passes **300/300 contract gates**.
5. Inputs use the established frozen profiles and matched feature flags. No
   Sonnet runs or production changes were made.

## Interpretation and next step

1. Production `ami-llm` is more stable than the rejected T004 variant but still
   far from the reliability objective.
2. The result is consistent with CR265's vote audit: natural-language evidence
   reaches a split PM, and the vote threshold amplifies small narration changes
   into binary flips.
3. Continue with the cards-ON/gate-OFF `ami-llm` pilot, then fit provider+model
   thresholds only from complete registry-backed evidence and run fresh V2
   acceptance. Do not enable the gate from this production baseline alone.
4. Ling remains a separate model result; no metric transfers between models.

## Artifacts

1. Canonical runs and gates: `docs/tools/room_investigation_V2/out/cr265-t011/ami/canonical_runs.jsonl` and `canonical_contract_gates.json`.
2. Numeric summary: `docs/tools/room_investigation_V2/out/cr265-t011/ami/analysis_summary.json`.
3. Original and replacement artifacts: `docs/tools/room_investigation_V2/out/cr265-t011/ami/baseline/` and `retry-*/`.
4. Human snapshot: `human_analyst_consensus_2026-10-28.md`.
5. Ling comparison: `results_t011_ling_risk_calibration_2026-10-29.md`.
