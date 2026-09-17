# C01 — "A neural network predicts tomorrow's stock price" — PRE-REGISTRATION

Written 2026-09-17, before any C01 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

An LSTM trained on a stock's own past closing prices predicts the next close. The evidence shown
is a predicted-vs-actual chart that overlays almost perfectly on the test set, plus a low RMSE.
Landscape class L1 — 2 videos read, 1.95M views (measured 2026-09-17).

## Recipe reproduced (Arm A — "as taught")

Variant **A1**, fully specified in its source: feature = close only; `MinMaxScaler(0,1)` **fit on
the entire series before the split**; look-back 100 days; chronological 65/35 split; 3 stacked
LSTM layers × 50 units → Dense(1); MSE loss; Adam; 100 epochs; batch 64; target = next close
(price level).

Variant **A2**: look-back 60; scaler fit on the whole series; 80/20 split; target = next close.
Its source does not show the full architecture or epoch count on screen. **Our assumption,
disclosed:** LSTM(50) → LSTM(50) → Dense(25) → Dense(1), 20 epochs, batch 32.

Both in PyTorch (the sources use Keras; layer sizes, loss and optimiser are identical).

## Fair arm (Arm B)

Same architectures. Scaler fit on the **training segment only**. Two targets: **B-price** (next
close) and **B-return** (next-day return, the quantity a trader needs).

## Data

Narrowed universe for compute: `U-LSTM` = AAPL MSFT AMZN NVDA TSLA JPM XOM KO INTC SPY.
Daily adjusted closes 2012-01-01 → 2026-08-31. 3 seeds per ticker per arm. Test segment = the
last 35% (A1, B) or 20% (A2) of each series.

Compute contingency, fixed now: if a single A1 run exceeds 4 minutes on this Mac, epochs drop to
50 for **all** arms and `RESULTS.md` says so.

## Measurements (test segment only)

1. **M1 — persistence ratio.** RMSE(model) ÷ RMSE(naive forecast "tomorrow = today"), per
   ticker-seed. Price-level RMSE, exactly the metric the videos quote.
2. **M2 — what the prediction tracks.** corr(predicted change, actual change) where predicted
   change = ŷ(t+1) − y(t); against corr(ŷ(t+1) − ŷ(t), y(t) − y(t−1)), i.e. does the forecast
   move with *tomorrow* or echo *yesterday*. Also the lag at which cross-correlation of ŷ and y peaks.
3. **M3 — direction.** Hit rate of sign(ŷ(t+1) − y(t)) against the realised sign, versus the
   always-up base rate of the same test segment. Wilson interval per ticker; block bootstrap pooled.
4. **M4 — money.** Long when ŷ(t+1) > y(t), else flat. `same_close` (the generous reading) and
   `next_open`; 5 bps. Paired difference in mean daily return versus buy-and-hold, pooled, block
   bootstrap interval.
5. **M5 — the leak.** A1 versus the identical model with the scaler fit on train only: change in
   test RMSE. Reported, not part of the verdict.
6. **M6 — the "30-day forecast".** Recursive self-fed forecast, 30 steps, from the end of the
   training segment: ratio of the forecast path's daily-change standard deviation to the realised
   one. Reported, not part of the verdict.

## Our hypothesis

H1: median M1 ≥ 1.0 — the network does not beat "tomorrow = today" on the very metric it is
advertised with. H2: the forecast echoes yesterday (second M2 correlation high) and carries no
information about tomorrow (first M2 interval includes 0). H3: M3 does not exceed the base rate.
H4: M4 interval includes or lies below zero.

## What would support the claim instead

Any **one** of these, in the fair arm (B), makes the verdict `PARTLY HOLDS` or `HOLDS`:

- median M1 < 0.95 **and** M1 < 1 in ≥ 80% of ticker-seeds;
- pooled M3 exceeds max(base rate, 50%) with the interval excluding it, **and** in ≥ 7 of 10 tickers;
- pooled M4 interval strictly above zero under `next_open`.

`DISPROVED` requires H1–H4 to hold in Arm A **and** none of the three conditions above to be met
in Arm B.

## Not claimed

Nothing here says machine learning cannot forecast anything in markets (volatility is
forecastable — P20). The test is of *this* recipe and its evidence standard. P01 already covers
gradient-boosted direction models.
