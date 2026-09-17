"""
EXPLORATORY -- not pre-registered; written and run after the pre-registered
results were seen.

Extended placebo resolver for the post-hoc diagnostic
(`posthoc_diagnostic.py`). Does not modify or import from `placebo_swing.py`
-- that module backs the pre-registered `run_c05.py` pipeline and its
already-written `out/results.json`/`out/summary.txt`, which this follow-up
must not touch. This is a parallel, separately-seeded extension of the same
resolver rules (same 10-bar swing stop, same R target, same one-position-
at-a-time / stop-first-in-bar / gap-fills-at-open discipline as
`swing_stop_resolver.run_swing_r_brackets` and `placebo_swing._resolve_one_trade`)
that additionally reports, per resolved trade: the stop distance as a
fraction of entry price, and percent (not R-normalised) gross/net returns
-- the detail needed to diagnose whether "net expectancy in R" is
ill-conditioned by tiny R-denominators, per the coordinator's question.

`run_placebo_replications_ext` also supports an optional
`min_stop_dist_pct` floor: a drawn signal is rejected and redrawn (up to
`max_passes` tries per placement, same retry budget as the unconstrained
placebo) if its stop distance as a fraction of entry price would fall below
that floor. This is the "distance-matched" placebo arm -- it answers "what
does random timing look like once the tiny-stop-distance trades that blow
up the R-denominator are excluded the same way the recipe's own 10th
percentile stop distance excludes them." If no candidate bar in a
replication's remaining usable range clears the floor after exhausting
`max_passes` tries, the draw is accepted anyway and counted in
`n_floor_exhausted` -- this arm is diagnostic, not a guarantee, and a
silent floor violation would misrepresent what was actually drawn.
"""

from __future__ import annotations

import numpy as np


def _swing_stop_price(low: np.ndarray, high: np.ndarray, signal_bar: int, side_is_long: bool, lookback: int) -> float:
    start = max(0, signal_bar - lookback + 1)
    if side_is_long:
        return float(np.min(low[start : signal_bar + 1]))
    return float(np.max(high[start : signal_bar + 1]))


def _stop_dist_pct_for_signal(
    open_: np.ndarray, high: np.ndarray, low: np.ndarray, signal_bar: int, side_is_long: bool, lookback: int, n: int
) -> float | None:
    """Stop distance as a fraction of entry price for the trade a signal at
    `signal_bar` WOULD open, or None if there is no room for an entry bar."""
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return None
    entry_price = open_[entry_bar]
    stop_price = _swing_stop_price(low, high, signal_bar, side_is_long, lookback)
    return abs(entry_price - stop_price) / entry_price


def _resolve_one_trade_ext(
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
) -> dict:
    """Same exit resolution as `placebo_swing._resolve_one_trade`, returning
    the fuller per-trade record the post-hoc diagnostic needs (stop distance
    %, percent returns) in addition to the R-normalised ones."""
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return {"skipped": True, "exit_bar": signal_bar}

    entry_price = open_[entry_bar]
    stop_price = _swing_stop_price(low, high, signal_bar, side_is_long, lookback)

    wrong_side = (stop_price >= entry_price) if side_is_long else (stop_price <= entry_price)
    if wrong_side:
        return {"skipped": True, "exit_bar": entry_bar}

    sign = 1.0 if side_is_long else -1.0
    r_distance = abs(entry_price - stop_price)
    stop_dist_pct = r_distance / entry_price
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

    gross_pct = sign * (exit_price / entry_price - 1.0)
    net_pct = gross_pct - 2 * cost_rate
    gross_r = sign * (exit_price - entry_price) / r_distance
    cost_r = (2 * cost_rate * entry_price) / r_distance
    net_r = gross_r - cost_r

    return {
        "skipped": False,
        "exit_bar": exit_bar,
        "gross_r": gross_r,
        "net_r": net_r,
        "gross_pct": gross_pct,
        "net_pct": net_pct,
        "cost_r": cost_r,
        "stop_dist_pct": stop_dist_pct,
    }


def run_placebo_replications_ext(
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
    min_stop_dist_pct: float | None = None,
    max_passes: int = 200,
) -> dict:
    """Extended placebo: per-replication sums of gross/net R, gross/net
    percent, cost-in-R, and stop-distance-percent, plus per-rep win/realised
    counts -- everything `posthoc_diagnostic.py` needs to report gross-only
    and percent-based views alongside the pre-registered R-normalised ones.

    `min_stop_dist_pct`, when given, makes this the "distance-matched" arm:
    a drawn signal bar is rejected and redrawn (same `max_passes` retry
    budget used for the one-position-at-a-time constraint) if
    `_stop_dist_pct_for_signal` at that bar would fall below the floor.
    `n_floor_exhausted` counts placements (not replications) where, WITH a
    floor active, no candidate bar cleared both the one-position-at-a-time
    cursor and the floor within `max_passes` tries and the draw was
    accepted anyway -- so a caller can see if the floor was ever not
    actually met. It stays 0 whenever `min_stop_dist_pct is None`, even
    though the same retry loop can still exhaust its budget on the cursor
    constraint alone (as the unfloored `placebo_swing.run_placebo_replications`
    does silently) -- that is the pre-existing one-position-at-a-time
    fallback, not a floor violation, so it is not counted here.
    """
    n = len(close)
    rng = np.random.default_rng(seed)

    win_count = np.zeros(n_reps, dtype=np.int64)
    n_realised = np.zeros(n_reps, dtype=np.int64)
    sum_net_r = np.zeros(n_reps, dtype=np.float64)
    sum_gross_r = np.zeros(n_reps, dtype=np.float64)
    sum_net_pct = np.zeros(n_reps, dtype=np.float64)
    sum_gross_pct = np.zeros(n_reps, dtype=np.float64)
    sum_cost_r = np.zeros(n_reps, dtype=np.float64)
    stop_dist_pcts: list[float] = []
    n_floor_exhausted = 0

    last_usable_signal_bar = n - 2
    empty = {
        "win_count": win_count,
        "n_realised": n_realised,
        "sum_net_r": sum_net_r,
        "sum_gross_r": sum_gross_r,
        "sum_net_pct": sum_net_pct,
        "sum_gross_pct": sum_gross_pct,
        "sum_cost_r": sum_cost_r,
        "stop_dist_pcts": np.array(stop_dist_pcts, dtype=np.float64),
        "n_floor_exhausted": n_floor_exhausted,
    }
    if last_usable_signal_bar < 0 or n_trades == 0:
        return empty

    for r in range(n_reps):
        sides = np.zeros(n_trades, dtype=bool)
        sides[:n_long] = True
        rng.shuffle(sides)

        cursor = 0
        k = 0
        while k < n_trades:
            side_is_long = bool(sides[k])
            placed = False
            candidate = None
            for _attempt in range(max_passes):
                candidate = int(rng.integers(0, last_usable_signal_bar + 1))
                if candidate < cursor:
                    continue
                if min_stop_dist_pct is not None:
                    dist = _stop_dist_pct_for_signal(open_, high, low, candidate, side_is_long, lookback, n)
                    if dist is None or dist < min_stop_dist_pct:
                        continue
                placed = True
                break
            if not placed:
                if min_stop_dist_pct is not None:
                    n_floor_exhausted += 1
                cursor = 0
                candidate = int(rng.integers(0, last_usable_signal_bar + 1))
            signal_bar = candidate

            rec = _resolve_one_trade_ext(
                open_, high, low, close, signal_bar, side_is_long,
                target_r, cost_rate, max_bars, lookback, n,
            )
            if not rec["skipped"]:
                n_realised[r] += 1
                sum_net_r[r] += rec["net_r"]
                sum_gross_r[r] += rec["gross_r"]
                sum_net_pct[r] += rec["net_pct"]
                sum_gross_pct[r] += rec["gross_pct"]
                sum_cost_r[r] += rec["cost_r"]
                stop_dist_pcts.append(rec["stop_dist_pct"])
                if rec["net_r"] > 0:
                    win_count[r] += 1
            cursor = rec["exit_bar"] + 1
            k += 1

    return {
        "win_count": win_count,
        "n_realised": n_realised,
        "sum_net_r": sum_net_r,
        "sum_gross_r": sum_gross_r,
        "sum_net_pct": sum_net_pct,
        "sum_gross_pct": sum_gross_pct,
        "sum_cost_r": sum_cost_r,
        "stop_dist_pcts": np.array(stop_dist_pcts, dtype=np.float64),
        "n_floor_exhausted": n_floor_exhausted,
    }
