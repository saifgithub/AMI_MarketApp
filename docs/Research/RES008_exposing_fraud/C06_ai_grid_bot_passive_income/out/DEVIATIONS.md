# C06 — deviations and disclosed assumptions

Recorded before results were inspected, per the task's hard rules: nothing here changes a
parameter, instrument, window, metric or threshold in PREREGISTRATION.md — each entry is a
literal-reading choice the spec's prose left to implementation, made once and carried through.

## Mechanism 1 (grid_sim.py)

1. **"levels" = number of grid LINES, not intervals.** `levels ∈ {10,20,50}` is read as the count
   of arithmetic price lines across `[P0(1-r), P0(1+r)]`, giving `levels-1` order slots — the
   standard exchange-tutorial phrasing ("50 grids" ⇒ 49 profit-taking trades per full traversal).
   `step = (high-low)/(levels-1)`.
2. **"Equal quote capital per level" = a fixed quote amount per slot, not a fixed base quantity.**
   `Q = capital / (levels-1)` quote units per slot, held fixed at that slot's original allocation.
   Base quantity at a line therefore differs slightly line to line (`Q / line_price`). This is the
   exchange-default "equal investment per grid" mode; equal-base-quantity is a separately-labelled
   alternative the spec does not ask for.
3. **Initial inventory sizing.** For every slot `i` whose sell line (`lines[i+1]`) is above P0, the
   bot pre-buys `Q / lines[i+1]` base units at P0 (summed across such slots, one fee on the total).
   This sizes the pre-bought inventory at the price it will later sell at, so filling that sell
   releases exactly `Q` of quote — the grid is self-financing under this reading, which is the only
   reading under which "grid profit" per completed pair reduces to `qty*(P_sell-P_buy) - fees`
   without additional bookkeeping the spec doesn't describe.
4. **Quantity conservation buy-to-sell.** A resting buy at line `i`, when filled, buys
   `qty = Q / lines[i]` base units; that exact same `qty` (not re-sized to the sell line's price)
   rests as the sell at line `i+1`. You can only sell what you bought.
5. **5x liquidation "worst point of each bar's assumed path"** is read as the bar's `low` for the
   long/flat spot book the grid always holds (grid inventory is never net short), regardless of
   whether the bar is classified up or down for the O→L→H→C / O→H→L→C path-order rule (that rule
   governs level-crossing order within the bar, not which extreme is worst for a long book).
6. **Buy-and-hold placebo bought "at P0"** uses the run's own P0 (first bar's open, per below) as
   the entry price, one 10 bps fee, consistent with "buy-and-hold of the same starting capital
   bought at P0" in PREREGISTRATION.md.
7. **P0 = the run's first bar's `open`.** The spec calls P0 "the start price" without specifying
   open vs. close of the start bar; `open` is used since it is the first tradable price of the run
   and PREREG_COMMON's own default execution convention ties actions to bar opens.

## Mechanism 2 (band_grid_sim.py)

8. **ATR(14) = simple (unweighted) rolling mean of True Range over 14 bars**, not Wilder's
   exponential smoothing. "ATR(14)" names a 14-bar average without specifying the smoothing method;
   the simple rolling mean is the more literal reading of "a 14-bar average."
9. **Signal timing: computed on bar t's close, filled at bar t+1's open** — PREREG_COMMON.md's house
   default execution convention (`next_open`), applied because Mechanism 2's own description ties
   actions to closes ("sell one unit when close > upper band...") without stating a fill timing.
10. **Unit notional per add is a fraction of STARTING equity, fixed for the life of the run** (not
    marked to current equity), per the spec's own words: "fixed at start."
11. **Martingale sizing multiplies by 1.5^k where k is the 0-indexed add number within the current
    basket** (k=0 for the basket's first unit, k=1 for the first add, etc.), consistent with
    "1.5× martingale" describing the ratio between successive adds.
12. **"At least 1 ATR(14) past the last add price"** is read as the ATR(14) value at the CURRENT
    bar's signal (close), compared against the absolute distance from the current close to the
    price of the basket's most recent add (not the basket's first entry).
13. **Ruin check uses the bar's worst point for the currently-open basket's side** (low for a long
    basket, high for a short basket) marked against quote-cash-plus-unrealized-P&L, in addition to
    the close-of-bar mark used for the equity curve and monthly-return reporting — per the task's
    "equity marked at each bar's close AND at the bar's worst point for the ruin check."
14. **FX cost (2 bps per side)** is charged on the notional of each add (at the add's fill price)
    and on the notional of the whole basket at the close fill (at the close fill's price) — "per
    side" read as per position-change event (open an add / close the basket), matching
    PREREG_COMMON's "charged on every position change" cost convention.

## run_c06.py

15. **90-day horizon = 90 calendar days**, matching the spec's explicit "90-day horizon (90
    calendar days)"; grid runs are sliced by calendar-day boundaries on each arm's native bar
    spacing (hourly bars within the 90-day window, daily bars within the 90-day window).
16. **Band grid "share of start dates ruined within N years"** denominators only count start dates
    that have at least `N*365` calendar days of data remaining after them, per the spec's own
    instruction to report denominators for exactly this reason.
17. **Band grid "median monthly return while alive"** is defined and stated in `out/summary.txt`
    and `results.json` as: the median, over calendar months, of each run's month-end-equity over
    prior-month-end-equity minus 1, pooled across every run of that setting, using only months
    observed before that run's ruin (if any).
18. **U-FX for the band grid arm is all three PREREG_COMMON `U-FX` members** (EURUSD=X, GBPUSD=X,
    USDJPY=X); the spec's figure instruction singles out EURUSD only for `band_grid_equity.png`,
    not for the measured statistics.
