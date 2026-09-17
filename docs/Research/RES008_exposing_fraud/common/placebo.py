"""
Placebo controls for RES008: what does trade geometry alone produce?

Every claim tested in this programme must beat a control that has the same
trade count, the same holding-period distribution and the same costs but
picks its entries with no information at all. If a "signal" cannot beat
random entries of the same shape, the signal is not doing anything -- the
apparent edge is coming from the trade geometry (holding period, side,
cost drag) rather than from timing.

`matched_random_entries` matches position-based trades (from
`backtest.run_positions`): same count, same sides, same holding-period
multiset, drawn at uniformly random non-overlapping start dates, PRICED
UNDER THE SAME EXECUTION CONVENTION as the real trades (`execution=`,
default "next_open") -- a random trade must earn exactly the overnight
exit leg a real trade of the same shape would earn, or the control is
biased: for equities that overnight leg carries real drift, and pricing
the control's exit at that day's close (as if it always exited same-day)
would systematically miss it.

`matched_random_brackets` is the bracket-engine analogue: it does not try
to match a specific trade list, since bracket exits are path-dependent
(TP/SL/time), so instead it draws `n_trades` random entry dates and runs
them through the *same* `run_brackets` engine with the *same* TP/SL/max_bars
geometry, showing what that geometry does with zero signal. It matches
geometry and approximate count only, not an exact holding-period multiset:
`np.unique` on the drawn start bars plus `run_brackets`' one-position-at-a-
time rule can silently drop a draw that lands inside another trade's still-
open window, so the realised trade count can come in slightly under
`n_trades`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import run_brackets


def percentile_of(actual: float, distribution: np.ndarray) -> float:
    """Fraction of `distribution` that is <= actual, in [0, 1]."""
    distribution = np.asarray(distribution, dtype=float)
    if len(distribution) == 0:
        raise ValueError("distribution is empty")
    return float(np.mean(distribution <= actual))


def _uniform_composition(total: int, parts: int, rng: np.random.Generator) -> np.ndarray:
    """A uniform-random composition of `total` into `parts` non-negative integers.

    Stars-and-bars: choosing `parts - 1` distinct divider positions out of
    `total + parts - 1` slots (uniformly, without replacement) and reading
    off the gaps between them is a uniform bijection onto all compositions
    of `total` into `parts` non-negative parts.
    """
    if parts == 1:
        return np.array([total], dtype=int)
    chosen = np.sort(rng.choice(total + parts - 1, size=parts - 1, replace=False))
    boundaries = np.concatenate(([-1], chosen, [total + parts - 1]))
    return np.diff(boundaries) - 1


def _draw_non_overlapping_starts(
    n_bars: int,
    holding_periods: list[int],
    rng: np.random.Generator,
) -> list[int]:
    """Uniform random non-overlapping placement of intervals with the given lengths.

    Exact O(k) placement (k = number of intervals), replacing an earlier
    O(n_bars * k)-per-replication rejection sampler that was too slow at
    RES008's scale (thousands of bars, hundreds of trades, hundreds of
    replications, across hundreds of (strategy, ticker) pairs).

    The k intervals occupy `L = sum(holding_periods)` bars total, leaving
    `free = n_bars - L` bars to distribute as k+1 gaps (before, between,
    and after the intervals in some order). Shuffling the interval order
    first and then drawing gap sizes as a uniform random composition of
    `free` into k+1 parts is uniform over all non-overlapping placements of
    that order -- laying the shuffled intervals out left to right,
    separated by the drawn gaps, walks the free space and the intervals in
    lockstep with no rejection and no wasted draws.
    """
    k = len(holding_periods)
    total_occupied = sum(holding_periods)
    free = n_bars - total_occupied
    if free < 0:
        raise ValueError(
            f"cannot place {k} trades occupying {total_occupied} bars into only {n_bars} bars"
        )

    order = rng.permutation(k)
    gaps = _uniform_composition(free, k + 1, rng)

    starts = [None] * k
    cursor = int(gaps[0])
    for slot, idx in enumerate(order):
        starts[idx] = cursor
        cursor += holding_periods[idx] + int(gaps[slot + 1])

    return starts


def _price_placed_trade(
    open_: np.ndarray, close: np.ndarray, start: int, length: int, side: str, execution: str
) -> tuple[float, int]:
    """Gross return of a trade of `length` bars starting at `start`, priced like a real one.

    Mirrors `backtest._trade_gross_return` exactly: `next_open` earns
    open[start] -> open[start+length] (close[n-1] if the trade runs off the
    end of the series); `same_close` earns close[start] -> close[start+length]
    likewise. A constant-sign position does not compound to a simple
    price-ratio return when short (see `backtest.py`), so this replays the
    per-bar legs rather than taking an entry/exit price shortcut -- exactly
    like the real trades this control is matched against.
    """
    n = len(close)
    sign = 1.0 if side == "long" else -1.0
    end = start + length - 1  # last bar the position is HELD for, before any exit leg
    exit_bar = end + 1 if end + 1 < n else n - 1

    growth = 1.0
    if execution == "next_open":
        growth *= 1.0 + sign * (close[start] / open_[start] - 1.0)
        for t in range(start + 1, end + 1):
            leg1 = sign * (open_[t] / close[t - 1] - 1.0)
            leg2 = sign * (close[t] / open_[t] - 1.0)
            growth *= (1.0 + leg1) * (1.0 + leg2)
        if exit_bar > end:
            growth *= 1.0 + sign * (open_[exit_bar] / close[end] - 1.0)
    else:
        for t in range(start + 1, end + 1):
            growth *= 1.0 + sign * (close[t] / close[t - 1] - 1.0)
        if exit_bar > end:
            growth *= 1.0 + sign * (close[exit_bar] / close[end] - 1.0)

    return growth - 1.0, exit_bar


def matched_random_entries(
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    n_reps: int,
    cost_bps: float,
    seed: int,
    execution: str = "next_open",
) -> dict[str, np.ndarray]:
    """Random-entry control matched to `trades` on count, side and holding period.

    Each matched trade is priced under `execution` (default "next_open",
    matching `run_positions`' default) exactly as `backtest._extract_trades`
    prices a real trade of that shape -- same entry/exit bars relative to
    its start and length, same per-bar leg replay for shorts. Costs are the
    same 2x cost_rate per round trip (1x if the trade runs off the end of
    the series with nothing left to charge an exit cost on, matching
    `run_positions`).

    Returns a dict with `total_returns` (per-replication compounded net
    return across all that replication's matched trades) and
    `mean_trade_returns` (per-replication mean net return per trade).
    """
    if len(trades) == 0:
        raise ValueError("trades is empty; nothing to match")

    n_bars = len(bars)
    close = bars["close"].to_numpy(dtype=float)
    open_ = bars["open"].to_numpy(dtype=float)
    cost_rate = cost_bps / 10_000.0

    sides = trades["side"].tolist()
    holding_periods = trades["bars_held"].astype(int).tolist()

    rng = np.random.default_rng(seed)

    total_returns = np.empty(n_reps)
    mean_trade_returns = np.empty(n_reps)

    for r in range(n_reps):
        starts = _draw_non_overlapping_starts(n_bars, holding_periods, rng)

        trade_net_returns = []
        for side, length, start in zip(sides, holding_periods, starts):
            gross, exit_bar = _price_placed_trade(open_, close, start, length, side, execution)
            end = start + length - 1
            closes_within_series = exit_bar > end
            cost = cost_rate * (1.0 + (1.0 if closes_within_series else 0.0))
            trade_net_returns.append(gross - cost)

        trade_net_returns = np.array(trade_net_returns)
        total_returns[r] = float(np.prod(1.0 + trade_net_returns) - 1.0)
        mean_trade_returns[r] = float(np.mean(trade_net_returns))

    return {"total_returns": total_returns, "mean_trade_returns": mean_trade_returns}


def matched_random_brackets(
    bars: pd.DataFrame,
    n_trades: int,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_bars: int,
    cost_bps: float,
    side: str,
    n_reps: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Random-entry control run through the same bracket engine as the real signal.

    Shows what a TP/SL/max_bars geometry produces with zero timing skill:
    entries are drawn at random bars (spaced so each bracket has room to
    resolve within `max_bars`), then run through `run_brackets` exactly as
    the real signal would be.
    """
    n_bars = len(bars)
    rng = np.random.default_rng(seed)

    win_rates = np.empty(n_reps)
    expectancies = np.empty(n_reps)

    latest_start = n_bars - max_bars - 2
    if latest_start < 1:
        raise ValueError("bars too short for the requested max_bars")

    for r in range(n_reps):
        starts = rng.choice(np.arange(1, latest_start + 1), size=n_trades, replace=True)
        entries = pd.Series(False, index=bars.index)
        entries.iloc[np.unique(starts)] = True

        result = run_brackets(
            bars,
            entries,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            max_bars=max_bars,
            cost_bps=cost_bps,
            side=side,
        )
        trades = result.trades
        if len(trades) == 0:
            win_rates[r] = float("nan")
            expectancies[r] = float("nan")
            continue
        win_rates[r] = float((trades["net_return"] > 0).mean())
        expectancies[r] = float(trades["net_return"].mean())

    return {"win_rate": win_rates, "expectancy": expectancies}
