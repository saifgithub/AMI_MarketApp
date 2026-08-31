# RES006 — Pre-registration

**Committed before any code ran.** Frozen 2026-08-31. Same data, windows, and bootstrap as
RES003/RES004.

## Two questions

Saiful: *"I know we do not do order flow in the app. But can we still run a benchmark and see
if there is an advantage. And see how we can identify bad trades and eliminate them."*

## What we are NOT testing

**This is not a test of order flow.** Order flow is footprint, delta and the bid-ask ladder at
tick resolution with trade-side classification. We have daily OHLCV. Any finding here is about
the *logic* Creamer applies — effort versus result — at a resolution roughly three orders of
magnitude coarser than the one he works at. A null here does not refute order flow, and a
positive here is not evidence that order flow works. Stated up front so no later reader
mistakes one for the other.

## H1 — does "effort without result" predict reversal?

His core perceptual claim [35:27]: *"watch effort versus result — who is being successful in
that effort in causing price progression and who is not."* Sellers press, fail to move price,
and get trapped.

Daily proxy, all from trailing 60-day medians so it is causal:

- `effort_t` = volume ÷ median volume
- `result_t` = |return| ÷ median |return|
- `absorption_t` = `effort_t / result_t` — high means heavy volume, little movement

A **down-absorption day** is `return < 0` **and** `absorption` in the top tercile.

> **The control does the work.** Down-absorption days are compared against **other down days
> that are not absorption**, not against all days. Comparing to all days would just re-measure
> the buy-the-dip effect. Matching on the sign of the move isolates the absorption signal.

Forward simple returns h ∈ {1, 3, 5}. Kill: interval includes zero.

## H2 — do market-state filters beat trading less?

Non-overlapping long SPY trades every h days, size 1.

| Arm | Rule |
|:--|:--|
| A | take everything |
| D | skip when volume is below its trailing 60-day median (his participation floor, [38:02]) |
| E | **placebo** — skip the same *number* of trades, chosen at random |

Kill: the D − E interval includes zero. E is what makes this a test: any filter improves things
if it merely removes trades, so the only question is whether *this* filter beats *any* filter
of the same frequency.

## H3 — do trader-state filters beat trading less? (predicted null, and that is the point)

| Arm | Rule |
|:--|:--|
| B | skip the next trade after k consecutive losing trades, k ∈ {2, 3} (his rule, [46:42]) |
| C | **placebo** — skip the same number of trades, at random |

**We predict B − C is zero.** Trade outcomes on a mechanical rule are close to independent, so
stopping after a losing streak cannot help a machine. Creamer's rule exists because *he*
degrades after losses, not because the market does.

**A null here is the informative result, not a failed test.** It would locate the entire value
of that rule in the trader's behaviour rather than in the market — which is precisely the case
for instrumenting decision quality (RES005) instead of adding a market filter. Reported either
way, with the interval, and a null distinguished from low power.

## Inference

Definition 2005–2018, holdout 2019–2026, one shot. Stationary block bootstrap, expected block
length 2h, 10,000 resamples, 95% intervals. No p-values. No Sharpe. Means reported with
intervals and flagged as imprecisely estimable (Lo 2002 / CR136).
