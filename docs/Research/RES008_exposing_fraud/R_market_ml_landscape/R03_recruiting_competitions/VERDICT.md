# R03 — Recruiting-style prediction competitions (Jane Street, Optiver, Kaggle)

Surveyed 2026-09-20 as part of the broader market-ML sweep. Cross-reference:
`../../03_market_ml_landscape_survey.md`, `TRACKER.md` row B14.

## What it is

The same object class as Wunder Fund's challenge (R01), run by other trading firms:

- **Jane Street** — "Real-Time Market Data Forecasting" and earlier "Market Prediction" competitions
  on Kaggle (up to $100k prize pools); separately, "ETC" — an invitation-based, campus-recruiting
  weekend event where teams build bots that trade on a Jane-Street-built simulated exchange.
- **Optiver** — "Realized Volatility Prediction" and "Trading at the Close" on Kaggle; "Ready Trader
  Go," an intermittent algorithmic market-making competition.
- Kaggle itself functions as neutral host/platform across all of these.

## Our verdict

**NO MEASURABLE-EDGE CLAIM TO TEST — same shape as R01, plural instances of it.** None of these
firms claims a trading edge through the competition; they are scored on prediction-accuracy metrics
(volatility RMSE, price-direction accuracy, etc.) against historical data, explicitly framed as
recruiting/PR exercises, and none publishes or implies "this wins money." Optiver and Jane Street
are running firms trading their own capital; the public competitions are talent funnels, not signal
sources.

## Why this verdict, not a test

Identical reasoning to R01: prediction-accuracy metrics on historical data are not a "measurable
edge" as `PREREG_COMMON.md` defines it, no execution/cost model exists in any of these competitions,
and the underlying data is either proprietary/anonymized or, where public (Kaggle datasets), was
never claimed by the host firm to be tradeable as scored.

## Revisit if

Grouping these under one verdict rather than writing R01-style detail per firm is a deliberate
economy — the pattern is identical across all of them. Worth expanding into its own entry only if a
specific competition's winning solution gets repackaged elsewhere as a standalone trading-strategy
claim (that repackaging would be the new, testable thing — not the competition itself).

## Track record note (context only, not a verdict input)

Numerai (R02) is the one member of this broader landscape that breaks the pattern — it turns
crowd predictions into an actual traded, audited fund. Worth remembering the contrast: the
*presence* of a live fund wrapped around the predictions is what makes Numerai different in kind
from Wunder Fund, Jane Street, Optiver and Kaggle, not just different in degree.
