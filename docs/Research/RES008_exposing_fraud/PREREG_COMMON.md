# RES008 — shared pre-registration: universes, windows, costs, statistics

Committed before any RES008 test code runs. Every `C##/PREREGISTRATION.md` inherits this file and
may only *narrow* it (a subset of tickers for compute reasons, stated there). Nothing here is
changed after results are seen; a deviation is recorded in the claim's `RESULTS.md`, first section.

## Universes (fixed)

| Name | Members | Why these |
|:--|:--|:--|
| `U-EQ` | AAPL MSFT AMZN GOOGL META NVDA TSLA JPM JNJ XOM PG KO WMT DIS INTC CSCO BA GE PFE T · SPY QQQ | 20 large US names + 2 index ETFs. Deliberately includes long-run laggards (INTC, BA, GE, PFE, T, DIS) so the list is not "today's winners". |
| `U-CRYPTO` | BTC-USD ETH-USD | What the crypto videos trade. |
| `U-FX` | EURUSD=X GBPUSD=X USDJPY=X | What the forex videos trade. |
| `U-LARGE100` | 100 large US companies frozen in `C08_chatbot_stock_picks/code/universe_large100.py` at pre-registration (based on S&P 100 membership; exact membership not asserted) | Only for C08. |

**Survivorship, stated once:** every list is chosen today, so every member survived. That flatters
buy-and-hold and any long-biased rule *equally*. All RES008 verdicts rest on a strategy **versus
its own placebo or versus buy-and-hold on the same tickers**, where the bias cancels. No RES008
number is a statement about what an investor would have earned.

## Windows (fixed)

- `DEFINE` 2005-01-01 → 2018-12-31 · `HOLDOUT` 2019-01-01 → 2026-08-31 (RES001 convention).
- Data end is pinned at **2026-08-31** so a re-run reproduces.
- Instruments with shorter history start at their first bar (META 2012, TSLA 2010, BTC 2014, ETH 2017).
- Intraday from Yahoo: 60-minute ≈ last 730 days, 5-minute ≈ last 60 days. Short, and said so
  wherever used. An intraday cell is never the sole basis of a `DISPROVED`.

## Data

`yfinance`, daily OHLCV, `auto_adjust=False`, O/H/L/C multiplied by `adj_close/close` (total-return
basis), via `common/data.py`. Cached locally; caches are not committed.

## Execution and costs (same for every arm, including placebos)

- Default execution: signal computed on bar *t* close, filled at bar *t+1* open (`next_open`).
  `same_close` is used only to reproduce an "as taught" arm and is labelled.
- Costs per side, charged on every position change: **equities/ETFs 5 bps · crypto 10 bps · FX 2 bps.**
  These are deliberately modest (commission-free broker, liquid names, small size). Gross results
  are reported alongside net so nobody can say costs alone produced the verdict.
- Bracket orders: if take-profit and stop both fall inside one bar, the **stop** is assumed hit
  first; gaps fill at the open. No leverage unless the claim itself uses it.

## Statistics

- Intervals: stationary block bootstrap (Politis–Romano), 5,000 resamples, 95% percentile, fixed
  seed, via `common/bootstrap.py`. Win rates on independent-ish trades: Wilson interval.
- Comparisons to buy-and-hold are **paired** on daily returns over identical bars.
- Placebo: matched random entries — same number of trades, same sides, same holding-period
  multiset, same costs — ≥ 500 replications per instrument. "Skill" means beating the placebo;
  "worth doing" means beating buy-and-hold net of costs. Both are reported; they are different
  questions.
- No Sharpe ratio. No annualised figure from a window shorter than three years. No p-values.
- Every headline number carries its window and its interval.

## Verdict rule (all claims)

Each claim file states, in advance, (a) what result would count as **supporting the claim** and
(b) what result supports **our** hypothesis that it fails. If (a) occurs, the verdict is `HOLDS` or
`PARTLY HOLDS` and it is published as such. If neither is met cleanly, the verdict is
`NOT SUPPORTED`, never `DISPROVED`.
