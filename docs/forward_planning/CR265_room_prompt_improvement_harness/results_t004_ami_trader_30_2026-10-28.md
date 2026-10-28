# T004 — `ami-llm` Execution Desk clarification on 30 frozen tickers, 2026-10-28

Evaluation of the isolated Execution Desk thesis/timing prompt on
`qwen3.8-flash-next-abliterated-nvfp4`. Production control and Trader-only,
30 tickers × two repetitions at R4, identical frozen profiles per ticker.

## Decision

**NO-GO. Do not advance this variant to R1–R5 or production.** Trader-only
increased unstable tickers from **10/30 to 12/30** and reduced approvals from
**24/60 to 18/60**. Although several upstream desks became more stable, the
final decision became less stable and less willing.

## Headline

| Metric | Production control | Trader-only |
|---|---:|---:|
| Completed rooms | 60 | 60 |
| APPROVE | 24 | 18 |
| Unstable tickers | **10/30 (33.3%)** | **12/30 (40.0%)** |
| Contract gate | 60/60 | 59/60 original + 2/2 LEVI retry |
| Mean room duration | 12.67 min | 12.37 min |
| Trader geometry repairs | 2 | 4 |
| Envelope repairs | 4 | 3 |

Candidate LEVI-rep2 failed `PM_JSON_UNPARSEABLE`. Its replacement pair passed
both gates and returned APPROVE→PASS, so LEVI remains unstable and the headline
counts are unchanged. The original artifact is preserved.

## Flip locations

1. **Control (10):** APD BA BAC DHR MA PLD SLB SNAP SO WFC.
2. **Trader-only (12):** AAPL DE JPM MA NKE PLD RIOT SNAP TMO V WFC WU.
3. MA, PLD, SNAP and WFC flip in both arms; the candidate introduces eight new
   flip locations and removes six control flip locations.

## Desk-level stability

| Desk | Control unstable /30 | Trader-only unstable /30 |
|---|---:|---:|
| Fundamentals | 11 | 7 |
| Market | 12 | 8 |
| News | 10 | 6 |
| Social | 0 | 1 |
| Bull | 1 | 3 |
| Bear | 0 | 1 |
| Research Manager | 10 | 11 |
| Trader | 7 | 10 |

The candidate materially improved Fundamentals, Market and News, yet Trader and
Research Manager worsened and the final verdict regressed. This is another
example of upstream improvement failing to stabilise the PM's decision.

## Majority changes and market alignment

| Ticker | Control → candidate | Human consensus | Read |
|---|---|---|---|
| AAPL | PASS → APPROVE | Moderate Buy | Aligned bullish |
| APD | APPROVE → PASS | Moderate Buy | More contrarian |
| BA | APPROVE → PASS | Moderate Buy | More contrarian |
| BAC | APPROVE → PASS | Moderate Buy | More contrarian |
| LEVI | APPROVE → PASS | Moderate Buy | More contrarian |
| NKE | PASS → APPROVE | Reduce | More contrarian |
| RIOT | PASS → APPROVE | Moderate Buy | Aligned bullish |
| SLB | APPROVE → PASS | Moderate Buy | More contrarian |
| SO | APPROVE → PASS | Hold | More cautious |
| WU | PASS → APPROVE | Reduce | More contrarian |

The candidate's reduced willingness therefore does not uniformly improve market
alignment. It moves six names to PASS, five of them Moderate Buy, and four names
to APPROVE, two of them Reduce.

## PM-vote finding

All 22 flip pairs across control and candidate involved split PM votes; none was
a clean unanimous-APPROVE versus unanimous-PASS reversal. The final instability
is therefore not only upstream evidence selection. The PM's own vote boundary is
also a material amplifier.

## Data and contract checks

1. Rendered Fundamentals block hash: exactly one per ticker across all 120
   original rooms; no frozen-profile mismatch found.
2. Candidate LEVI replacement: 2/2 gates OK; control: 60/60 gates OK.
3. No NO_VERDICT or scripted-fallback outcome was recorded.
4. Geometry repair burden increased from two to four, a further reason not to
   advance this variant.

## Next

1. Retire the current Execution Desk variant for `ami-llm`; do not run it across
   R1–R5 or combine it with other prompt changes.
2. Do not infer that the desk-level improvements are worthless. They show that
   evidence stability and final-decision stability must be measured separately.
3. Next structural work should target the evidence/decision interface and PM
   vote boundary, not another rewrite of the same Trader prose.
4. Ling lane-only remains eligible for its separate T011 R1–R5 validation; the
   models must not share acceptance assumptions.

## Artifacts

1. Local runs: `docs/tools/room_investigation_V2/out/cr265-frozen30/ami/`.
2. melehost runs: `~/cr265_30_ami/`.
3. LEVI replacement: `trader-levi-retry/` with the original candidate retained.
4. Human calibration: `human_analyst_consensus_2026-10-28.md`.
