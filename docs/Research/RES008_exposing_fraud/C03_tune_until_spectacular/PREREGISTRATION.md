# C03 — "Keep tweaking until the backtest is spectacular" — PRE-REGISTRATION

Written 2026-09-17, before any C03 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

Start from a public trend-following script, add filters with a chatbot's help, adjust thresholds,
filter lengths and position size while watching the equity curve, add 10× margin, and arrive at a
headline such as "$1,000 into $17.4M". Variants of the same move: a paid "AI" toolkit whose exit
thresholds were optimised on the same two years its 74% win rate is quoted from; a chatbot-coded
prop-firm bot judged on 7–12 trades as four filters are stacked one by one. Landscape class L3.

The claim under test is the *procedure*: **choosing the best configuration on a window tells you
something about how it will do next.**

## Design

### Part 1 — selection on the tuning window

Strategy family (the one shown): SuperTrend long-only with optional RSI and ADX entry filters.
Grid fixed now — 420 configurations:

- SuperTrend ATR period ∈ {7, 10, 14, 21} × multiplier ∈ {2, 3, 4}
- RSI filter: none, or length ∈ {14, 28} × enter only if RSI > {40, 50, 60}
- ADX filter: none, or length ∈ {7, 14} × enter only if ADX > {20, 30}

Instruments: BTC-USD (as shown) with tuning window 2014-09-17 → 2020-12-31 and holdout
2021-01-01 → 2026-08-31; plus every `U-EQ` ticker with `DEFINE` / `HOLDOUT`. 23 instruments.
Unlevered, `next_open`, common costs.

For each instrument: rank all 420 by tuning-window net total return, take the winner — exactly
what is done on camera — then measure:

- **T1** the winner's **holdout percentile** among the same 420 (50 = selection told you nothing);
- **T2** Spearman rank correlation, tuning-window vs holdout return, across the 420;
- **T3** winner's holdout net return minus buy-and-hold;
- **T4** shrinkage: winner's tuning-window return vs its own holdout return (per year of window,
  labelled as such, both windows > 3 years).

### Part 2 — what the best of 420 coin-flippers looks like

On each instrument's tuning window, 420 random long/flat strategies with exposure and trade count
matched to the grid's medians. Compare the best random strategy's tuning-window return with the
tuned winner's. Reported; illustrates selection, not part of the verdict.

### Part 3 — the leverage nobody liquidates

The tuned BTC winner at 10× margin. Count position-days on which the bar's low is ≥ 10% below the
entry price (or the prior close, once marked to market daily) — a full loss of margin. Report
(a) the as-shown compounded return, which ignores liquidation, as the strategy tester does, and
(b) the same path with the account ending at the first liquidation.

## Our hypothesis

H1: mean T1 across the 23 instruments is below 65, interval (bootstrap over instruments)
including 50. H2: T3 < 0 for the majority of instruments. H3: the 10× BTC winner is liquidated at
least once inside its own tuning window.

## What would support the claim instead

- mean T1 ≥ 75 with the interval excluding 50, **and** T3 > 0 in the majority of instruments →
  picking the best backtest does carry forward; `HOLDS`.
- The 10× path is never liquidated in either window → the leverage point is dropped from the episode.

## Not claimed

Not that trend following is worthless, nor that parameter search is never legitimate. Walk-forward
selection with a holdout is ordinary practice. The test is of selection **without** one.
