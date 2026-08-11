# CR164 backtest scoring report — batch `pit-pilot-2`

Report date 2026-08-11 · seed 164 · bootstrap 10000 · arm(s): pit_v1

Sources: `backtest_run_index ⋈ room_runs` + `price_history_daily` (source != 'mock_walk') only — no live quotes. Byte-reproducible: rerun with the same DB state, --seed and --stamp to get identical bytes.

## Run accounting

- Index rows: **126**
- Excluded — missing room_runs row: 0, not completed: 1, null verdict: 0, non-bucket action: 0
- Bucketed (scored population): **125** — APPROVE: 13, PASS: 112, REJECT: 0, MODIFY: 0
- Distinct as-of dates: **71**
- Unscoreable at horizon — no entry bar: 0, no +5d row: 0, no +20d row: 0, no SPY +5d: 0, no SPY +20d: 0

## Forward returns by verdict bucket

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE | 1w | 13 | -0.57% | 13 | -1.01% |
| APPROVE | 4w | 13 | +5.75% | 13 | +4.83% |
| PASS | 1w | 112 | +0.05% | 112 | -0.41% |
| PASS | 4w | 112 | +2.57% | 112 | +0.60% |
| REJECT | 1w | 0 | — | 0 | — |
| REJECT | 4w | 0 | — | 0 | — |
| MODIFY | 1w | 0 | — | 0 | — |
| MODIFY | 4w | 0 | — | 0 | — |

Primary read: **APPROVE vs PASS** mean 1w/4w raw and excess above.

## Sensitivity: (APPROVE+MODIFY) vs (PASS+REJECT)

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE+MODIFY | 1w | 13 | -0.57% | 13 | -1.01% |
| APPROVE+MODIFY | 4w | 13 | +5.75% | 13 | +4.83% |
| PASS+REJECT | 1w | 112 | +0.05% | 112 | -0.41% |
| PASS+REJECT | 4w | 112 | +2.57% | 112 | +0.60% |

## Random-pick null (4w excess vs SPY)

Per as-of date with APPROVEs: draw |APPROVE_d| tickers uniformly (without replacement) from that date's convened tickers with a scoreable 4w excess, 10000× seeded; p = P(draw mean ≥ actual APPROVE mean).

| as_of | n APPROVE | pool | actual mean | p |
|---|---|---|---|---|
| 2025-03-14 | 1 | 2 | -10.87% | 1.0000 |
| 2025-03-21 | 1 | 2 | +14.43% | 0.5022 |
| 2025-04-25 | 1 | 2 | -3.20% | 0.4949 |
| 2025-07-04 | 1 | 2 | -0.70% | 0.4951 |
| 2025-07-11 | 1 | 2 | +0.11% | 1.0000 |
| 2025-08-01 | 1 | 2 | +7.37% | 0.4998 |
| 2025-09-05 | 1 | 2 | +6.71% | 0.5067 |
| 2025-10-17 | 1 | 2 | -3.16% | 1.0000 |
| 2025-12-12 | 1 | 1 | +2.19% | 1.0000 |
| 2026-01-02 | 1 | 2 | +48.78% | 0.4961 |
| 2026-01-23 | 1 | 2 | -27.38% | 1.0000 |
| 2026-03-20 | 1 | 1 | +18.39% | 1.0000 |
| 2026-05-29 | 1 | 2 | +10.10% | 0.4986 |

Pooled (dates weighted by n APPROVE): actual **+4.83%**, p = **0.1153** over 10000 pooled draws.

## Date-clustered CI — APPROVE − PASS, 4w excess

- Actual spread (mean APPROVE − mean PASS, 4w excess): **+4.23%**
- Block bootstrap over dates (10000 usable of 10000 replicates; 0 dropped an empty bucket):
  - 2.5th pct: -4.98%
  - 50th pct: +4.09%
  - 97.5th pct: +14.26%
- **Effective n = 71 distinct as-of dates** (not 125 runs — date clustering).

## Target/stop-hit (20 trading days after as-of, provenance-gated)

APPROVE/MODIFY runs carrying entry+target+stop; each leg scored only when its `level_provenance` is a stated level (not 'ami_default', not missing).

- Runs with all three levels: **13** — target leg provenance-excluded: 0, stop leg provenance-excluded: 0
- Target: evaluated 13, hit 3 (23.1% of scoreable), unscoreable 0
- Stop: evaluated 13, hit 5 (38.5% of scoreable), unscoreable 0
- First-touch (both legs evaluated): target_first: 2, stop_first: 5, ambiguous: 0, neither: 6, unscoreable: 0

## EDGAR PIT field coverage

Per bucketed run (125 runs), via `edgar_pit.fetch_pit_fundamentals(ticker, as_of)`.

| field | runs with field | coverage |
|---|---|---|
| pe | 79/125 | 63.2% |
| rev_growth | 91/125 | 72.8% |
| profit_margin | 79/125 | 63.2% |
| net_cash | 87/125 | 69.6% |
| price_to_sales | 80/125 | 64.0% |
| fcf_yield | 77/125 | 61.6% |
| ev_to_ebitda | 43/125 | 34.4% |
| dividend_yield | 60/125 | 48.0% |

## Limitations register (CR164)

1. Selection edge only — no Sharpe/portfolio claims (no SELL action, no portfolio; `docs/benchmark/claude/09` R1/R3).
2. ~12% verdict-flip noise floor (no temperature/seed in the gateway); the repeat-run subsample re-quantifies it per sweep.
3. Tested Room ≠ live Room: news, social, analyst target/rating, forward P/E, PEG, next-earnings all UNAVAILABLE.
4. Effective n ≈ #as-of dates, not convene count (date clustering).
5. Pre-cutoff structurally excluded; near-cutoff approximate price knowledge mitigated by the 8-week margin, not eliminated.
6. Survivorship: tickers_150 is a July-2026 live-name screen; membership-audit counts published verbatim.
7. Close-execution assumption, adj_close total-return proxy, static sector labels, no FOMC countdown for 2025 dates, differential EDGAR tag coverage (stats published).
