"""
Placebo control for C05: random entries through the identical swing-stop /
R-target resolver.

Per replication, for a given instrument: draw the same COUNT of trades and
the same LONG/SHORT MIX as the real recipe produced on that instrument (in
that cell), placed at uniformly random signal bars (one position at a time,
same one-position-at-a-time discipline as the real run -- a later draw
landing before the previous draw's exit is simply re-drawn forward), apply
the IDENTICAL 10-bar swing-stop rule, the same R target, and the same
per-side costs through a numpy re-implementation of
`swing_stop_resolver.run_swing_r_brackets`'s exact exit rules (stop-first
when both levels fall in one bar, gap-through fills at the open,
`max_bars` time exit). This is the control for "the recipe's win rate and
expectancy are just what its own stop/target geometry gives any entry,
timed by nothing at all."

Pure-numpy inner loop (no pandas) because this runs 500 replications x 7
instruments x 12 cells: `_run_replication` operates entirely on primitive
arrays, matching `swing_stop_resolver._resolve_exit`'s branch order and
`swing_stop_distance`'s window exactly so the placebo is priced by the same
rules as the real trades, not merely a similar approximation of them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PlaceboCellResult:
    pooled_win_rate: np.ndarray  # shape (n_reps,)
    pooled_net_expectancy_r: np.ndarray  # shape (n_reps,)
    pooled_gross_expectancy_r: np.ndarray  # shape (n_reps,)


def _swing_stop_price(low: np.ndarray, high: np.ndarray, signal_bar: int, side_is_long: bool, lookback: int) -> float:
    start = max(0, signal_bar - lookback + 1)
    if side_is_long:
        return float(np.min(low[start : signal_bar + 1]))
    return float(np.max(high[start : signal_bar + 1]))


def _resolve_one_trade(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal_bar: int,
    side_is_long: bool,
    target_r: float,
    cost_rate: float,
    max_bars: int,
    lookback: int,
    n: int,
) -> tuple[bool, int, float, float]:
    """Returns (skipped, exit_bar, net_r, gross_r). exit_bar is entry_bar's
    exit bar (the last bar this trade occupies), used by the caller to place
    the next draw strictly after it."""
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return True, signal_bar, 0.0, 0.0

    entry_price = open_[entry_bar]
    stop_price = _swing_stop_price(low, high, signal_bar, side_is_long, lookback)

    wrong_side = (stop_price >= entry_price) if side_is_long else (stop_price <= entry_price)
    if wrong_side:
        return True, entry_bar, 0.0, 0.0

    sign = 1.0 if side_is_long else -1.0
    r_distance = abs(entry_price - stop_price)
    target_price = entry_price + sign * target_r * r_distance

    max_j = min(entry_bar + max_bars - 1, n - 1)
    j = entry_bar
    exit_price = None
    while j <= max_j:
        bar_open = entry_price if j == entry_bar else open_[j]

        hit_target = (high[j] >= target_price) if side_is_long else (low[j] <= target_price)
        hit_stop = (low[j] <= stop_price) if side_is_long else (high[j] >= stop_price)
        gapped_through_stop = (bar_open <= stop_price) if side_is_long else (bar_open >= stop_price)

        if hit_stop and gapped_through_stop:
            exit_price = bar_open
            exit_bar = j
            break
        if hit_stop:
            exit_price = stop_price
            exit_bar = j
            break
        if hit_target:
            exit_price = target_price
            exit_bar = j
            break
        if j == max_j:
            exit_price = close[j]
            exit_bar = j
            break
        j += 1

    gross_return = sign * (exit_price / entry_price - 1.0)
    net_return = gross_return - 2 * cost_rate
    gross_r = sign * (exit_price - entry_price) / r_distance
    cost_r = (2 * cost_rate * entry_price) / r_distance
    net_r = gross_r - cost_r

    return False, exit_bar, net_r, gross_r


def run_placebo_replications(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    n_trades: int,
    n_long: int,
    target_r: float,
    cost_rate: float,
    max_bars: int,
    lookback: int,
    n_reps: int,
    seed: int,
    max_passes: int = 200,
) -> dict:
    """`n_trades` random trades per replication, `n_long` of them long (the
    rest short), matching the real cell's count and side mix on this
    instrument. Returns per-replication (win_count, n_realised, sum_net_r,
    sum_gross_r) arrays so the caller can pool across instruments before
    computing win rate / expectancy (pooling raw counts/sums, not
    per-instrument rates, keeps every trade weighted equally in the pool).

    Bracket-style exits are path-dependent (stop/target/time), so a trade's
    holding period is not known before it resolves -- the same problem
    `common/placebo.py`'s `matched_random_brackets` and
    `C04_win_rate_proves_edge/code/brackets_mixed.draw_entry_bars_mixed`
    solve for a single global draw. Within a replication, each signal bar
    is drawn UNIFORMLY over the whole usable range and only accepted if it
    is at or after the current cursor (i.e. not inside the position the
    previous draw in this pass is still holding); drawing uniformly over
    the full range each time (rather than narrowing the sampled interval to
    `[cursor, last_usable]`, which would waste most of an average trade's
    ~30-bar holding period by concentrating later draws near the end of the
    series and starving the count) keeps the marginal placement of any one
    signal close to uniform while still respecting one-position-at-a-time.
    If a pass cannot place the next signal within `max_passes` uniform
    tries (the position it would land in remains open for the rest of the
    series), the position is reset to the start of the range for a fresh
    pass -- mirroring the resampling-pass pattern already established for
    the same path-dependent-exit problem in `brackets_mixed.py`, and never
    silently under-delivering trades the way a single narrowing-window walk
    would.
    """
    n = len(close)
    rng = np.random.default_rng(seed)

    win_count = np.zeros(n_reps, dtype=np.int64)
    n_realised = np.zeros(n_reps, dtype=np.int64)
    sum_net_r = np.zeros(n_reps, dtype=np.float64)
    sum_gross_r = np.zeros(n_reps, dtype=np.float64)

    last_usable_signal_bar = n - 2
    if last_usable_signal_bar < 0 or n_trades == 0:
        return {
            "win_count": win_count,
            "n_realised": n_realised,
            "sum_net_r": sum_net_r,
            "sum_gross_r": sum_gross_r,
        }

    for r in range(n_reps):
        sides = np.zeros(n_trades, dtype=bool)
        sides[:n_long] = True
        rng.shuffle(sides)

        cursor = 0
        k = 0
        while k < n_trades:
            placed = False
            for _attempt in range(max_passes):
                signal_bar = int(rng.integers(0, last_usable_signal_bar + 1))
                if signal_bar >= cursor:
                    placed = True
                    break
            if not placed:
                cursor = 0
                signal_bar = int(rng.integers(0, last_usable_signal_bar + 1))

            skipped, exit_bar, net_r, gross_r = _resolve_one_trade(
                open_, high, low, close, signal_bar, bool(sides[k]),
                target_r, cost_rate, max_bars, lookback, n,
            )
            if not skipped:
                n_realised[r] += 1
                sum_net_r[r] += net_r
                sum_gross_r[r] += gross_r
                if net_r > 0:
                    win_count[r] += 1
            cursor = exit_bar + 1
            k += 1

    return {
        "win_count": win_count,
        "n_realised": n_realised,
        "sum_net_r": sum_net_r,
        "sum_gross_r": sum_gross_r,
    }
