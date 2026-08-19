# CR164 backtest scoring report — batch `r70-paired-1`

Report date 2026-08-19 · seed 164 · bootstrap 10000 · arm(s): pit_v1

Sources: `backtest_run_index ⋈ room_runs` + `price_history_daily` (source != 'mock_walk') only — no live quotes. Byte-reproducible: rerun with the same DB state, --seed and --stamp to get identical bytes.

## Run accounting

- Index rows: **126**
- Excluded — missing room_runs row: 0, not completed: 0, null verdict: 0, non-bucket action: 0
- Bucketed (scored population): **126** — APPROVE: 9, PASS: 117, REJECT: 0, MODIFY: 0
- Distinct as-of dates: **71**
- Unscoreable at horizon — no entry bar: 0, no +5d row: 0, no +20d row: 0, no SPY +5d: 0, no SPY +20d: 0

## Forward returns by verdict bucket

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE | 1w | 9 | +5.08% | 9 | +4.32% |
| APPROVE | 4w | 9 | +7.61% | 9 | +6.13% |
| PASS | 1w | 117 | -0.43% | 117 | -0.84% |
| PASS | 4w | 117 | +2.66% | 117 | +0.71% |
| REJECT | 1w | 0 | — | 0 | — |
| REJECT | 4w | 0 | — | 0 | — |
| MODIFY | 1w | 0 | — | 0 | — |
| MODIFY | 4w | 0 | — | 0 | — |

Primary read: **APPROVE vs PASS** mean 1w/4w raw and excess above.

## Sensitivity: (APPROVE+MODIFY) vs (PASS+REJECT)

| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |
|---|---|---|---|---|---|
| APPROVE+MODIFY | 1w | 9 | +5.08% | 9 | +4.32% |
| APPROVE+MODIFY | 4w | 9 | +7.61% | 9 | +6.13% |
| PASS+REJECT | 1w | 117 | -0.43% | 117 | -0.84% |
| PASS+REJECT | 4w | 117 | +2.66% | 117 | +0.71% |

## Random-pick null (4w excess vs SPY)

Per as-of date with APPROVEs: draw |APPROVE_d| tickers uniformly (without replacement) from that date's convened tickers with a scoreable 4w excess, 10000× seeded; p = P(draw mean ≥ actual APPROVE mean).

| as_of | n APPROVE | pool | actual mean | p |
|---|---|---|---|---|
| 2025-07-04 | 1 | 2 | -0.70% | 0.5025 |
| 2025-07-11 | 2 | 2 | +1.16% | 1.0000 |
| 2025-07-18 | 2 | 2 | +20.74% | 1.0000 |
| 2025-08-29 | 1 | 1 | +7.27% | 1.0000 |
| 2025-10-17 | 1 | 2 | -3.16% | 1.0000 |
| 2025-12-12 | 1 | 1 | +2.19% | 1.0000 |
| 2026-02-13 | 1 | 2 | +5.78% | 1.0000 |

Pooled (dates weighted by n APPROVE): actual **+6.13%**, p = **0.6248** over 10000 pooled draws.

## Date-clustered CI — APPROVE − PASS, 4w excess

- Actual spread (mean APPROVE − mean PASS, 4w excess): **+5.43%**
- Block bootstrap over dates (9992 usable of 10000 replicates; 8 dropped an empty bucket):
  - 2.5th pct: -1.48%
  - 50th pct: +4.97%
  - 97.5th pct: +13.69%
- **Effective n = 71 distinct as-of dates** (not 126 runs — date clustering).

## Target/stop-hit (20 trading days after as-of, provenance-gated)

APPROVE/MODIFY runs carrying entry+target+stop; each leg scored only when its `level_provenance` is a stated level (not 'ami_default', not missing).

- Runs with all three levels: **9** — target leg provenance-excluded: 0, stop leg provenance-excluded: 0
- Target: evaluated 9, hit 3 (33.3% of scoreable), unscoreable 0
- Stop: evaluated 9, hit 3 (33.3% of scoreable), unscoreable 0
- First-touch (both legs evaluated): target_first: 3, stop_first: 3, ambiguous: 0, neither: 3, unscoreable: 0

## EDGAR PIT field coverage

Per bucketed run (126 runs), via `edgar_pit.fetch_pit_fundamentals(ticker, as_of)`.

| field | runs with field | coverage |
|---|---|---|
| pe | 80/126 | 63.5% |
| rev_growth | 91/126 | 72.2% |
| profit_margin | 79/126 | 62.7% |
| net_cash | 88/126 | 69.8% |
| price_to_sales | 80/126 | 63.5% |
| fcf_yield | 90/126 | 71.4% |
| ev_to_ebitda | 44/126 | 34.9% |
| dividend_yield | 61/126 | 48.4% |

## Limitations register (CR164)

1. Selection edge only — no Sharpe/portfolio claims (no SELL action, no portfolio; `docs/benchmark/claude/09` R1/R3).
2. ~12% verdict-flip noise floor (no temperature/seed in the gateway); the repeat-run subsample re-quantifies it per sweep.
3. Tested Room ≠ live Room: news, social, analyst target/rating, forward P/E, PEG, next-earnings all UNAVAILABLE.
4. Effective n ≈ #as-of dates, not convene count (date clustering).
5. Pre-cutoff structurally excluded; near-cutoff approximate price knowledge mitigated by the 8-week margin, not eliminated.
6. Survivorship: tickers_150 is a July-2026 live-name screen; membership-audit counts published verbatim.
7. Close-execution assumption, adj_close total-return proxy, static sector labels, no FOMC countdown for 2025 dates, differential EDGAR tag coverage (stats published).
