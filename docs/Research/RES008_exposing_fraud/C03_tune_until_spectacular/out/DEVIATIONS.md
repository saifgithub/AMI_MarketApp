# C03 deviations and operationalisations

Recorded before results were inspected, per `PREREG_COMMON.md`'s deviation rule: nothing in
`PREREGISTRATION.md` was changed; anything infeasible or ambiguous is resolved here to the most
literal reading and carried through.

## 1. Entry-filter operationalisation (spec explicitly asks for this to be stated)

The source video does not specify how RSI/ADX filters interact with SuperTrend's trend state once
a position is already open, or what happens if a filter fails exactly at the flip-up bar. Reading
adopted: position = 1 while SuperTrend is in an uptrend, 0 otherwise. On a flat-to-long transition
(SuperTrend flips up), each enabled filter (RSI > threshold, ADX > threshold) must pass **on that
bar** for the entry to be taken; if a filter fails at the flip-up bar, no position is taken yet, and
the strategy re-checks the same filters on every subsequent bar of the *same* uptrend run, entering
on the first bar where they all pass. Once long, the position is held until SuperTrend flips down
regardless of what the filters do afterward -- filters gate entry only, never exit. If the filters
never pass before the uptrend ends, that uptrend run produces no trade. Implemented in
`code/strategy.py::compute_target_position`.

## 2. Wilder RMA seeding bug found and fixed during indicator construction

`code/indicators.py::_wilder_rma`'s first draft seeded the running average with a plain mean of the
first `period` raw values. Both RSI's day-1 diff (`close.diff()`, NaN at bar 0) and ADX's `dx`
series (NaN during its own upstream `+DI`/`-DI` warmup) start with a leading run of NaN; a plain
`numpy` mean over a window containing any NaN is NaN, and that NaN then propagated through every
subsequent bar via the recurrence, permanently. Fixed by (a) treating RSI's bar-0 gain/loss as 0
(no prior bar to diff against, matching ATR's existing bar-0 convention already in the file) and
(b) making `_wilder_rma` seed from the first `period` *consecutive non-NaN* values rather than
positionally the first `period` values, wherever they start -- still purely a function of history up
to and including the seed bar, so causality (the truncation test) is unaffected. Caught by
`test_indicators.py::test_rsi_strictly_rising_is_100` failing and a manual ADX warmup check; not a
deviation from the spec, but recorded here since it was a real defect in the indicator math, not
just a style choice.

## 3. Part 2 random-strategy construction is C03-local, not `common.placebo`

`common/placebo.py::matched_random_entries` matches an existing trade list's exact per-trade
holding-period multiset. Part 1's spec instead asks Part 2's 420 random strategies to match the
**grid's medians** (median trade count, median exposure) on that instrument's tuning window -- there
is no single "real" trade list to match against. Built a small dedicated generator,
`code/random_strategy.py`, reusing the same non-overlapping-random-placement idea as
`common.placebo` (uniform placement, retry on packing failure) but drawing `median_trades` spell
lengths via a random composition of `round(median_exposure * window_length)` total in-market bars,
per the spec's literal wording ("random non-overlapping long spells ... spell lengths drawn by a
random composition, placement uniform"). This does not touch `common/`.

## 4. BTC has no pre-window warmup history

The no-look-ahead rule requires indicators to be warmed up on data before the window starts "where
history exists." BTC-USD's first available bar (2014-09-17) *is* the tuning window's first day, so
there is no pre-window history to warm up on for BTC specifically -- this is a data-availability
fact, not a choice, and BTC's first few tuning-window bars carry the same ATR/RSI/ADX ramp-up any
fresh series would. Every U-EQ ticker has at least one full year of pre-2005 daily history loaded
(from 2000-01-01, or the ticker's own IPO date if later) specifically so its indicators are warmed
up before its 2005-01-01 tuning window starts.

## 5. T4 "per year of window" denominator

The spec defines T4 as "winner's tuning-window return vs its own holdout return (per year of
window, labelled as such, both windows > 3 years)" without a formula. Read literally as: divide
each window's net total return by that window's length in years (`window_days / 365.25`), reported
as `tune_return_per_year` and `holdout_return_per_year` in `results.json`, both windows confirmed
> 3 years for every instrument before this ratio is used (14.0y / 7.7y for U-EQ, 6.3y / 5.7y for
BTC). This is a simple linear per-year rate, not an annualised/compounded CAGR -- the spec's house
rule elsewhere bars annualising short windows via compounding, and a plain per-year division is the
most literal reading of "per year of window" that avoids that machinery.

## 6. Liquidation reference price on the entry bar vs subsequent bars

The spec's liquidation rule: "a bar whose LOW is >= 10% below the prior close (or below the entry
open on the entry bar) wipes the margin." Implemented literally: on the first bar a position turns
long (entry bar), the reference price is that bar's own open; on every subsequent bar the position
stays long, the reference is the *previous* bar's close (marked to market daily, as the spec's Part
3 preamble states). A position that is already long going into a window's first bar (i.e. would have
opened before the window if this were a mid-run slice) is treated the same as any other bar with a
prior position: reference = previous close -- this only matters at a window boundary and did not
arise for the BTC winner in either window (checked in `results.json`).

## 7. Part 3's "count position-days" vs the design's own liquidation description

The **Design** section's Part 3 paragraph says "count position-days on which the bar's low is >=
10% below the entry price (or the prior close, once marked to market daily)"; the **What would
support the claim** section instead says "a bar whose low is >= 10% below the prior close (or below
the entry open on the entry bar)." These two phrasings differ (entry price vs entry open on the
entry bar) only in wording, not substance, for a long-only next-open strategy -- the entry bar's
"entry price" *is* that bar's open (see `common/backtest.py`'s `next_open` convention: the position
decided at the prior close is filled at this bar's open). Read as the same rule; implemented per
deviation #6 above using the second section's wording since it is the more operational of the two.

## 8. [Post-run finding, not a design deviation] "As-shown" 10x equity goes negative, not just small

The as-shown series is computed exactly as specified -- `cumprod(1 + 10 * daily_net_return)` with
no floor, per "the as-shown compounded return, which ignores liquidation, as the strategy tester
does." Once any single bar's leveraged return is worse than -100% (a 10x position against a >=10%
adverse daily move), that bar's multiplicative factor `(1 + 10*r)` goes negative, and the running
product can itself go negative or oscillate in sign for the remainder of the window (measured:
tuning-window as-shown equity's minimum value is -0.0212; 925 of the tuning window's bars and 1,778
of the holdout window's bars carry a non-positive as-shown equity value). This is a real, expected
consequence of the literal "no liquidation floor" definition, not a bug -- a naive strategy tester
that truly ignores liquidation produces exactly this nonsensical negative-equity output, which is
itself part of what the leverage claim glosses over. Two consequences for reading the numbers:
(a) `as_shown_net_return` for the 10x case is reported as essentially -1.0000 in both windows, but
that number understates how broken the underlying path is -- the equity multiple does not decay
monotonically to zero, it crosses zero and keeps compounding through negative territory; (b) the
`leverage_10x_BTC.png` log-scale plot cannot render non-positive values, so matplotlib silently
omits every non-positive bar, leaving visual gaps that make the as-shown curve look like it recovers
to small-but-positive levels between liquidation-scale events rather than showing the negative
excursions in between. The underlying values are in `out/results.json`
(`part3_btc_leverage.<window>.leverage_10x.as_shown_equity_curve`) for anyone who wants the full
signed path; the figure is a visualisation aid, not the source of record.
