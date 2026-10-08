# CR251 market reference — Street consensus refresh (2026-10-08)

**Purpose.** Refresh the analyst-consensus reference for the CR228 30-ticker benchmark
universe so AMI matrix verdicts can be compared against where the Street stands now.
The previous reference was `CR035 results/consensus.jsonl` (asof 2026-07-17); the
universe was stratified by those buckets, so bucket drift matters for how we read
sample coverage.

**Method.** Same schema as CR035 (`ticker/source/asof/bucket/counts/mean_score/
mean_target/n_analysts`), source Yahoo Finance via yfinance (recommendations
period `0m` + analyst price targets), spot price added for upside computation.
`mean_score` is the count-weighted 1–5 rating mean (1=strong buy … 5=strong sell);
buckets: ≤1.5 strong_buy, <2.5 buy, <3.5 hold, <4.5 sell, else strong_sell.
The 2026-07 stockanalysis secondary source is dropped (their API shape is gone,
404; pages are JS-rendered). Data: `results/consensus_refresh.jsonl`
(30 rows, all fetched 2026-10-08 UTC). Fetch/compare scripts in `tools/`.

## Then → now drift (2026-07-17 → 2026-10-08, ~12 weeks)

22/30 buckets unchanged. Direction: broad Street cooling.

| Ticker | 2026-07 | 2026-10-08 | Note |
|---|---|---|---|
| AAPL | buy (2.04) | hold (2.50) | target above→below spot |
| NKE | buy (2.49) | hold (2.98) | target cut 51.30→38.15 |
| DHR | strong_buy | buy | |
| MA | strong_buy | buy | |
| V | strong_buy | buy | |
| RIOT | strong_buy | buy | |
| BGS | sell | hold | sell stratum disappears |
| WU | sell | hold | sell stratum disappears |

Universe shift: strong_buy 4→0, sell 2→0, buy 14→16, hold 10→14.
Consequence: the CR228 stratification no longer describes the current tape — there
are no Street-sell names left in the sample, so the red-line check is vacuous this
round by construction (AMI approved BGS/WU 0/10 anyway).

## AMI matrix vs Street now (frozen analysis_r2.md, production baseline)

AMI = APPROVE count of 2 reps per risk level. Street = yahoo bucket/score now.

| Ticker | AMI R1/R2/R3/R4/R5 | AMI Jev | Street now | Target | Spot | Upside | Street 2026-07 |
|---|---|---|---|---|---|---|---|
| AAPL | 0/0/1/2/2 | 0.69 | hold (2.50) | 328.09 | 336.67 | -3% | buy (2.04) |
| APD | 0/0/1/0/0 | 0.77 | buy (2.14) | 342.53 | 278.12 | +23% | buy (1.86) |
| BA | 0/0/0/0/0 | 0.72 | buy (1.93) | 271.77 | 188.32 | +44% | buy (1.68) |
| BAC | 0/0/0/1/1 | 0.72 | buy (1.88) | 67.33 | 53.52 | +26% | buy (1.54) |
| BGS | 0/0/0/0/0 | 0.77 | hold (3.20) | 4.30 | 2.53 | +70% | sell (3.67) |
| CAG | 0/0/0/0/2 | 0.77 | hold (3.24) | 14.32 | 13.25 | +8% | hold (3.29) |
| DE | 0/0/0/1/1 | 0.76 | buy (2.24) | 691.83 | 656.87 | +5% | buy (2.13) |
| DHR | 0/0/0/1/1 | 0.81 | buy (1.92) | 239.05 | 218.49 | +9% | strong_buy |
| FCEL | 0/0/0/0/1 | 0.82 | hold (2.73) | 21.10 | 18.37 | +15% | hold (2.63) |
| JPM | 0/1/1/2/1 | 0.65 | buy (2.29) | 372.81 | 329.58 | +13% | buy (2.17) |
| LEVI | 0/1/2/1/0 | 0.86 | buy (1.87) | 27.53 | 19.51 | +41% | buy (1.60) |
| MA | 0/1/2/2/2 | 0.64 | buy (1.88) | 666.71 | 570.06 | +17% | strong_buy |
| MO | 0/0/1/1/2 | 0.68 | hold (2.93) | 70.00 | 69.38 | +1% | hold (2.62) |
| NKE | 0/0/1/1/0 | 0.68 | hold (2.98) | 38.15 | 34.36 | +11% | buy (2.49) |
| PLD | 0/0/0/2/1 | 0.73 | buy (2.24) | 158.23 | 127.30 | +24% | buy (2.00) |
| PYPL | 0/0/0/2/1 | 0.81 | hold (2.83) | 56.92 | 54.95 | +4% | hold (2.88) |
| RIOT | 0/0/0/0/0 | 0.79 | buy (1.73) | 31.54 | 18.54 | +70% | strong_buy |
| RIVN | 0/0/0/0/0 | 0.74 | hold (2.64) | 19.00 | 14.34 | +32% | hold (2.58) |
| SEDG | 0/0/0/1/0 | 0.80 | hold (3.12) | 38.16 | 33.16 | +15% | hold (3.19) |
| SLB | 0/0/0/1/1 | 0.77 | buy (2.00) | 62.38 | 47.96 | +30% | buy (1.60) |
| SNAP | 0/0/0/1/2 | 0.74 | hold (2.79) | 7.40 | 5.81 | +27% | hold (2.70) |
| SO | 0/0/0/0/2 | 0.75 | hold (2.74) | 98.13 | 85.44 | +15% | hold (2.58) |
| SPCE | 0/0/0/0/0 | 0.74 | hold (2.86) | 3.56 | 3.01 | +18% | hold (2.71) |
| T | 0/0/0/2/2 | 0.78 | buy (2.27) | 28.77 | 24.47 | +18% | buy (2.08) |
| TMO | 0/0/0/2/1 | 0.75 | buy (2.07) | 665.16 | 662.06 | +0% | buy (1.61) |
| V | 0/0/0/2/2 | 0.73 | buy (1.93) | 419.36 | 372.10 | +13% | strong_buy |
| WFC | 0/0/0/0/1 | 0.75 | buy (2.11) | 99.02 | 80.26 | +23% | buy (1.92) |
| WU | 0/0/0/0/0 | 0.77 | hold (3.39) | 6.80 | 6.11 | +11% | sell (3.61) |
| XPEV | 0/0/0/0/0 | 0.76 | buy (2.16) | 18.41 | 9.58 | +92% | buy (1.73) |
| XRX | 0/0/0/1/0 | 0.76 | hold (3.25) | 3.82 | 3.01 | +27% | hold (3.33) |

## Findings

1. **Agreement at R5 (top of the appetite axis):** AMI approves 11/16 Street-buy
   names (69%) — BAC, DE, DHR, JPM, MA, PLD, SLB, T, TMO, V, WFC — and 7/14
   Street-hold names (50%) — AAPL, CAG, FCEL, MO, PYPL, SNAP, SO.
   The Room is Street-tilted, consistent with the frozen baseline's switch shape
   (gate opens at R4, content skews to quality large-caps).
2. **Street-buy holdouts (divergence to explain in CR253 calibration):** BA (+44%
   upside, 0/10), RIOT (+70%, 0/10), XPEV (+92%, 0/10), APD (+23%, 1/10 at R3 only),
   LEVI (+41%, approvals at R2/R3 but 0 at R5 — decision-limited). These five are
   the natural stress set for the disposition fix: high Street value signals the
   Room declines for timing-shaped reasons.
3. **Street-hold approvals:** AAPL (-3% target upside) approves 3/10 while BA at
   +44% gets 0/10 — the clearest restatement of the CR035 finding that the Room
   answers "buy now at this price?" (entry timing) while the Street answers
   "attractive over 12 months?" (value). Mean Street upside of R5-approved names
   ≈ +12%; mean upside of the five Street-buy holdouts ≈ +54%. No target-price
   field is fed to the room, so this gap is structural, not a defect per se.
4. **Jev vs Street:** the two highest-Jev names (LEVI 0.86, FCEL 0.82) are mid-
   table for the Street; Jev support is not tracking Street enthusiasm — more
   evidence (with finding 2 in analysis_r2) that support scores measure thesis
   coherence, not external accuracy.
5. **Benchmark hygiene:** with both sell names upgraded to hold, the current 30
   no longer exercise the red-line. If future rounds need sell coverage, re-draw
   sell names from the 142-name pool rather than reusing the stratified 30.

## Implications

- Keep this file + `results/consensus_refresh.jsonl` as the market reference for
  the CR253 calibration benchmark (75-room run): expected direction = disposition
  variant should pick up some of the Street-buy holdouts at R4/R5 without lifting
  red-line incidence on the (currently absent) sell stratum.
- A CR253 GO/NO-GO should be scored against this reference in addition to the
  frozen internal baseline: e.g. holdout-recovery rate on {BA, RIOT, XPEV, APD,
  LEVI} is a measurable external-facing metric.

**Files:** `results/consensus_refresh.jsonl` · `tools/fetch_market_consensus.py` ·
`tools/build_market_comparison.py`
