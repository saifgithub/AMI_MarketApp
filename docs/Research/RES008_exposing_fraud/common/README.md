# `common/` — RES008 shared research library

Small, correct, well-tested primitives that every claim folder (`C##_<slug>/`) builds
on. Every verdict in the public research programme rests on this code, so correctness
— especially no look-ahead — matters far more than features. If you find yourself
wanting a new feature here for one claim, prefer to build it in that claim's `code/`
first; only promote it here once a second claim needs it too.

## What each module guarantees

### `data.py`
- `load_daily(tickers, start, end=None)` and `load_intraday(ticker, interval)` return
  OHLCV bars that are **split-and-dividend adjusted on a total-return basis**: raw
  open/high/low/close are each multiplied by that row's `adj_close / close` ratio, not
  just `Adj Close` alone. This matters for anything range- or gap-based (`run_brackets`)
  — if only the close were adjusted, a strategy reading high/low around a split or
  ex-dividend date would see stale, pre-adjustment levels.
- Rows with NaN or non-positive O/H/L/C are dropped. A ticker returning no data raises
  `ValueError` — it never silently hands back an empty frame.
- Downloads are cached to CSV in `common/cache/` (git-ignored) with a sidecar `.meta`
  file recording the download date. A cached range is reused when it already covers
  the request; otherwise a fresh `yfinance.download()` is issued and re-cached.
- `load_intraday` supports `60m` (yfinance's ~730-day window) and `5m` (~60-day
  window) only, cached the same way.

### `backtest.py`
- `run_positions(bars, target_position, cost_bps, execution)` — the general-purpose
  engine. `target_position[t]` must be decided from information available at the
  **close of bar t**; the function does not shift it for you. Two execution modes:
  - `next_open` (default): the change decided at close(t) fills at open(t+1). See the
    timeline diagram below.
  - `same_close`: decided and filled at close(t) itself — reproduces what most
    tutorials implicitly assume (instant, free-of-slippage fills at the signal bar's
    close). Needed to run an "as taught" arm honestly, not because it is a
    recommended convention.
  - Costs are `cost_bps` per unit of **absolute position change**, charged on the
    execution bar. A flat→long round trip pays cost twice (once each way); a
    +1→−1 flip pays 2× on the single flip bar.
  - Returns a `BacktestResult`: `daily_returns` (net), `gross_daily_returns`,
    `positions_held`, `trades` (one row per maximal same-sign run), and `.summary()`
    — total_return, buy_hold_return, n_trades, win_rate, avg_win, avg_loss,
    payoff_ratio, profit_factor, expectancy_per_trade, max_drawdown, exposure.
    **No Sharpe ratio anywhere** — deliberate house rule (see repo README, Method
    standard #5): mean daily returns are not reliably estimable at backtest sample
    sizes, and a Sharpe number invites exactly the false precision this programme
    exists to debunk.
- `run_brackets(bars, entries, take_profit_pct, stop_loss_pct, max_bars, cost_bps, side)`
  — fixed TP/SL bracket engine. Entry fills at the open of the bar *after* a signal.
  Exit is evaluated bar-by-bar against high/low:
  - **If both TP and SL fall inside the same bar's [low, high] range, the STOP is
    assumed to trigger first.** This is a conservative assumption, not a measured
    fact — daily/intraday OHLC alone cannot tell you the true intrabar path, and
    assuming the friendlier order would flatter every strategy tested here.
  - A gap that opens through the stop level fills at that bar's open price (worse
    than the nominal stop), not at the stop price itself.
  - No exit within `max_bars` closes the position at that bar's close (`time_exit`).
  - One position at a time — entry signals arriving while a position is open are
    ignored.

Trade-table accounting (`.trades`, both engines): a "trade" is a maximal run of one
sign in the realised position series. Its **economic** entry/exit bars are NOT
necessarily the run's own first/last bar — see "Trade-return convention" below. Every
trade's `gross_return` replays that trade's own per-bar legs exactly as the daily
engine computed them (not a shortcut from entry/exit price alone), because a constant
**short** position does not compound to a simple `-(exit/entry - 1)` — see the same
section. `net_return` subtracts `cost_rate` once for opening and once for closing (a
flip closes one trade and opens another on the same bar, so each carries its own 1 +
1 units of cost), except when the run reaches the last bar, where there is no exit
bar left to charge a cost on.

### `placebo.py`

- `matched_random_entries(bars, trades, n_reps, cost_bps, seed, execution="next_open")`
  — for each replication, draws the same **count**, same **sides**, and same
  **holding-period multiset** as the real `trades`, placed at uniformly random
  non-overlapping start bars, priced under the SAME `execution` convention as the real
  trades (see "Trade-return convention" below), filled and costed the same way.
  Returns per-replication `total_returns` and `mean_trade_returns`. This is the
  control for `run_positions`-style trades: if a signal cannot beat this distribution,
  its edge is coming from trade geometry (side, holding period, cost drag), not from
  timing. Matching the execution convention matters: a `next_open` trade earns an
  overnight leg (close(t) -> open(t+1)) that carries real drift for equities: pricing
  the control as if it always exited at that day's close would silently exclude that
  leg and bias the comparison.
- `matched_random_brackets(bars, n_trades, take_profit_pct, stop_loss_pct, max_bars,
  cost_bps, side, n_reps, seed)` — draws `n_trades` random entry dates and runs them
  through the *same* `run_brackets` engine with the *same* geometry, showing what a
  TP/SL/max_bars shape produces with zero signal. Unlike `matched_random_entries`,
  this matches geometry and **approximate** count only, not an exact holding-period
  multiset — bracket exits are path-dependent (TP/SL/time), so there is no fixed
  holding period to match against, and `np.unique` on the drawn start bars plus
  `run_brackets`' one-position-at-a-time rule can silently drop a draw that lands
  inside another trade's still-open window, so the realised trade count can come in
  slightly under `n_trades`.
- `percentile_of(actual, distribution)` — fraction of the control distribution at or
  below the actual result.
- Random non-overlapping placement (`_draw_non_overlapping_starts`) is an O(k) exact
  uniform-composition placement (k = number of trades), not a rejection sampler —
  needed at RES008's scale (thousands of bars, hundreds of trades, hundreds of
  replications, across hundreds of (strategy, ticker) pairs).

### `bootstrap.py`
- `stationary_block_bootstrap_ci(x, stat, block_len, n_boot, alpha, seed)` — Politis–
  Romano stationary (circular) block bootstrap, geometric block lengths with mean
  `block_len` (default `max(5, round(n**(1/3) * 2))`), percentile interval. Used
  instead of a t-test or ordinary iid bootstrap because daily returns are
  autocorrelated (Lo 2002) and an iid resample would understate true uncertainty.
- `paired_diff_ci(a, b, ...)` — CI for `stat(a) - stat(b)` using the **same**
  resampled block-index path for both series on each replicate, so shared structure
  (e.g. two arms measured on the same dates) is preserved rather than washed out.
- `proportion_ci(successes, n)` — Wilson score interval. Its docstring warns
  explicitly: this treats trades as independent Bernoulli draws, which is weak when
  trades overlap in time or share a market-wide regime driver. Prefer the block
  bootstrap on a return series when that independence assumption is doubtful.
- **No p-values, no significance stars, anywhere.** Report the window and the
  interval, every time — house rule (repo README, Method standard #5).

## Execution-timing convention

```
next_open (default):

  ... close(t-1)      close(t)            open(t+1)      close(t+1) ...
                          |  signal            |               |
                          |  decided            \  fill        |
                 old position earns <----------- new position earns ---->
                 [close(t-1) -> open(t+1)]      [open(t+1) -> close(t+1)]

  Bar t+1's net return COMPOUNDS the two legs -- (1+leg1)*(1+leg2) - 1, not a
  sum -- so an UNCHANGED position's bar return still reduces exactly to plain
  close-to-close (this is what the buy-and-hold identity test checks). A
  signal observed at close(t) never earns the close(t-1) -> close(t) move
  that produced it.

same_close:

  ... close(t-1)      close(t) ============================ close(t+1) ...
                          |  signal + decided + filled            |
                          |<-- new position earns this leg ------>|

  Reproduces the "instant, free fill at the signal bar's close" assumption
  many tutorials make implicitly. Needed to run an "as taught" arm honestly,
  not a recommended convention.
```

## Trade-return convention

A run `start..end` in `positions_held` (a maximal stretch of one sign) does NOT earn
its economic entry/exit on its own first/last bar alone — the exit leg (and exit cost)
land one bar OUTSIDE the run, on the bar `run_positions` itself charges the turnover
cost:

```
next_open:  run is bars [start .. end] (held == sign there)

  entry: open(start)                         -- bar `start` is already the
                                                 execution bar
  ...    close(start)->open(start+1)->close(start+1)->...->close(end)
  exit:  open(end + 1)                       -- the OLD position earns
                                                 close(end) -> open(end+1)
                                                 before the NEW target
                                                 takes over there
         (or close(n-1), no exit leg/cost, if the run reaches the last bar)

  trade's true price span:  open(start)  ->  open(end + 1)

same_close:  run is bars [start .. end]

  entry: close(start)                        -- decided AND filled here;
                                                 earns close(start)->close(start+1)
                                                 on the run's own FIRST bar
  exit:  close(end + 1)                      -- still holding through
                                                 close(end)->close(end+1)
         (or close(n-1), no exit leg/cost, if the run reaches the last bar)

  trade's true price span:  close(start)  ->  close(end + 1)
```

`gross_return` is **not** a shortcut `sign * (exit_price / entry_price - 1)` — for a
constant SHORT position that formula is simply wrong: unlike a long, negating a
price-ratio return and compounding it across many bars does not equal compounding
`(1 + sign * (leg_ratio - 1))` bar by bar (there is no closed form in the two endpoint
prices alone once `sign = -1`). `_extract_trades` (and `placebo._price_placed_trade`,
which prices a matched-random trade of the same shape identically) instead replays
every bar's own leg with the same formula the daily engine uses, for both signs and
both conventions. This is what makes `prod(1 + trades.gross_return) - 1` reproduce
`prod(1 + gross_daily_returns) - 1` exactly (float precision) — `net_return` differs
from the compounded daily net series by a small, second-order additive-vs-compounded
cost drag (the daily engine compounds each cost forward through later bars; the trade
table subtracts each trade's cost once from that trade's own total), which is expected
and bounded, not a bug.

Both engines assume a **constant position size within a run** (true for every RES008
use: positions are drawn from `{-1, 0, +1}`) — if size varies inside a run, the size
at the run's first bar is used, which is a simplification, not an exact accounting of
a resized position.

## Cost convention

`cost_bps` is charged per unit of **absolute position change**, on the bar where the
change executes. Flat → long → flat pays `cost_bps` twice (once on entry, once on
exit — total `2 * cost_bps`); a `+1 -> -1` flip pays `2 * cost_bps` on the single bar
where the flip executes, because `|change| = 2`. A position held unchanged pays
nothing. `run_brackets` charges `cost_bps` once on the entry bar and once on the exit
bar (also `2 * cost_bps` per round trip).

## The both-in-one-bar rule (`run_brackets`)

Daily (or even intraday) OHLC bars do not tell you the true order in which price
touched the take-profit and stop-loss levels within a single bar. When both levels
fall inside one bar's `[low, high]` range, `run_brackets` **always assumes the stop
was hit first**. This is a conservative modelling choice, deliberately biased against
the strategy being tested, not a claim about what actually happened intrabar.

## Running the tests

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp/docs/Research/RES008_exposing_fraud"
.venv/bin/python -m pytest common/tests -q            # network test skipped by default
.venv/bin/python -m pytest common/tests -q -m network # run the network smoke test explicitly
```

`common/tests/pytest.ini` registers the `network` marker and sets
`addopts = -m "not network"`, so the default run never touches the network; the one
`@pytest.mark.network` test (`test_load_daily_spy_network_smoke` in `test_data.py`)
must be run explicitly with `-m network`.
