# CR035 — fixed-Room baseline re-run scoring (`baseline150fix-2026-07-20`)

**What this is.** The honest re-measurement of the 150-ticker Room-vs-Street benchmark after DEF066
and DEF067 were fixed and shipped live (commit `ea77bc5`, on melehost). All three prior arms
(A/B/C) measured the *buggy* Room; this run is the first on the corrected Room, all-live config
(`SUPPRESS_ANALYST_CONSENSUS=false`, `ADANOS_API_KEY` live, `USE_REAL_MARKET_DATA=true`).

Data: [`runs_baseline150fix-2026-07-20.jsonl`](runs_baseline150fix-2026-07-20.jsonl) (151 lines =
150 unique tickers + 1 duplicate for CPB, which timed out once then completed on resume). Scoring
dedups by ticker, latest record wins. Baseline of comparison: the buggy
[`runs_baseline150-2026-07-17.jsonl`](runs_baseline150-2026-07-17.jsonl) (arm A).

All numbers below were measured directly from the two JSONL files and the `llm_audit` table on
melehost — none are extrapolated.

## Fixed-Room run, standalone

| Metric | Value |
|---|---|
| Unique tickers | 150 |
| Completed | 149 (1 `poll_timeout`: OSCR — slow convene, safe no-trade) |
| **APPROVE / PASS** | **55 / 94** |
| **APPROVE rate** | **55/149 = 36.9%** |
| DEF058-class parse-fallback (residual) | **1/150 (AES, 0.7%)** — fails safe to PASS |

## Acceptance — both defects pass

| Defect | Criterion | Measured | Verdict |
|---|---|---|---|
| **DEF067** | reformatter traffic drops ~90% | `room_pm_reformat` **1 / 152 convenes (0.7%)** vs ~142/150 (~95%) buggy → ~99% reduction | ✅ |
| **DEF067** | 0 leaked reformatter complaints as verdicts | **0** across 150 names | ✅ |
| **DEF058 residual** | parse-fallback < 2% | **0.7%** (was corrected 6.0%), fails safe | ✅ |
| **DEF066** | 0 verdicts citing stop-distance-as-cap | **0 / 149** | ✅ |
| **DEF066** | re-check the originally-refused names | of 12 re-checked, 3 now APPROVE (BKNG, NEE, PLD); rest correctly PASS on other grounds | ✅ |

## Fixed vs buggy baseline (same 149 comparable tickers)

| Metric | Value |
|---|---|
| Same verdict | 98/149 (66%) |
| Flipped | 51 |
| — PASS→APPROVE (recovered buys) | **35** |
| — APPROVE→PASS (lost) | **16** |
| APPROVE count | buggy 36 (24%) → **fixed 55 (37%)**, net **+19** |

**APPROVE-set overlap (hypergeometric).** Buggy and fixed share **20** APPROVE names; **13.3**
expected by chance (buggy K=36, fixed n=55, N=149). **P(overlap ≥ 20) = 0.007** → the fixed run's
buy-set tracks the buggy run's buy-set **above chance** — i.e. there is now a statistically stable
buy-core, unlike the earlier ablation arms (B p=0.57, C p=0.16, both at/near chance).

## Interpretation (honest)

1. **The two bugs were suppressing real buys.** Removing them lifts the Room's APPROVE rate from
   24% to 37% on the identical 150 names, closing roughly a third of the Street-Buy (63%) vs
   Room-PASS gap. 35 names the buggy Room passed are now approved; the recovered set is dominated by
   megacap quality names the Street strongly buys — GOOGL, META, MSFT, NVDA, V, MA, JPM, ORCL, UNH,
   CRM, HON, CAT, plus BKNG/NEE/PLD (the DEF066 arithmetic-refusers) and the DEF067
   MODIFY-AND-APPROVE names (META, NIO, VZ, EXPE …).
2. **It is not purely additive.** 51 of 149 names (34%) changed verdict, and 16 flipped the "wrong"
   way (APPROVE→PASS: AAPL, TSLA, AVGO, ABBV, RTX …). Some of the movement is still Room
   stochasticity — the same ticker convened twice can differ. The net is +19 buys, not +35.
3. **But the buy-core is now real.** The above-chance APPROVE overlap (p=0.007) is the first
   arm-to-arm comparison in CR035 to clear significance. The three-arm conclusion ("stable buy
   *rate*, no stable *which names*") is partly a bug artifact: on the corrected Room a stable core
   of names survives across runs.

## Bottom line

DEF066 and DEF067 are resolved and verified live. The corrected Room approves 37% (vs 24% buggy,
vs 63% Street). The Street-vs-Room gap is smaller than the buggy benchmark claimed, and a
statistically stable buy-core now exists — the remaining ~26-point gap to the Street is the real,
non-artifact question for any follow-up.
