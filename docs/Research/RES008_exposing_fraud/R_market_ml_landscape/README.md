# R_market_ml_landscape — market-data ML sites, competitions & funds

Saiful's 2026-09-20 request: look at wundernn.io (a market-data ML site) and investigate the ideas
behind it, then widen the sweep to other market-analysis approaches not yet covered — either as
knowledge base or as a possibility of edge. Full comparative writeup:
`../03_market_ml_landscape_survey.md`. Tracker row: `TRACKER.md` B14.

**Different unit again, and a new grouping folder rather than continuing `R_oss_stack/`'s numbering.**
`R_oss_stack/` surveyed named GitHub repos; this folder surveys named sites/competitions/funds — a
different object entirely, so it gets its own self-contained `R01`–`R0N` numbering rather than
picking up at R09. None of these was tested (no code run, no `RESULTS.md`); each folder holds a
desk-review `VERDICT.md`.

| ID | Subject | Verdict |
|:--|:--|:--|
| R01 | Wunder Fund RNN Challenge (wundernn.io) | No measurable-edge claim — forecasting-accuracy recruiting contest, not a trading-edge claim |
| R02 | Numerai | Real, audited fund performance (25.45% net / 2.75 Sharpe, 2024) — not testable by our method, not a debunk candidate; the one counter-example that crowd-sourced ML *can* hold up |
| R03 | Jane Street / Optiver / Kaggle competitions | Same shape as R01 — no measurable-edge claim, recruiting/PR framing throughout |
| R04 | Academic LOB-forecasting literature | Not a claim to test — independently corroborates our own C01 finding: high forecast accuracy ≠ actionable trading signal |

Do not re-run this survey from scratch on a later visit — read the relevant `R##/VERDICT.md` first;
each one states exactly what would justify promoting it.
