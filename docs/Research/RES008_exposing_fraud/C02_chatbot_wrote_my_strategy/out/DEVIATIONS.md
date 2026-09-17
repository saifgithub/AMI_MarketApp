# C02 — deviations from PREREGISTRATION.md

Written after 02_extract_and_gate.py and 03_score.py both ran to completion with an empty
`deviations` list (no code-block extraction failures, no static-safety exclusions, no
out-of-{-1,0,1} positions on any ticker, no strategy over the 20-minute wall-time threshold).
Nothing here changes a parameter, window, metric, or threshold from PREREGISTRATION.md /
PREREG_COMMON.md — these are records of literal readings taken where the spec left an
implementation detail unstated, per the task's instruction to record such readings here.

- **Truncation-test cut dates**: the spec says "5 cut dates spread through the sample" without
  naming them. Read literally as 5 dates evenly spread across the SPY history used for gating:
  the bars at the 20th/40th/60th/80th/95th percentile of index position (2009-05-01, 2013-08-29,
  2017-12-26, 2022-04-26, 2025-07-30).
- **Repair-round prompt**: sent to `common.ask_chatbot.ask(model_alias, prompt=...)` containing
  the original prompt text, the strategy's own previous code verbatim, the exact failure message
  (exception text or the look-ahead description), and the original interface instruction
  (`TO_CODE` from `01_generate_strategies.py`) verbatim, exactly as the task specified.
- **Placebo/bootstrap seeding**: PREREG_COMMON.md fixes seeds but does not name a scheme for
  giving each (strategy, ticker, window) cell its own reproducible seed. Used
  `PLACEBO_SEED (20260917) + sha256("strategy|ticker|WINDOW")[:8] as int % 10_000` — deterministic
  across runs (unlike Python's built-in `hash()` on strings, which is randomized per process and
  was caught and replaced before the scoring run, not after).
- **Out-of-{-1,0,1} position values on non-SPY tickers**: the look-ahead gate (SPY only, per the
  task) validates output range on SPY; scoring runs every strategy on every ticker in its
  universe, which the gate did not individually validate. `03_score.py` checks for this on every
  (strategy, ticker) pair and would have logged an entry here with the offending values had any
  appeared, clipping to [-1, 1] and rounding to the nearest of {-1, 0, 1} as the stated handling.
  None appeared in this run — every gated strategy also stayed within {-1, 0, 1} (up to NaN, which
  is coerced to 0 as pre-declared) on every U-EQ or U-CRYPTO ticker.
