# R04 — Academic limit-order-book forecasting literature

Surveyed 2026-09-20 as part of the broader market-ML sweep. Cross-reference:
`../../03_market_ml_landscape_survey.md`, `TRACKER.md` row B14.

## What it is

Not a single project — a body of published research (e.g. "Deep limit order book forecasting: a
microstructural guide," 2025–2026; the FI-2010 LOBFrame benchmark line of work) that trains deep
models to predict LOB mid-price movements and reports genuinely high forecasting accuracy (R²/
F1-style metrics) on historical exchange data.

## Our verdict

**NOT A CANDIDATE — but the single most useful piece of external validation found this sweep.** The
literature's own stated conclusion is exactly our C01 finding, independently arrived at: **high
forecasting power does not necessarily correspond to actionable trading signals.** Papers in this
line explicitly separate statistical forecast quality from tradeable-signal quality, and note that a
stock's own microstructure (tick size, liquidity, venue) governs whether any of that forecasting
power survives into an executable edge.

## Why this verdict, not a test

This is a literature review, not a claim with a name attached to falsify. There is nothing to
pre-register — it is context that corroborates a finding RES008 already produced independently (C01)
from a completely different angle (retail YouTube LSTM claim vs. institutional LOB deep learning
research). Two unrelated investigations landing on the same conclusion is worth citing, not testing.

## Revisit if

A specific paper's specific reported strategy (not just its forecasting accuracy) claims to beat
buy-and-hold or a placebo net of costs — that would be a new, nameable, testable claim. Nothing
found in this pass makes that claim; every source found stops at forecasting accuracy.

## Track record note (context only, not a verdict input)

Cite this literature directly in the R01 (Wunder Fund) verdict and in any future "prediction
accuracy ≠ trading edge" episode segment — it is a credible, non-retail, non-scammy source making
the exact point the C01 episode makes from data, which strengthens that episode's claim rather than
duplicating it.
