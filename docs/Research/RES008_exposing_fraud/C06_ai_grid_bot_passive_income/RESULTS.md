# C06 — RESULTS — "An AI grid / band robot earns passive income in any market"

**Verdict: `NOT SUPPORTED`.** Pre-registration: commit `3ac320eb` (2026-09-17), before any test
code existed. Run: 2026-09-17 · 22,356 grid runs + 1,746 band-grid runs · 808 s ·
`code/` 11 tests green. Every figure below is in [`out/results.json`](out/results.json).

Two of our own four predictions were wrong (H2, H4). Under the shared verdict rule that makes this
`NOT SUPPORTED`, not `DISPROVED` — and the measurements are reported as measurements.

---

## 1. Deviations and disclosed assumptions

Nothing in the pre-registration was changed: no parameter, instrument, window, metric or threshold.
The pre-registration's prose left 18 implementation choices open; each was fixed once, before
results were inspected, and is listed in [`out/DEVIATIONS.md`](out/DEVIATIONS.md). The ones a
reader is most likely to question:

| # | Choice | Effect |
|:--|:--|:--|
| 1 | `levels` = number of grid **lines** (so `levels − 1` order slots) | Exchange-tutorial reading. |
| 2–4 | Fixed quote amount per slot; inventory above the start price pre-bought at the start; the quantity bought is the quantity sold | Makes "grid profit" per completed pair well-defined. |
| 5 | 5× liquidation tested at each bar's **low** | The grid is never net short. Daily bars understate intrabar path, so liquidation is if anything under-counted. |
| 7 | Start price = first bar's open | — |
| 8 | ATR(14) = simple 14-bar mean of true range, not Wilder smoothing | Band arm only. |
| 9 | Band signals at the close, filled next open | Shared default. |
| 13 | Ruin (equity ≤ 20% of start) checked at the bar's worst point for the open basket | — |
| 16 | "Ruined within N years" counts only start dates with N years of data after them | Denominators printed below. |

Intraday caveat (shared pre-registration): the hourly arms cover roughly the last 730 days only and
are never the sole basis of a verdict. They are reported next to the daily arm, not instead of it.

## 2. Mechanism 1 — spot grid, BTC-USD and ETH-USD

Range ±10/20/30% around the start price × 10/20/50 lines = 9 settings per instrument; 90-day runs
started every 7 days; 10 bps per side. Daily arm: BTC from 2014, ETH from 2017, to 2026-08-31.

| Pooled over settings and both coins | Daily, 1× (n = 9,522) | Hourly, 1× (n = 1,656) |
|:--|--:|--:|
| Runs where the bot's **"grid profit"** is positive | **99.65%** | 99.64% |
| Runs where the **account** (true P&L incl. inventory) is negative | **36.80%** | 50.24% |
| Median true P&L over 90 days | +3.35% | −0.18% |
| 5th / 95th percentile true P&L | −37.2% / +11.5% | −29.4% / +10.6% |
| Runs that beat buy-and-hold from the same start | 51.09% | 62.68% |
| Runs that beat holding cash | 63.20% | 49.76% |
| Runs where price left the grid's range | 87.71% | 82.79% |

**With 5× leverage** (same runs): liquidated in **32.54%** of daily-arm runs (hourly 38.89%); 5th
percentile outcome −100%; beats buy-and-hold in 31.45%. By setting, liquidation share runs from
18.66% (BTC, ±30%, 10 lines) to 48.55% (ETH, ±10%, 50 lines); 17 of 18 settings are ≥ 20%.

**Best single setting**, daily 1×: BTC ±20% / 10 lines — true P&L ≥ 0 in 69.89% of 611 runs. No
setting reaches the 90% that would have supported "any market".

Shape of the payoff: the upside is capped at roughly the grid's width (95th percentile +11.5%),
the downside is the coin's (5th percentile −37.2%). Price leaves the range in 7 runs out of 8 —
upward, the bot has sold out and watches; downward, it has bought all the way down and holds.

## 3. Mechanism 2 — Bollinger band grid, no stop, EURUSD / GBPUSD / USDJPY

Sell above the upper band, buy below the lower, add on each further ATR against, close the basket
at the mean; constant and 1.5× martingale sizing; unit 0.5× / 1× / 2× starting equity; 2 bps per
side; ruin = equity ≤ 20% of start. Daily 2005 → 2026-08-31, 258 start dates per setting.

| Daily arm, pooled over 3 pairs | Basket win rate | Median monthly return | Ruined ≤ 1 y (n = 246) | ≤ 3 y (n = 222) | ≤ 5 y (n = 198) |
|:--|--:|--:|--:|--:|--:|
| constant 0.5× | 73.0% | +0.23% | 0.0% | 0.0% | 0.0% |
| constant 1× | 73.0% | +0.45% | 0.0% | 0.5% | 1.5% |
| constant 2× | 73.3% | +0.70% | 4.1% | 14.9% | 28.8% |
| martingale 0.5× | 76.4% | +0.27% | 1.2% | 5.0% | 9.6% |
| martingale 1× | 76.6% | +0.47% | 4.1% | 16.2% | 29.3% |
| martingale 2× | 76.9% | +0.73% | 11.4% | 32.9% | 51.5% |

Highest single-cell win rate 80.9% (USDJPY, martingale 2×); highest single-cell median monthly
return 0.75% (GBPUSD, constant 2×). **Hourly arm** (≈ 730 days, 33 starts per setting): median
monthly return negative in all six sizings (−0.44% to −3.44%); martingale 2× ruined within a year
from 61.9% of 21 eligible starts.

Doubling the size roughly doubles the monthly figure and multiplies the ruin share: going from 1×
to 2× adds 0.25 points of monthly return and moves 5-year ruin from 1.5% to 28.8%.

## 4. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | "Grid profit" positive in ≥ 95% of runs while true P&L negative in ≥ 30% | 99.65% and 36.80% (daily, 1×) | **met** |
| H2 | Grid beats buy-and-hold in fewer than half of daily-arm runs | 51.09% | **not met** — it is a coin flip against buy-and-hold, not worse |
| H3 | 5× grid liquidated in ≥ 20% of daily-arm 90-day runs | 32.54% | **met** |
| H4 | Band basket win rate ≥ 85%, and every sizing with median ≥ 3%/month ruined within 5 y from a majority of starts | Win rate 73–77%; **no** sizing reaches 3%/month (max 0.73%) | **not met** — we expected a higher win rate and a higher income than the mechanism delivers |

What would have supported the claim: a grid setting with true P&L ≥ 0 in ≥ 90% of daily runs —
best 69.89%, **not met**; a band sizing with ≥ 3%/month and zero ruin — none reaches 3%/month at
any ruin level, **not met**.

Neither side's conditions are met cleanly → **`NOT SUPPORTED`**.

## 5. What can and cannot be said

Can be said, as measurements:

- The number a grid bot's dashboard shows ("grid profit") was positive in 99.65% of 90-day runs
  while the account was down in 36.80% of them. The dashboard counts completed buy-low/sell-high
  pairs and leaves out the inventory bought on the way down.
- "Any market" fails on the downside tail: one 90-day run in twenty lost 37% or more, unlevered.
- At 5×, one 90-day run in three was liquidated.
- The band grid wins about three baskets in four and earns 0.2–0.7% a month at the median on daily
  bars; the size that gets it to 0.7% is ruined within five years from 29–52% of start dates.

Cannot be said:

- That a grid is *worse than holding the coin*. It was not: 51.09% of runs beat buy-and-hold, and
  the median 90-day run made +3.35%. We predicted otherwise and were wrong. A spot grid is a
  defensible way to be paid for providing liquidity in a range — it is a short-volatility position
  with a capped upside, not an income stream.
- Anything about a specific commercial bot. The logic of the products in the videos is not
  disclosed; this is the generic mechanism their own tutorials describe.
- Anything about grids on instruments other than BTC/ETH, or band grids other than the three pairs.
- The hourly arms are ≈ 2 years; they describe that period, not the mechanism.

## 6. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C06_ai_grid_bot_passive_income/code -q
.venv/bin/python C06_ai_grid_bot_passive_income/code/run_c06.py     # ≈ 14 min; data end pinned 2026-08-31
```

Figures: `out/grid_dashboard_vs_truth.png`, `out/band_grid_equity.png`. Text summary: `out/summary.txt`.
