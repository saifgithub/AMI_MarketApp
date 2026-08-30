# RES003 — Pre-registration

**Written and committed before any code ran.** Frozen 2026-08-30.

## Where this came from

Two practitioners, no connection to each other, different instruments, both claim the same
mechanism (RES002): **gamma/volatility regime tells you how much to risk, not which way to
go.** Creamer (micro futures, orderflow): negative gamma means expect faster moves.
Ireland (SPY options): negative gamma means size down 30–50% and take profit at 1R
instead of 2R. Both also independently arrive at heavy non-participation.

Saiful's question: *"are these two just lucky, or do they have a method?"*

## What we can and cannot answer

**Cannot:** whether *these two people* are skilled. There is no audited trade log for either,
both trade instruments and horizons we have no data for, and both are selling something.
No test we can run touches that.

**Can:** (a) whether the *mechanism they both credit* is real in data we do have, and
(b) whether a championship result of the size claimed is surprising under pure luck.

The distinction matters. If the mechanism is absent, their results are unexplained by the
thing they say explains them. If it is present, they have a defensible basis — which is
still not proof that they personally execute it well.

## Hypothesis

> Volatility regime, classified using only past information, predicts forward realized
> **volatility** but not forward **direction**; and scaling position size inversely to
> regime homogenizes realized risk per trade beyond what varying size at random achieves.

## Data

- `SPY` daily OHLC, 2005-01-03 → 2026-08-28, via `yfinance` (already a backend dep).
- `^VIX` daily close, same window. **Verified available: 5,449 rows.**
- `^VIX3M` / `^VIX9D` / `^VXV` — **Yahoo serves no history** (verified: 1 row or zero).
  VIX *term structure* is therefore unavailable, and it is the closest free analogue to
  GEX's forward-looking dealer positioning. We substitute VIX **level percentile**, which
  is still implied (forward-looking) but is not the curve. This is a real weakening of the
  proxy and must be stated in any writeup.

## Regime classification — ex-ante, information through t−1 close only

- `vix_pct` — percentile rank of VIX close at t−1 within the trailing 504 trading days.
- `gk_pct` — percentile rank of 20-day Garman-Klass realized vol at t−1, same window.
  GK uses the full OHLC bar and is materially more efficient than close-to-close on daily data:
  `σ²_GK = 0.5·(ln(H/L))² − (2ln2 − 1)·(ln(C/O))²`, averaged over 20 days, ×252.
- **Primary classifier: `vix_pct`.** Secondary `gk_pct` for robustness.
- Terciles: `calm` (<33.3), `normal`, `stressed` (>66.7).

## Windows

- **Definition window: 2005-01-03 → 2018-12-31.** All thresholds and constants fixed here.
- **Holdout: 2019-01-01 → 2026-08-28.** Untouched until the definition is frozen.
- One shot at the holdout. Any retune afterwards burns it, and the writeup must say so.

## Horizons

h ∈ {5, 10, 21} trading days — spanning `Verdict.time_horizon_days` in the live app.

## Inference

Daily observations are heavily autocorrelated (volatility clusters), so naive standard
errors are invalid. **Stationary block bootstrap, expected block length 2h, 10,000
resamples**, for every interval reported. Intervals, never p-values.

## Tests and kill criteria

**A — regime → forward realized vol.** Statistic: ratio of mean forward realized vol,
stressed ÷ calm. *Kill: 95% CI includes 1.0.* Expected to pass; this is a calibration check
on our instrument, not a discovery — vol clustering is among the most robust facts in finance.
If A fails, our code is wrong, not the market.

**B — regime → forward direction. Expected to produce a null.** Statistic: difference in
mean forward log return, stressed − calm, and each regime's mean vs zero. *Inverted kill:
if the CI excludes zero, stop and re-scope* — a regime term that predicts direction is a
trading signal, not risk management, and that is outside what a simulation-only training
product should carry. A null must be reported with its interval: a null with a wide band is
"no power", not "no effect".

**C — does regime scaling homogenize realized risk?** No strategy: 10,000 random entry dates,
fixed holding period h, long-only, evaluated on the **identical entry set** across three arms.

| Arm | Size rule |
|:---|:---|
| 1 · constant | 1.0 |
| 2 · vol-scaled | `clip(target_vol / forecast_vol, 0.5, 1.5)`, `forecast_vol` = GK vol at t−1, `target_vol` = median GK vol **on the definition window**, frozen |
| 3 · shuffled (placebo) | the arm-2 multiset of sizes, randomly permuted across entries |

Arm 3 is the control that makes this a real test: it has identical size dispersion but no
alignment with regime. **If arm 2 does not beat arm 3, then varying size is doing the work
and knowing the regime is not** — which would mean these two have a habit, not a method.

Primary metric: **variance of per-trade P&L**, arm 2 ÷ arm 3. Second moment, so estimable at
this n. *Kill: CI includes 1.0.* Secondary: 95th-percentile loss, excess kurtosis.

Mean P&L is reported for every arm **with its interval and an explicit note that it is not
precisely estimable** (Lo 2002; CR136 Rev 2 dropped Sharpe and every mean-numerator ratio for
this reason). We are not claiming the rule makes money. No Sharpe is computed anywhere.

**E — is a championship result evidence of skill?** Under a null of zero skill, N entrants
each draw a one-month return from a zero-mean distribution with monthly vol *v*. Simulate the
distribution of the **maximum** across N. Solve for the *v* at which a +100% winner is the
expected maximum, for N ∈ {50, 100, 300, 500}. Then ask whether that *v* is plausible for
leveraged micro-futures day trading. *If it is, the championship is not evidence of skill* —
it is what a contest of that size produces by construction.

## What would change our mind

- A passes, B nulls, C's arm 2 beats arm 3 → the mechanism is real and worth a CR.
- A passes, B nulls, C's arm 2 ties arm 3 → vol targeting works, regime knowledge adds nothing.
- B comes back directional → re-scope; this is not the feature we thought.
- E shows +100% is unsurprising → the trophy is not evidence, whatever the mechanism does.
