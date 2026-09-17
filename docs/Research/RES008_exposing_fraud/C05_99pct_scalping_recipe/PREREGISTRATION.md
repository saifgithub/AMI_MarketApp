# C05 — The "99% win rate" scalping recipe — PRE-REGISTRATION

Written 2026-09-17, before any C05 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

An ATR-trailing-stop alert indicator ("UT Bot" family) confirmed by a Schaff Trend Cycle (STC)
oscillator, with a fixed R-multiple target, wins 80% of the time alone and 90–99% with the
confirmation. Landscape class L5 — 2 videos read, 2.17M views (measured 2026-09-17); the larger
one is the single most-viewed video in the whole survey. Neither indicator involves any machine
learning; both rank on "AI indicator" searches. Evidence shown: two hand-picked chart examples in
one; in the other, 100 manual setups that came out at **55%**, against its own 99% title.

## Recipe reproduced

**UT Bot** (standard public formula): `nLoss = key × ATR(period)`, ratcheting trailing stop on
close; buy when close crosses above the stop, sell when it crosses below.

**STC** (the common public script): `macd = EMA(close, fast) − EMA(close, slow)`; stochastic of
`macd` over `length`, smoothed by factor 0.5; stochastic of that again over `length`, smoothed by
0.5. "Green" = rising, "red" = falling.

| | V1 (as one video sets it) | V2 (as the other sets it) |
|:--|:--|:--|
| UT Bot | key 2, ATR 6, both sides | buy instance key 2 / ATR 1; sell instance key 2 / ATR 300 |
| STC | length 80, fast 27, slow 50 | length 80, fast 27, slow 50 |
| Target | 1.5 R | 2 R |

Entry filter, two readings, because the videos describe it loosely — both pre-registered:
**R-strict** long only if STC is rising **and** below 25 (short: falling and above 75);
**R-loose** long if STC is rising (short if falling).

Stop = "recent swing low/high". **Our operationalisation, disclosed:** lowest low (highest high)
of the 10 bars up to and including the signal bar. 1 R = entry − stop. Entry at next bar's open;
one position at a time; no time exit other than 200 bars.

## Data and cells

Instruments: BTC-USD, ETH-USD, SPY, QQQ, AAPL, NVDA, TSLA.
Timeframes: **60-minute (~730 days) = primary**; 5-minute (~60 days) = as taught but short;
daily (full history) = long-history check. 2 variants × 2 readings × 3 timeframes = 12 cells,
each pooled across the 7 instruments. Common costs; gross also reported — on 5-minute bars costs
are a large fraction of 1 R, and that is part of the finding, so it is shown separately.

## Measurements

Per cell: trades, win rate (Wilson), expectancy in R net and gross (bootstrap over trades in time
order), and the **placebo**: random entries with the same side mix, the same 10-bar stop rule and
the same R target, 500 replications → where the recipe's win rate and net expectancy fall in that
distribution.

## Our hypothesis

H1: win rate below 60% in all 12 cells. H2: win rate inside the placebo's central 90% in at least
9 of 12 cells — the recipe's win rate is what its target-to-stop geometry gives any entry.
H3: net expectancy not above the placebo's 95th percentile in the primary cells.

## What would support the claim instead

- win rate ≥ 80% in any primary (60-minute) cell → the headline claim `HOLDS`;
- or net expectancy above the placebo's 95th percentile in ≥ 3 of the 4 primary cells **and** in
  the matching daily cells → `PARTLY HOLDS` (a real entry signal, not a 99% one). The 55% at 1.5 R
  that one video measured by hand would, if real, be a substantial edge; this condition is how we
  would find out.

## Not claimed

The 5-minute history available to us is two months. A null there is weak on its own; the verdict
rests on the 60-minute and daily cells, and the results say so.
