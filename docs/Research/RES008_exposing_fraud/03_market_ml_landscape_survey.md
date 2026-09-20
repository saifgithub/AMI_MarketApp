# 03 — Market-data ML landscape: sites, competitions, and funds beyond our current claim set

Surveyed 2026-09-20, at Saiful's request: "look at the market data machine learning site wundernn.io
and investigate the ideas that may have been used before. The intention here is to also look at
other possible market analysis that we may not have covered either as knowledge base or as a
possibility of edge." Like `02_oss_stack_survey.md`, this is not a YouTube-claim survey — it covers
named sites, competitions, and one operating fund. Verdicts live one-per-item in
[`R_market_ml_landscape/`](R_market_ml_landscape/) (R01–R04); this file is the comparative writeup.

## What wundernn.io actually is

Not a product making a public trading claim — it's a **recruiting competition** run by Wunder Fund,
a real high-frequency trading firm operating since 2014. Two generations exist:

- **Wunder Challenge (2025)**: predict two next-step price-movement targets from ~28 anonymized LOB
  features, scored by weighted Pearson correlation.
- **Wunder Fund RNN challenge (Sept 11 – Dec 1, 2026, live now)**: predict the entire next
  market-state vector (~200 anonymized features across several interconnected instruments) from
  sequences of 20,000 states, scored by mean R² across features, cross-validated with
  sequence-grouped folds. Public leaderboard #1: R²=0.3920; finals winner: R²=0.3964. Multiple public
  GitHub attempts exist (transformer, GRU/LSTM, ensemble architectures), landing in the 0.25–0.40 R²
  band depending on approach and feature.

**What prior entrants actually tried** (from public repos): transformer-based sequence predictors
with multi-head attention and learned positional encoding (best found: mean R² 0.396); vanilla
GRU/LSTM baselines; ensembles. No approach in what we found reports beating the published
leaderboard ceiling by a wide margin — the task appears to be close to its practical predictability
limit around R² ≈ 0.40, consistent with heavy microstructure noise.

**The load-bearing point**: R² on next-tick features is a forecasting-accuracy metric, not a trading-
edge claim. Wunder Fund never asserts the winning model would make money — it's scoring raw
predictive fit on data that "closely resembles" (their words), not is, their production features.
There is no cost model, no position sizing, no holding period, no comparison to a placebo or
buy-and-hold anywhere in the competition's framing. Full reasoning: `R_market_ml_landscape/R01_wunder_fund_challenge/VERDICT.md`.

## The wider sweep

Saiful's ask had two parts — wundernn.io specifically, and "other possible market analysis... as
knowledge base or as a possibility of edge" more broadly. Three more items surfaced:

- **Numerai** ([R02](R_market_ml_landscape/R02_numerai/VERDICT.md)) — the one genuine outlier. A
  crowd-sourced quant fund that blends thousands of submitted models into a live "Meta Model"
  driving real, audited trading: reported 2024 net return 25.45% at a 2.75 Sharpe, JPMorgan capacity
  up to $500M, AUM grown from ~$60M to ~$550M over three years. This is not testable by our method
  (the edge is Numerai's undisclosed proprietary blend, not a public recipe) and it is not debunk
  fodder — it is the strongest evidence found anywhere in this project that "ML finds a market edge"
  can hold up under years of live, real-money, institutionally-vetted operation. Worth remembering as
  a calibration point against everything else the series has tested.
- **Jane Street / Optiver / Kaggle competitions**
  ([R03](R_market_ml_landscape/R03_recruiting_competitions/VERDICT.md)) — same shape as Wunder
  Fund's challenge: prediction-accuracy contests run by real trading firms as recruiting/PR, no
  trading-edge claim made anywhere in their framing.
- **Academic LOB-forecasting literature**
  ([R04](R_market_ml_landscape/R04_lob_forecasting_literature/VERDICT.md)) — not a claim to test, but
  useful corroboration: recent (2025–2026) published research states directly that high LOB
  forecasting power "does not necessarily correspond to actionable trading signals" — the same
  conclusion our own C01 test reached independently, from a completely different angle (a retail
  YouTube LSTM claim vs. institutional deep-learning research on real exchange data).

## What this means for RES008

None of the four is being promoted to `C##` — none hands us a public, reproducible recipe with a
stated P&L claim to pre-register (`PREREG_COMMON.md`'s bar). Logged as backlog (`B14` in
`TRACKER.md`), with individual `VERDICT.md` files under `R_market_ml_landscape/` for later revisit.

The more useful output of this pass is a **calibration point**, not a new test candidate: Numerai
shows the "measurable edge" bar this series applies is achievable, and the LOB literature
independently confirms our C01 finding that forecast accuracy and trading edge are different
things measured on different axes. Both are worth a line in future episodes as fairness/context —
the series debunks specific overclaimed recipes, not the idea that any ML-market approach could ever
work.

## Provenance note

Wunder Fund, Numerai, Jane Street, Optiver, and Kaggle are all named directly — same reasoning as
`02_oss_stack_survey.md`'s provenance note: these are named public projects/competitions/firms being
evaluated on their own claims, not YouTube creators. No `_internal/` entry needed, no scrub concern
beyond the usual "Saiful" decision-owner attribution flag.
