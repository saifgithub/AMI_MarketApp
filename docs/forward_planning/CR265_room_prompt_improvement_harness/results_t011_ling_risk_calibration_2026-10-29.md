# T011 — Ling R1–R5 calibration on 30 frozen tickers, 2026-10-29

Full production-control versus lane-only evaluation on
Ling-3.0-flash-Fin-fp4. Thirty tickers × five risk levels × two repetitions ×
two prompt states = 600 rooms. Inputs are frozen per ticker, reviews OFF,
thinking OFF, five PM samples, native temperature.

## Decision

**GO to use lane-only as a candidate in the CR266 structural comparison, not as
a production prompt rollout.** It improves monotonicity and stability, but 22%
of ticker/risk pairs still flip—above the <10% objective. The result supports
per-model prompt routing and further structural work, not a claim that prompt
editing solved reliability.

## Final risk curves

| Risk | Control approvals | Lane approvals | Control flips | Lane flips |
|---|---:|---:|---:|---:|
| R1 | 10/60 = 16.7% | 5/60 = 8.3% | 6 | 5 |
| R2 | 10/60 = 16.7% | 10/60 = 16.7% | 8 | 6 |
| R3 | 17/60 = 28.3% | 20/60 = 33.3% | 7 | 6 |
| R4 | 26/60 = 43.3% | 31/60 = 51.7% | 12 | 5 |
| R5 | 26/60 = 43.3% | 28/60 = 46.7% | 12 | 11 |
| **Total** | **89/300 = 29.7%** | **94/300 = 31.3%** | **45** | **33** |

Lane is monotone at 8.3% → 16.7% → 33.3% → 51.7% → 46.7%. Control is
16.7% → 16.7% → 28.3% → 43.3% → 43.3%. Lane increases willingness slightly
overall and substantially at R4/R5 without a proportional instability cost.

Against the locked target 5/15/30/45/46 per 60, lane is more conservative at
every level except R1 where it matches 5/60. It should not be described as
target-calibrated; it is merely a better-shaped curve than control.

## Stability and uncertainty

1. Control flip rate: **45/150 = 30.0%**, Wilson 95% CI **23.2–37.8%**.
2. Lane flip rate: **33/150 = 22.0%**, Wilson 95% CI **16.1–29.3%**.
3. Relative reduction: **26.7%**. The confidence intervals overlap, so this is a
   meaningful direction of improvement, not proof of a solved mechanism.
4. Nonmonotone tickers across R1–R5: **16 control → 12 lane**.
5. Mean duration: **7.87 min control → 8.44 min lane** (+7.2%).

## Human-consensus alignment

| Human rating | Control approvals | Lane approvals |
|---|---:|---:|
| Buy | 7/10 = 70% | 7/10 = 70% |
| Moderate Buy | 58/150 = 38.7% | 69/150 = 46.0% |
| Hold | 19/80 = 23.8% | 14/80 = 17.5% |
| Reduce | 5/50 = 10.0% | 4/50 = 8.0% |
| Sell | 0/10 = 0% | 0/10 = 0% |

Lane is more aligned with Moderate Buy, more conservative on Hold and Reduce,
and unchanged on Buy/Sell. This is calibration context, not proof of accuracy or
independence: Street consensus is also present in the Room's fact sheet.

Only five tickers changed their overall majority: AAPL, DHR and TMO moved PASS
to APPROVE; T and LEVI moved APPROVE to PASS. Most of the benefit is therefore
within-risk stability and curve shape rather than wholesale ticker reversals.

## Contract and contamination record

1. All 600 original rooms completed. Sixteen failed contract checks: six control
   and ten lane rooms, mostly PM JSON failures plus stance/truncation issues.
2. All 32 replacement rooms passed their gates, including the second DHR pair.
   Original failed artifacts are preserved; analysis substitutes only those
   exact failed arms with their validated replacements.
3. Rendered Fundamentals block hash: exactly one per ticker across all original
   600 rooms; no frozen-profile mismatch found.
4. The wrapper's `exit: numeric argument required` was a shell error, not an
   experiment failure. It did not require rerunning the completed rooms.
5. Geometry repairs: control 46, lane 35 plus one envelope repair. The candidate
   did not increase the repair burden.

## Interpretation

1. **Best measured prompt-side result in this programme:** monotone curve,
   fewer flips, fewer nonmonotone tickers, almost unchanged approval count.
2. **Not general stability:** 22% flips and PM vote variance remain. This is why
   the next step is typed evidence and a computed decision interface, not more
   self-congratulatory prompt tuning.
3. **Model-local:** no inference is permitted to `ami-llm`, where lane cleanup
   previously degraded stability. Per-model prompt routing is the only possible
   future for this candidate.
4. **Not independent correctness:** a more Street-aligned curve can be wrong in
   either direction. Outcome and evidence-quality evaluation remain separate.

## Next

1. Use lane-only as the candidate prompt state in CR266's evidence-gate pilot
   on Ling. Compare structured decision versus full transcript on the same
   frozen profiles.
2. Do not enable lane-only globally and do not call the <10% goal achieved.
3. After structural acceptance on Ling, request a narrow Sonnet confirmation.
   Sonnet remains confirmation-only, not an iteration provider.
4. Complete `ami-llm` production R1–R5 calibration separately; no candidate from
   T004 advances there.

## Artifacts

1. Local runs: `docs/tools/room_investigation_V2/out/cr265-t011/ling/`.
2. melehost runs and replacement logs: `~/cr265_t011_ling/`.
3. Human consensus: `human_analyst_consensus_2026-10-28.md`.
4. Previous R4 result: `results_t003_ling_lane_30_2026-10-28.md`.
