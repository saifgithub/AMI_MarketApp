# T003 — Ling lane cleanup on 30 frozen tickers, 2026-10-28

First multi-ticker evaluation of the isolated four-analyst prompt cleanup on
Ling-3.0-flash-Fin-fp4. Production control and lane-only candidate, 30 tickers ×
two repetitions at R4, identical frozen profiles per ticker.

## Decision

**GO for the next per-model validation stage on Ling; not yet a production
fold-in.** Lane cleanup reduced unstable tickers from **13/30 to 5/30** while
holding approvals at **33/60 for both arms**. All 60 candidate rooms passed the
contract gate. This earns an R1–R5 calibration trial and later Sonnet
confirmation, but does not establish decision accuracy or transfer to `ami-llm`.

## Headline

| Metric | Production control | Lane-only |
|---|---:|---:|
| Completed rooms | 60 | 60 |
| APPROVE including legacy REJECT as PASS-equivalent | 33 | 33 |
| Unstable tickers (two reps disagree) | **13/30 (43.3%)** | **5/30 (16.7%)** |
| Adjacent-pair flip reduction | — | **61.5% relative** |
| Contract gate | 59/60 original + 2/2 TMO retry | **60/60** |
| Mean room duration | 7.75 min | 7.42 min |
| Trader geometry repairs | 7 including TMO retry | 7 |

Control's original TMO-rep2 failed `MISSING_STANCE` on Research Manager. The
original two-PASS pair was replaced for analysis by a fresh clean pair on the
identical frozen TMO profile. That pair itself returned PASS→APPROVE, so TMO is
counted unstable. The original artifact is preserved; the clean replacement is
not hidden.

## Tickers that flipped

1. **Control (13):** BGS CAG DE DHR JPM PYPL RIOT SNAP SO T TMO WFC WU.
2. **Lane-only (5):** APD DHR NKE PLD SEDG.
3. Only DHR flips in both arms; the other nine control flip locations disappear
   under lane cleanup, while APD/NKE/PLD/SEDG become newly unstable.

## Desk-level stability

| Desk | Control unstable /30 | Lane-only unstable /30 |
|---|---:|---:|
| Fundamentals | 7 | 5 |
| Market | 4 | 4 |
| News | 5 | 7 |
| Social | 1 | 1 |
| Bull | 0 | 3 |
| Bear | 0 | 0 |
| Research Manager | 10 | 15 |
| Trader | 18 | 13 |

The final verdict improved despite more variation in Research Manager and News.
This confirms that per-desk agreement and final-verdict agreement are different
metrics. The lane change is not a full-pipeline stabiliser.

## Verdict changes, not just stability changes

Lane-only changed the two-rep majority on nine tickers:

| Ticker | Control → lane | Human consensus | Read |
|---|---|---|---|
| CAG | PASS → APPROVE | Reduce | More contrarian |
| JPM | PASS → APPROVE | Moderate Buy | Aligned bullish |
| PLD | APPROVE → PASS | Moderate Buy | More contrarian |
| PYPL | PASS → APPROVE | Hold | More permissive |
| RIVN | APPROVE → PASS | Hold | More cautious |
| SEDG | APPROVE → PASS | Reduce | Aligned cautious |
| SO | PASS → APPROVE | Hold | More permissive |
| T | PASS → APPROVE | Moderate Buy | Aligned bullish |
| TMO | PASS → APPROVE | Moderate Buy | Aligned bullish |
| WFC | PASS → APPROVE | Moderate Buy | Aligned bullish |

These changes are not evidence of correctness. They are the cases to inspect in
later R1–R5 calibration and independent evidence review.

## Human-consensus cautions

1. Candidate now APPROVEs CAG (Reduce) and passes PLD (Moderate Buy): direct
   disagreements worth reviewing, not automatic errors.
2. RIVN (Hold) and SEDG (Reduce) moving to PASS is consistent with the cautious
   human view.
3. JPM/T/TMO/WFC moving to APPROVE is consistent with Moderate Buy.
4. Human ratings are a dated calibration reference, partly already present in
   the Room's Street-consensus fact-sheet fields, not independent truth.

## Contract and quality checks

1. Candidate: 60/60 `scoring.gate_report` passes.
2. Control: 59/60 original passes; TMO replacement pair 2/2 passes.
3. Rendered Fundamentals block hash: exactly one per ticker across all 120
   original control/candidate rooms; no frozen-profile mismatch found.
4. Trader geometry repair burden is unchanged at seven per arm.
5. No NO_VERDICT or scripted-fallback outcome was recorded.

## Next

1. **T011 on Ling:** production control and lane-only across R1–R5 using the same
   30 frozen profiles. Report approval rates, flips, per-ticker monotonicity,
   PM vote margins and alignment with the human snapshot.
2. **Do not deploy yet.** Confirm across risk levels, then use Sonnet once for a
   frozen AAPL/multi-ticker confirmation if the candidate still earns it.
3. For `ami-llm`, do not infer the same result. T004 is a different isolated
   intervention on a different model and must be judged separately.

## Artifacts

1. Local runs: `docs/tools/room_investigation_V2/out/cr265-frozen30/ling/`.
2. melehost runs: `~/cr265_30_ling/`.
3. TMO replacement: `baseline-tmo-retry/` with the original baseline retained.
4. Human calibration: `human_analyst_consensus_2026-10-28.md`.
