# 01 — Prior work: what we already tested

Swept 2026-09-17 across this repo's `docs/Research/` and the earlier `saifgithub` research
repos (`Aegis-Finance`, `aegis-quant-classic`, `aegis-quant-frontier`, `AMI_QUANT`, `AMI_FOREX`,
`Another_Forex`, `Forex`, `AgenticForexTeam`, and the GitHub-only `aegis-quant`,
`aegis-finance`, `stock-fundamentals-`, `Commodities-Tracker`, `commodities-pricing`).

**Rule: what is listed as `solid` here is not re-tested.** It is reused. Each row below is
carried into [`TRACKER.md`](TRACKER.md) as a `P##` (prior) item.

**Verification status.** `✔ primary` = the quoted number was re-read in the primary file during
this sweep. `index` = taken from a summary or tombstone index; open the primary file once before
any number goes into a script. The Aegis repos are private, so an episode built on them needs
its evidence re-hosted (or re-run under RES008) before it can claim "reproducible".

Several Aegis-era studies report Sharpe/DSR. RES001 later banned Sharpe as a headline metric.
Their numbers are quoted here as recorded; an episode should lead with the kill criterion and
the holdout outcome, not the Sharpe figure.

---

## A. Solid — reuse, do not re-test

| P## | Claim tested | Where | Method in one line | Recorded verdict | Verified |
|:--|:--|:--|:--|:--|:--|
| P01 | "ML predicts stock direction" (the generic *AI predicts stocks* claim) | `docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md` | LightGBM, 13–32 tickers, daily + intraday, 5-fold walk-forward with purge gap, injected-signal control (recovers AUC 0.95), shuffled-label control (0.4969), 11-model shoot-out | Overall AUC 0.5292 **but edge negative in 30 of 32 cells** against an always-up baseline; after removing market beta by cross-sectional ranking AUC 0.5055, p = 0.62; intraday exactly chance | ✔ primary |
| P02 | A volatility/gamma "flip" predicts downside | RES001 part 04 | SPY, VIX, 9 sector ETFs, daily 2005–2026, define 2005–18 / confirm 2019–26, matched control | **0 of 18** intervals exclude zero; definition-window signs run opposite to the prediction; 11–54 events in 21 years | ✔ primary (RES001 README) |
| P03 | Volatility regime predicts *direction* | RES001 part 03 | same data, 3 horizons × 2 windows | Null; point estimates flip sign across the sample split | ✔ primary |
| P04 | "Stop trading after k losses" improves results | RES001 part 06 | rule vs matched random skip, 12 cells | Rule below placebo in 10 of 12 cells — mechanically mildly harmful; its value is behavioural | ✔ primary |
| P05 | Heavy volume without progress predicts reversal | RES001 part 06 | daily-bar proxy, 3 horizons × 2 windows | All six point estimates lean the wrong way. **Caveat that must be said on camera:** a daily-bar proxy is ~3 orders of magnitude coarser than real order flow | ✔ primary |
| P06 | A contest-winning return proves skill | RES001 part 03 §E / README finding 1 | null model: expected maximum among N zero-skill entrants | +100% in a month is the *expected maximum* among a few hundred zero-skill entrants at 4–6× SPY volatility. Conditional statement only — says nothing about any individual | ✔ primary |
| P07 | Pre-FOMC drift is a tradeable edge | `Aegis-Finance/…/edge_hunt_2026-07/FINDINGS.md` P1 | 259 FOMC dates 1994–2026, pre-registered kill line | Real 1994–2014; **dead in 2015–2026** (below kill line, sign flip 2015–19). Killed | ✔ primary |
| P08 | FX fix reversal / month-end continuation | same file, P3 + P3b | own tick data, in-sample on 7 series, **true holdout on 5 unseen pairs**, 390 trades | Gross signal real (+2.26 bps, 5/5 pairs) — **net of costs below the pre-registered bar** (+1.19 bps, t 1.43 < 2.0). Killed. The cleanest "real but cost-eaten" case we hold | ✔ primary |
| P09 | Regime-timed strategy beats buy-and-hold | `Aegis-Finance/finance/docs/strategy_cemetery/` T-005; `aegis-quant-classic/docs/TIER1_EVIDENCE_REPORT.md` | 207 instruments, walk-forward, deflated-Sharpe gate, cost stress | Zero instruments pass the gate. Includes a self-caught coordinate-space bug post-mortem | index |
| P10 | HMM regime labels predict direction | cemetery T-001 | 207 instruments | Directional agreement ≈ 0.50 universe-wide | index |
| P11 | Opening-range breakout, intraday | cemetery T-006 | 82 instruments, walk-forward | 0 of 82 pass | index |
| P12 | Breakout-combination sweep on gold | cemetery T-020 | 65-cell sweep, walk-forward + holdout | Best in-sample cell was the worst in holdout — a textbook overfitting picture | index |
| P13 | Meta-labelling adds directional edge | cemetery T-021 | — | OOS AUC ≈ 0.5; it destroyed the one positive baseline | index |
| P14 | A neural-SDE "daily edge" | `Aegis-Finance/…/CR033_STAGE3_RESULTS_AND_WHY_DSR_IS_ZERO.md`, T-010 | 17 walk-forward windows, daily vs M1-resampled features, independently reproduced | The impressive daily figure was a non-tradeable smoothing artifact; IC ≈ 0 at M1/M30/H1 | index |
| P15 | Gold swing S/R + RSI reversal | `AMI_FOREX/docs/strategies/R-rev-1.md` + raw `results.json` | XAUUSD 5 y + ~1 y OOS, costs modelled, two null controls | `"verdict": "no edge"`; expectancy −0.135 R in-sample (296 trades), −0.079 R OOS (72); underperformed the random-entry control at every R:R | sweep-verified vs raw JSON |

## B. Exists but too weak to publish without a re-run

| P## | Item | Why it is not ready |
|:--|:--|:--|
| P16 | VWAP pullback on a leveraged ETF (`Another_Forex`) | Positive IS/OOS split, but costs are not itemised and it was later abandoned ("attention cost exceeded what the edge paid") |
| P17 | MT5 EA parameter sweeps (`Forex/backtester/*_sweep_results.csv`) | Real costed numbers, no narrative verdict; supporting evidence only |
| P18 | Remaining cemetery tombstones (T-007, T-008, T-011–T-017) | Numbers seen only in the index |
| P19 | Fundamentals-fed LLM verdict, single-ticker case study | One ticker; one claim already self-retracted. Not a test of an edge claim |

`Forex/news_validator/` is a fully built LLM news-classification harness that was **never run** —
no result exists. It is a ready tool if a sentiment claim is taken up later.

## C. What held up — reported, not buried

These are the honest counterweight and the raw material for a "what is actually real" episode.

| P## | Finding | Size and the catch |
|:--|:--|:--|
| P20 | Volatility is forecastable; regime-aligned sizing homogenises risk | Variance ratio 0.57–0.75 vs shuffled-size placebo, every interval below 1.0 (RES001 part 03). **A risk method, not a return method** — it lowered mean return on the holdout (+1.34% → +1.04%) |
| P21 | Dispersion rotates with regime | Real and long documented; public knowledge, not an edge |
| P22 | Conditioned VIX-futures carry | Survived its kill line marginally; carried by 2012–2017, thin after 2020, negative skew |
| P23 | Crypto perpetual funding carry | Survived (8.4% net annualised while in market, post-2024) but decaying toward the kill line through 2026 H1, and assumes a perfect hedge |
| P24 | Gold overnight drift | Positive through walk-forward and a disjoint lockbox in the `Forex` repo; single instrument, private evidence — needs an RES008-standard re-run before any public statement |

## The pattern across all of it

Three independent programmes (RES001, the Aegis family, the Forex/MT5 sweeps) landed in the same
place: **second moments and risk premia are real; directional prediction is not.** Volatility
clusters, correlations rise in stress, carry pays until it doesn't. Everything that claimed to
predict *direction* from price history died at the holdout or at the cost line. That is the
spine of the channel.
