# R01 — Wunder Fund RNN Challenge (wundernn.io / wunder-challenge.io)

Surveyed 2026-09-20, at Saiful's request ("look at the market data machine learning site
wundernn.io and investigate the ideas that may have been used before"). Cross-reference:
`../../03_market_ml_landscape_survey.md`, `TRACKER.md` row B14.

## What it is

A recruiting competition run by Wunder Fund, a real, operating high-frequency trading firm (running
since 2014, on traditional and crypto markets). Not a product, not a claim aimed at retail — a
talent pipeline dressed as a Kaggle-style contest. Two generations exist:

- **Wunder Challenge (2025)**: predict two next-step price-movement targets from ~28 anonymized
  limit-order-book features (price/volume levels + trade prices/volumes), scored by a **weighted
  Pearson correlation** that emphasises large-amplitude targets, clipped to [-6, 6].
- **Wunder Fund RNN challenge (Sept 11 – Dec 1, 2026, current)**: predict the *entire* next market-
  state vector (~200 anonymized features spanning several interconnected instruments) from
  sequences of 20,000 states, scored by **mean R² across features**, cross-validated with sequence-
  grouped folds. Public leaderboard #1 sits at R²=0.3920; the finals winner scored 0.3964. Prize
  pool reported at $13,600 (per a YouTube recap of the competition, not independently confirmed on
  the site itself, which is a JS-rendered SPA that resists direct fetch).

## Our verdict

**NO MEASURABLE-EDGE CLAIM TO TEST — it is a forecasting-accuracy contest, not a trading-edge
claim.** Wunder Fund is not asserting "this beats the market"; it is scoring how well entrants
predict *next-tick feature values*, full stop. There is no backtest, no position sizing, no cost
model, no holding period, and no comparison to buy-and-hold or a placebo anywhere in the
competition's own framing. R²=0.39 on a next-market-state vector is a statement about curve-fit
quality on autocorrelated microstructure data, not a statement about P&L.

This is the same category error underlying our own **C01** (`NOT SUPPORTED`): a network can score
well on next-step prediction while still losing money after costs, because (a) most of that R² is
explained by trivial persistence (this tick looks like the last tick) rather than genuine signal,
and (b) even genuine short-horizon predictability at HFT tick-level requires colocated execution,
sub-millisecond latency and queue-position edge to monetize — none of which a Kaggle-style
leaderboard measures. Published 2025–2026 academic work on deep LOB forecasting makes exactly this
point explicitly: high forecasting power does not necessarily correspond to actionable trading
signals (see `../../03_market_ml_landscape_survey.md` for the citation).

## Why this verdict, not a test

- The data is proprietary and anonymized specifically to prevent reconstruction of Wunder Fund's
  actual instruments/venues — there is no way to independently rebuild the dataset to RES008's own
  pre-registration standard (fixed universe, real transaction costs, our own bootstrap intervals).
- Even with the data, R²-on-next-state is not a "measurable edge" as `PREREG_COMMON.md` defines it
  (beats a placebo or beats buy-and-hold, net of costs) — it is a different quantity entirely, one
  level upstream of any tradeable claim. Testing it would mean inventing an entire execution layer
  and cost model Wunder Fund never claimed, then testing *our own invention* — the C04/C05 mistake
  in reverse, same as the OSS-stack survey's infrastructure repos.
- The competition explicitly runs on data that "closely resembles" (not *is*) their production
  features — so even a leaderboard-topping model is once removed from anything real.

## Revisit if

- Wunder Fund (or any contestant) ever publishes an actual backtested/live P&L claim built on a
  winning model — that would be a new, testable claim, not this one.
- A future episode wants a "prediction accuracy ≠ trading edge" explainer segment — this is a clean,
  named, legitimate (non-scammy) example precisely because Wunder Fund never overclaims: it says
  "predict market states," not "predict profit." Good contrast case against the YouTube claims that
  do overclaim from far weaker footing (C01 in particular).

## Track record note (context only, not a verdict input)

Wunder Fund itself is a genuine, long-running HFT shop, not a claimed-but-unverifiable retail
product — nothing here reads as fraud or misrepresentation. The verdict is narrowly about whether
the *competition's own framing* hands RES008 a testable trading-edge claim, and it does not, by
design: Wunder Fund is buying talent, not selling a signal.
