# CR164 backtest scoring report — batch `r70-outcome-2`

Report date 2026-08-21 · seed 164 · bootstrap 10000 · arm(s): pit_v1

Sources: `backtest_run_index ⋈ room_runs` + `price_history_daily` (source != 'mock_walk') only — no live quotes. Byte-reproducible: rerun with the same DB state, --seed and --stamp to get identical bytes.

## Run accounting

- Sweep completion: **COMPLETE** — planned 450, completed 50, failed 0, finished 2026-08-21T10:20:54.960227+00:00.
- Index rows: **450**
- Excluded — missing room_runs row: 0, not completed: 4, null verdict: 0, non-bucket action: 0, LLM-outage fail-safe: 0
- Bucketed (scored population): **446** — APPROVE: 40, PASS: 406, REJECT: 0, MODIFY: 0
- Distinct as-of dates: **18**
- Unscoreable at horizon — no entry bar: 0, no +5d row: 0, no +20d row: 0, no SPY +5d: 0, no SPY +20d: 0

## Forward returns by verdict bucket

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE | 1w | 40 | +0.14% | 40 | +0.47% |
| APPROVE | 4w | 40 | +3.20% | 40 | +1.40% |
| PASS | 1w | 406 | +1.02% | 406 | +0.94% |
| PASS | 4w | 406 | +2.39% | 406 | +0.25% |
| REJECT | 1w | 0 | — | 0 | — |
| REJECT | 4w | 0 | — | 0 | — |
| MODIFY | 1w | 0 | — | 0 | — |
| MODIFY | 4w | 0 | — | 0 | — |

Primary read: **APPROVE vs PASS** mean 1w/4w raw and excess above.

## Sensitivity: (APPROVE+MODIFY) vs (PASS+REJECT)

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE+MODIFY | 1w | 40 | +0.14% | 40 | +0.47% |
| APPROVE+MODIFY | 4w | 40 | +3.20% | 40 | +1.40% |
| PASS+REJECT | 1w | 406 | +1.02% | 406 | +0.94% |
| PASS+REJECT | 4w | 406 | +2.39% | 406 | +0.25% |

## Random-pick null (4w excess vs SPY)

Per as-of date with APPROVEs: draw |APPROVE_d| tickers uniformly (without replacement) from that date's convened tickers with a scoreable 4w excess, 10000× seeded; p = P(draw mean ≥ actual APPROVE mean).

| as_of | n APPROVE | pool | actual mean | p |
|---|---|---|---|---|
| 2025-02-28 | 4 | 25 | -8.77% | 0.8751 |
| 2025-04-11 | 4 | 25 | +5.93% | 0.6060 |
| 2025-05-09 | 3 | 25 | +11.73% | 0.0566 |
| 2025-06-13 | 1 | 25 | +5.35% | 0.2372 |
| 2025-07-11 | 3 | 25 | +2.27% | 0.2994 |
| 2025-08-08 | 2 | 25 | +14.51% | 0.0949 |
| 2025-08-15 | 2 | 22 | -2.69% | 0.5987 |
| 2025-09-12 | 2 | 25 | -1.36% | 0.6053 |
| 2025-10-31 | 2 | 25 | -6.03% | 0.5998 |
| 2025-11-28 | 3 | 25 | +1.04% | 0.3528 |
| 2025-12-05 | 1 | 25 | +4.98% | 0.2471 |
| 2026-01-09 | 1 | 25 | +2.28% | 0.4662 |
| 2026-02-06 | 2 | 25 | +4.79% | 0.2840 |
| 2026-03-13 | 1 | 25 | +12.22% | 0.2819 |
| 2026-04-10 | 1 | 25 | -8.27% | 0.8028 |
| 2026-04-24 | 2 | 24 | -12.00% | 0.8572 |
| 2026-06-12 | 2 | 25 | +4.60% | 0.2303 |
| 2026-06-19 | 4 | 25 | +0.51% | 0.4064 |

Pooled (dates weighted by n APPROVE): actual **+1.40%**, p = **0.3010** over 10000 pooled draws.

## Date-clustered CI — APPROVE − PASS, 4w excess

- Actual spread (mean APPROVE − mean PASS, 4w excess): **+1.15%**
- Block bootstrap over dates (10000 usable of 10000 replicates; 0 dropped an empty bucket):
  - 2.5th pct: -2.05%
  - 50th pct: +1.17%
  - 97.5th pct: +4.43%
- **Effective n = 18 distinct as-of dates** (not 446 runs — date clustering).

## Target/stop-hit (20 trading days after as-of, provenance-gated)

APPROVE/MODIFY runs carrying entry+target+stop; each leg scored only when its `level_provenance` is a stated level (not 'ami_default', not missing).

- Runs with all three levels: **40** — target leg provenance-excluded: 0, stop leg provenance-excluded: 0
- Target: evaluated 40, hit 10 (25.0% of scoreable), unscoreable 0
- Stop: evaluated 40, hit 15 (37.5% of scoreable), unscoreable 0
- First-touch (both legs evaluated): target_first: 9, stop_first: 13, ambiguous: 0, neither: 18, unscoreable: 0

## EDGAR PIT field coverage

Per bucketed run (446 runs), via `edgar_pit.fetch_pit_fundamentals(ticker, as_of)`.

| field | runs with field | coverage |
|---|---|---|
| pe | 299/446 | 67.0% |
| rev_growth | 363/446 | 81.4% |
| profit_margin | 335/446 | 75.1% |
| net_cash | 276/446 | 61.9% |
| price_to_sales | 337/446 | 75.6% |
| fcf_yield | 321/446 | 72.0% |
| ev_to_ebitda | 137/446 | 30.7% |
| dividend_yield | 196/446 | 43.9% |

## Limitations register (CR164)

1. Selection edge only — no Sharpe/portfolio claims (no SELL action, no portfolio; `docs/benchmark/claude/09` R1/R3).
2. ~12% verdict-flip noise floor (no temperature/seed in the gateway); the repeat-run subsample re-quantifies it per sweep.
3. Tested Room ≠ live Room: news, social, analyst target/rating, forward P/E, PEG, next-earnings all UNAVAILABLE.
4. Effective n ≈ #as-of dates, not convene count (date clustering).
5. Pre-cutoff structurally excluded; near-cutoff approximate price knowledge mitigated by the 8-week margin, not eliminated.
6. Survivorship: tickers_150 is a July-2026 live-name screen; membership-audit counts published verbatim.
7. Close-execution assumption, adj_close total-return proxy, static sector labels, no FOMC countdown for 2025 dates, differential EDGAR tag coverage (stats published).
