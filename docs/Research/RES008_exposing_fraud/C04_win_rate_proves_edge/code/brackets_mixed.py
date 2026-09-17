"""
Mixed-side bracket engine for C04 Part 1.

`common.backtest.run_brackets` takes one `side` for the whole call. C04's
random-entry design draws a fresh 50/50 long/short coin flip per trade, so
this module re-implements the same entry/exit/cost logic with a per-entry
side instead of a single global one. `run_mixed_brackets` is structured as
a bar-by-bar replay of `run_brackets` with `sign` looked up per trade rather
than fixed for the whole series, so that with a uniform side sequence it
must produce bit-for-bit the same trades — `tests/test_brackets_mixed_agrees.py`
proves this on real SPY bars for both "long" and "short".

`draw_entry_bars_mixed` draws the actual (entry_bar, side) sequence used by
`run_c04.py`: entries are picked sequentially -- a random bar strictly after
the previous trade's exit bar -- with a fresh independent coin flip for
side, exactly as the pre-registration describes ("draw sequentially: pick a
random bar after the previous exit"). No single instrument's history is
long enough to fit 2,000 non-overlapping brackets in one pass at any C04
geometry (window * 2,000 exceeds even SPY's full history), so the design
explicitly allows resampling passes over the same history with fresh
random offsets. Each pass is one hypothetical single-position-at-a-time
run and is returned as its own group of (signal_bars, sides) rather than
flattened into one global draw: running every pass's signals through a
single `run_mixed_brackets` call would let one pass's still-open position
window silently swallow a different pass's signal that happens to land
inside it (both passes reuse the same calendar bars by design), which is
exactly the "silently deliver fewer trades" failure the pre-registration
rules out. `run_c04.py` runs the engine once per pass and concatenates the
resulting trades, so every drawn signal becomes a real, counted trade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.backtest import BacktestResult, _validate_bars


def run_mixed_brackets(
    bars: pd.DataFrame,
    entries: pd.Series,
    sides: pd.Series,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_bars: int,
    cost_bps: float,
) -> BacktestResult:
    """Bracket backtest where each entry signal carries its own side.

    `entries` is a boolean Series aligned to `bars.index`, exactly as in
    `run_brackets`. `sides` gives the side ("long"/"short") to use for the
    trade opened at each True entry bar; a signal arriving while a position
    is open is still ignored, matching `run_brackets`.
    """
    _validate_bars(bars)
    if "low" not in bars.columns or "high" not in bars.columns:
        raise ValueError("bars must include 'high' and 'low' for bracket exits")

    n = len(bars)
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    signal = entries.reindex(bars.index).fillna(False)
    if signal.dtype != bool:
        signal = signal.astype(bool)
    signal_arr = signal.to_numpy()

    side_arr = sides.reindex(bars.index).to_numpy()

    cost_rate = cost_bps / 10_000.0

    held = np.zeros(n)
    gross = np.zeros(n)
    net = np.zeros(n)
    records = []

    i = 0
    while i < n - 1:
        if not signal_arr[i]:
            i += 1
            continue

        side = side_arr[i]
        if side not in ("long", "short"):
            raise ValueError(f"unknown side {side!r} at signal bar {i}")
        sign = 1.0 if side == "long" else -1.0

        entry_bar = i + 1
        entry_price = open_[entry_bar]
        tp_price = entry_price * (1.0 + sign * take_profit_pct)
        sl_price = entry_price * (1.0 - sign * stop_loss_pct)

        held[entry_bar] = sign

        entry_cost = cost_rate
        exit_bar = None
        exit_price = None
        exit_reason = None

        j = entry_bar
        max_j = min(entry_bar + max_bars - 1, n - 1)
        while j <= max_j:
            if j == entry_bar:
                bar_open_for_j = entry_price
                bar_gross = sign * (close[j] / entry_price - 1.0)
            else:
                bar_open_for_j = open_[j]
                bar_gross = sign * (close[j] / close[j - 1] - 1.0)
                held[j] = sign

            hit_tp = (high[j] >= tp_price) if side == "long" else (low[j] <= tp_price)
            hit_sl = (low[j] <= sl_price) if side == "long" else (high[j] >= sl_price)

            gapped_through_sl = (bar_open_for_j <= sl_price) if side == "long" else (bar_open_for_j >= sl_price)

            if hit_sl and gapped_through_sl:
                exit_price = bar_open_for_j
                exit_reason = "stop_gap"
                bar_gross = sign * (exit_price / (entry_price if j == entry_bar else close[j - 1]) - 1.0)
                exit_bar = j
            elif hit_sl and hit_tp:
                exit_price = sl_price
                exit_reason = "stop"
                bar_gross = sign * (exit_price / (entry_price if j == entry_bar else close[j - 1]) - 1.0)
                exit_bar = j
            elif hit_sl:
                exit_price = sl_price
                exit_reason = "stop"
                bar_gross = sign * (exit_price / (entry_price if j == entry_bar else close[j - 1]) - 1.0)
                exit_bar = j
            elif hit_tp:
                exit_price = tp_price
                exit_reason = "take_profit"
                bar_gross = sign * (exit_price / (entry_price if j == entry_bar else close[j - 1]) - 1.0)
                exit_bar = j
            elif j == max_j:
                exit_price = close[j]
                exit_reason = "time_exit"
                exit_bar = j
            else:
                gross[j] += bar_gross
                net[j] += bar_gross
                j += 1
                continue

            gross[j] += bar_gross
            net[j] += bar_gross
            break

        exit_cost = cost_rate
        net[entry_bar] -= entry_cost
        net[exit_bar] -= exit_cost

        bars_held = exit_bar - entry_bar + 1
        trade_gross = sign * (exit_price / entry_price - 1.0)
        trade_net = trade_gross - 2 * cost_rate

        records.append(
            {
                "entry_date": bars.index[entry_bar],
                "exit_date": bars.index[exit_bar],
                "side": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "bars_held": bars_held,
                "gross_return": float(trade_gross),
                "net_return": float(trade_net),
                "exit_reason": exit_reason,
            }
        )

        i = exit_bar + 1

    gross_daily_returns = pd.Series(gross, index=bars.index, name="gross_daily_returns")
    net_daily_returns = pd.Series(net, index=bars.index, name="daily_returns")
    positions_held = pd.Series(held, index=bars.index, name="positions_held")
    trades = pd.DataFrame(
        records,
        columns=[
            "entry_date",
            "exit_date",
            "side",
            "entry_price",
            "exit_price",
            "bars_held",
            "gross_return",
            "net_return",
            "exit_reason",
        ],
    )

    return BacktestResult(
        daily_returns=net_daily_returns,
        gross_daily_returns=gross_daily_returns,
        positions_held=positions_held,
        trades=trades,
        _bars=bars,
    )


def draw_entry_bars_mixed(
    n_bars: int,
    n_trades: int,
    max_bars: int,
    rng: np.random.Generator,
) -> list[tuple[list[int], list[str]]]:
    """Draw `n_trades` sequential non-overlapping (entry-signal-bar, side) pairs.

    A "pass" is one walk forward through the history, sequentially: at each
    step it advances to the next bar at or after a cursor, draws a signal
    there with a fresh independent 50/50 side coin flip, and moves the
    cursor past that trade's whole worst-case window (signal bar .. signal
    bar + 1 + max_bars, the longest a bracket can stay open) so within a
    single pass no later draw ever lands on a bar the engine could still be
    holding a position through -- matching what a single-position-at-a-time
    engine run over one pass would actually realise. When 2,000 trades do
    not fit in one pass (window * n_trades > n_bars, true for every
    instrument at every C04 geometry -- max ~87 non-overlapping trades over
    even SPY's full history at the widest geometry), a fresh resampling
    pass restarts from a newly drawn random offset (still consuming `rng`,
    fully determined by the fixed seed): different passes MAY reuse
    calendar bars, since each pass stands for an independent hypothetical
    single-position run over the same history, not one continuous
    position-tracking timeline shared across passes. The one bar-level
    invariant enforced across passes is that the same exact signal bar is
    never drawn twice -- reused only avoided at that granularity so the
    boolean `entries` Series handed to the engine can never silently
    collapse two draws into one and quietly under-deliver `n_trades`.
    Returns a list of (signal_bars, sides) groups, one per pass; the
    caller runs the engine once per group and concatenates trades, so the
    per-pass single-position invariant is preserved and every one of the
    `sum(len(g[0]) for g in groups) == n_trades` signals becomes a real
    trade. `len(groups)` is the number of resampling passes used.
    """
    if n_bars < max_bars + 2:
        raise ValueError("history too short for even one trade at this geometry")

    window = max_bars + 2  # signal bar + entry bar .. worst-case exit bar, inclusive
    last_bar_usable_as_signal = n_bars - 2  # signal at i needs entry_bar = i+1 <= n-1

    used_signal_bar = np.zeros(n_bars, dtype=bool)
    groups: list[tuple[list[int], list[str]]] = []
    total_drawn = 0
    n_passes = 0

    while total_drawn < n_trades:
        n_passes += 1
        offset = int(rng.integers(0, window)) if n_passes > 1 else 0
        cursor = offset
        pass_signal_bars: list[int] = []
        pass_sides: list[str] = []
        advanced_this_pass = False

        while total_drawn < n_trades and cursor <= last_bar_usable_as_signal:
            if used_signal_bar[cursor]:
                cursor += 1
                continue

            signal_bar = cursor
            side = "long" if rng.random() < 0.5 else "short"
            pass_signal_bars.append(signal_bar)
            pass_sides.append(side)
            used_signal_bar[signal_bar] = True
            advanced_this_pass = True
            total_drawn += 1

            cursor = signal_bar + window

        if pass_signal_bars:
            groups.append((pass_signal_bars, pass_sides))

        if total_drawn < n_trades and not advanced_this_pass:
            raise ValueError(
                "every bar usable as a signal is already used exactly once; "
                f"cannot realise {n_trades} distinct trades (got {total_drawn}) "
                "for this instrument/geometry."
            )

    return groups
