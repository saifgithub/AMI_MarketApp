# C07 -- deviations and ambiguity resolutions

None of these change a parameter, universe, window, metric or threshold
fixed by `PREREGISTRATION.md` or `PREREG_COMMON.md`. Each is a literal
reading chosen where the prereg text did not fully specify a mechanical
detail, recorded here per the run instructions.

1. **"Part 1 RSI rule run as a 22-ticker equal-weight portfolio of its
   per-ticker daily net returns" -- which window(s).** The prereg does not
   say whether this comparator uses DEFINE, HOLDOUT, or both. Part 2's own
   bot simulation spans 2005-01-03 -> 2026-08-31, so the literal match is
   the CONCATENATION of Part 1's DEFINE (2005-2018) and HOLDOUT (2019-2026)
   daily net-return series per ticker, giving one continuous 2005-2026
   series per ticker before equal-weighting. This is what
   `run_part1.py::_save_full_window_returns` writes to
   `out/rsi_rule_daily_net_returns_full_window.csv` and what
   `run_part2.py::load_rsi_rule_portfolio_returns` equal-weights (simple
   mean across the 22 tickers each day, i.e. a daily-rebalanced
   equal-weight combination of net returns, not of prices).

2. **Zero-skill bot equity sizing: "each position 1/3 of equity" -- of what
   equity, measured when.** Read as 1/3 of the bot's CURRENT total equity
   at the moment each position opens (not a fixed fraction of initial
   capital), since positions open and close repeatedly across a 21-year
   run and a fixed-initial-capital reading would let committed notional
   drift arbitrarily far from actual equity. See `zero_skill_bot.py` docstring.

3. **Zero-skill bot slot-refill timing.** The prereg does not spell out
   whether a slot freed by an exit at close(t) can be refilled at that same
   bar. Read literally from "exit at the close of the last held day" and "a
   new position opened at a bar's open": a position with holding period h
   opened at open(t) is held through bars t..t+h-1 and exits at
   close(t+h-1); the slot is free starting bar t+h, so the earliest a new
   position can open there is open(t+h) -- an exit's close and the next
   entry's open never coincide on the same bar for the same slot.

4. **Trending-basket composition before TSLA lists (2010-06-29).** The
   prereg's "equal-weight buy-and-hold basket of the 10 names" pre-dates
   TSLA's listing for part of the 2005-2026 window. Read literally
   alongside "TSLA joins when it lists" (stated for the bot universe): the
   basket is the equal-weight (nanmean) of whichever of the 10 names are
   listed on a given bar -- 9 names before 2010-06-29, 10 after.

5. **Trending-month trade attribution.** "The zero-skill bot's trade win
   rate for trades opened inside such [trending] windows" is read as: a
   trade's OWN entry bar must fall inside a 21-day window whose own
   trailing-forward return (that window's bars only) was >= 8%. A trade
   opened just before a trending window starts, or one that extends past
   the window's end, is attributed by its entry bar alone, per the prereg's
   "opened inside" wording -- not by any overlap test with the window's
   full span.

6. **Trending-month conditional win rate: full 2,000-bot replay, not a
   subsample.** `run_part2.py::trending_month_analysis` re-runs all 2,000
   bots (same seeds as the headline `simulate_bots` run) through an
   unvectorised, trade-logging loop to attribute each trade's entry bar to
   a trending/non-trending window. This is slower than the vectorised
   headline run (no numpy vectorisation across bots) but was measured at
   full scale (see wall-time note below) and stayed within "keep the run
   to minutes", so no bot-count reduction was needed.

7. **Sample-size arithmetic mu convention.** PREREGISTRATION.md gives
   "mu = 5%/52 (or /12)"; this is read as 5 PERCENTAGE POINTS of annual
   excess return divided by periods per year (0.05/52 per week,
   0.05/12 per month), matching "a genuine +5 points-per-year edge" in the
   Our-hypothesis section, not 5% of some baseline return.

8. **`out/results.json` split into `results_part1.json` + `results_part2.json`.**
   The run instructions name a single `out/results.json`; Part 1 (22
   tickers x 3 windows, with 500-rep placebos per ticker-window) and Part 2
   (2,000 bots x 2 rolling-window granularities) are independent runs with
   very different wall times (Part 1 ~13 min, Part 2 ~12 min) and Part 2
   consumes one of Part 1's outputs (the equal-weight RSI portfolio
   comparator) — keeping them as two files let Part 2 be re-run without
   re-running Part 1, and let each be validated independently before the
   next stage started. Every number in `out/summary.txt` traces to one of
   these two files; nothing is invented or recomputed for the summary.
