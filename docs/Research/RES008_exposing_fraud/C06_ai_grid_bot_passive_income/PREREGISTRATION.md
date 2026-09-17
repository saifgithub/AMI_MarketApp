# C06 — "An AI grid bot earns passive income in any market" — PRE-REGISTRATION

Written 2026-09-17, before any C06 code exists. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

A bot labelled "AI" / "robotic" buys low and sells high automatically, profits whether the market
rises or falls, and produces steady hands-off income ("money printer", "while you sleep").
Landscape class L6 — 3 videos read, 0.92M views, dozens more in the search results (measured
2026-09-17). Where a mechanism is disclosed it is one of two: a **price grid**, or **adding to a
mean-reversion position at a volatility band with no stop**. One video shows the second kind
taking a live account from $3,000 to ~$115,000 and then to zero. Products with undisclosed logic
(landscape L15) cannot be tested and are not covered by this verdict.

## Mechanism 1 — spot grid (as the exchange tutorials describe it)

Range `[P0·(1−r), P0·(1+r)]` around the start price, arithmetic levels. Capital split equally per
level; at start the bot buys the inventory needed for the sell orders above price. A unit bought
at level *i* is sold at level *i+1*. Fee 10 bps per fill.

Grid: r ∈ {10%, 20%, 30%} × levels ∈ {10, 20, 50} = 9 settings. Horizon 90 days. Runs start every
7 days. Out-of-range: the bot simply stops trading and holds what it holds (what the exchanges do).

- **Hourly arm** (fill-accurate, ~730 days): BTC-USD, ETH-USD. Intrabar path assumed
  open → low → high → close on up bars, open → high → low → close on down bars.
- **Daily arm** (long history, includes 2018 and 2022): BTC-USD from 2014-09, ETH-USD from
  2017-11. Daily bars **undercount** grid fills, which understates grid profit; stated wherever
  this arm is quoted.

Also a **5× leveraged** version of each setting (the tutorial's own example): liquidation when the
mark-to-market loss reaches 1/5 of notional, less a 0.5% maintenance margin.

Measured per setting over all start dates: (a) **"grid profit"** — the sum of completed
buy-low/sell-high pairs, the number a bot dashboard displays; (b) **true P&L**, marking leftover
inventory to market; (c) true P&L minus buy-and-hold and minus cash; (d) share of runs that leave
the range; (e) for 5×: share of runs liquidated.

## Mechanism 2 — band grid with no stop (the blown account)

Bollinger(20, 2) on close. Sell one unit when close > upper band, buy one when close < lower band;
**add** a unit on each further close beyond the band at least 1 ATR(14) past the last add; close
the whole basket when price returns to the 20-bar mean. No stop. Two sizings, both disclosed as
our assumptions because the source does not give them: constant unit, and 1.5× martingale.

Instruments `U-FX`. Hourly (~730 days) and daily (2005-01 → 2026-08). FX cost 2 bps per side.
Unit notional per add ∈ {0.5×, 1×, 2×} of account equity (fixed at start). Runs start at the first
bar of every calendar quarter. **Ruin** = equity ≤ 20% of starting equity (a margin stop-out).

Measured: basket win rate; median monthly return while alive; time to ruin; share of start dates
ruined within 1, 3 and 5 years.

## Our hypothesis

H1 (grid): "grid profit" is positive in ≥ 95% of runs while true P&L is negative in ≥ 30% — the
dashboard number and the account diverge. H2 (grid): true P&L beats buy-and-hold in fewer than
half of runs in the daily arm. H3 (5× grid): ≥ 20% of 90-day runs are liquidated in the daily arm.
H4 (band): basket win rate ≥ 85%, **and** every sizing whose median monthly return is ≥ 3% is
ruined within 5 years from a majority of start dates.

## What would support the claim instead

- a grid setting with true P&L ≥ 0 in ≥ 90% of runs in the daily arm (which contains two bear
  markets) → `PARTLY HOLDS` for that setting;
- a band-grid sizing with median monthly return ≥ 3% and **zero** ruin across all start dates,
  2005–2026, net of costs → `HOLDS`.

## Not claimed

Grid trading is a legitimate way to be paid for providing liquidity in a range, and an honest
tutorial says exactly when it loses. The test is of "any market" and "passive income".
