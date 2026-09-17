"""
Per-trade swing-stop/R-target bracket resolver for C05.

`common.backtest.run_brackets` takes one fixed take-profit/stop-loss
PERCENT and one fixed `side` per call. C05's recipe instead sets each
trade's own stop distance from a 10-bar swing low/high around the signal
bar (so every trade has its own stop in price terms, not a percent) and
mixes long and short signals from two different UT Bot instances in the
same run. `run_swing_r_brackets` is a from-scratch reimplementation of
exactly the same fill/exit/cost rules as `run_brackets`, generalised to a
per-trade stop distance and a per-trade side, so it can serve both variants'
long+short, R-multiple-target trades:

  - entry at the open of the bar AFTER the signal bar (`next_open`);
  - stop = lowest low (long) / highest high (short) of the 10 bars up to
    and including the signal bar; if that stop is on the wrong side of the
    entry open (e.g. a long whose entry opens at or below the swing low),
    the trade is skipped and counted, never taken;
  - target = entry +/- `target_r * (entry - stop)` (1R = entry - stop);
  - if both the stop and target fall inside one bar's [low, high], the
    STOP is assumed to trigger first (same conservative assumption as
    `run_brackets`);
  - a gap that opens through the stop fills at that bar's open, not the
    nominal stop price;
  - `cost_bps` is charged once on entry and once on exit (equities/ETFs 5
    bps, crypto 10 bps per PREREG_COMMON, looked up per instrument by the
    caller and passed in already resolved to a single number per call);
  - one position open at a time; a signal arriving while a position is
    open is ignored (not queued, not counted as a second trade);
  - a trade still open after `max_bars` bars closes at that bar's close
    (`time_exit`), matching `run_brackets`.

`test_swing_stop_agrees_with_run_brackets.py` proves this reduces to
`common.backtest.run_brackets` exactly, bit for bit, on a case where the
two coincide: a FIXED percentage stop/target (so the "swing stop" is
replaced with a constant distance) and a single side, on real SPY bars.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

_EXIT_REASONS = ["take_profit", "stop", "stop_gap", "time_exit"]


@dataclass
class SwingTrade:
    signal_bar: int
    side: str
    entry_bar: int | None
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    r_distance: float | None
    exit_bar: int | None
    exit_price: float | None
    exit_reason: str | None
    gross_return: float | None
    net_return: float | None
    gross_r: float | None
    net_r: float | None
    skipped: bool


@dataclass
class SwingBracketResult:
    trades: pd.DataFrame
    n_skipped: int
    _bars: pd.DataFrame = field(repr=False)


def swing_stop_distance(bars: pd.DataFrame, signal_bar: int, side: str, lookback: int = 10) -> float:
    """Lowest low (long) / highest high (short) of the `lookback` bars up to
    and including `signal_bar`. Returns the STOP PRICE (not a distance)."""
    start = max(0, signal_bar - lookback + 1)
    window = bars.iloc[start : signal_bar + 1]
    if side == "long":
        return float(window["low"].min())
    return float(window["high"].max())


def run_swing_r_brackets(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    target_r: float,
    cost_bps: float,
    max_bars: int = 200,
    lookback: int = 10,
) -> SwingBracketResult:
    """Backtest per-trade swing-stop / R-multiple-target brackets.

    `signals` is a DataFrame aligned to `bars.index` with a boolean `long`
    column and a boolean `short` column (both may be True on different bars;
    a bar with both True is not expected under this recipe's entry filters
    and is resolved by preferring `long`, recorded as a deviation if it ever
    fires). A signal on bar i is observed at close(i); the trade (if not
    skipped) enters at open(i+1). One position open at a time -- a signal
    arriving on a bar while a position is already open is ignored, not
    queued.
    """
    _validate(bars)
    n = len(bars)
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    long_sig = signals["long"].reindex(bars.index).fillna(False).to_numpy()
    short_sig = signals["short"].reindex(bars.index).fillna(False).to_numpy()

    cost_rate = cost_bps / 10_000.0
    records: list[dict] = []
    n_skipped = 0
    both_sides_fired = 0

    i = 0
    while i < n - 1:
        is_long = bool(long_sig[i])
        is_short = bool(short_sig[i])
        if not is_long and not is_short:
            i += 1
            continue
        if is_long and is_short:
            both_sides_fired += 1
            is_short = False

        side = "long" if is_long else "short"
        sign = 1.0 if side == "long" else -1.0

        entry_bar = i + 1
        entry_price = open_[entry_bar]
        stop_price = swing_stop_distance(bars, i, side, lookback=lookback)

        wrong_side = (side == "long" and stop_price >= entry_price) or (
            side == "short" and stop_price <= entry_price
        )
        if wrong_side:
            n_skipped += 1
            records.append(
                _skip_record(bars.index[i], side, entry_price, stop_price)
            )
            i += 1
            continue

        r_distance = abs(entry_price - stop_price)
        target_price = entry_price + sign * target_r * r_distance

        exit_bar, exit_price, exit_reason = _resolve_exit(
            open_, high, low, close, entry_bar, entry_price, stop_price, target_price, sign, max_bars, n
        )

        gross_return = sign * (exit_price / entry_price - 1.0)
        net_return = gross_return - 2 * cost_rate

        gross_r = sign * (exit_price - entry_price) / r_distance
        cost_r = (2 * cost_rate * entry_price) / r_distance
        net_r = gross_r - cost_r

        records.append(
            {
                "signal_date": bars.index[i],
                "entry_date": bars.index[entry_bar],
                "exit_date": bars.index[exit_bar],
                "side": side,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "exit_price": exit_price,
                "bars_held": exit_bar - entry_bar + 1,
                "exit_reason": exit_reason,
                "r_distance": r_distance,
                "gross_return": gross_return,
                "net_return": net_return,
                "gross_r": gross_r,
                "net_r": net_r,
                "skipped": False,
            }
        )

        i = exit_bar + 1

    trades = pd.DataFrame.from_records(records)

    if both_sides_fired:
        trades.attrs["both_sides_fired"] = both_sides_fired

    return SwingBracketResult(trades=trades, n_skipped=n_skipped, _bars=bars)


def _skip_record(signal_date, side: str, entry_price: float, stop_price: float) -> dict:
    return {
        "signal_date": signal_date,
        "entry_date": pd.NaT,
        "exit_date": pd.NaT,
        "side": side,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": np.nan,
        "exit_price": np.nan,
        "bars_held": 0,
        "exit_reason": "skipped_wrong_side_stop",
        "r_distance": np.nan,
        "gross_return": np.nan,
        "net_return": np.nan,
        "gross_r": np.nan,
        "net_r": np.nan,
        "skipped": True,
    }


def _resolve_exit(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    entry_bar: int,
    entry_price: float,
    stop_price: float,
    target_price: float,
    sign: float,
    max_bars: int,
    n: int,
) -> tuple[int, float, str]:
    max_j = min(entry_bar + max_bars - 1, n - 1)
    j = entry_bar
    while j <= max_j:
        bar_open = entry_price if j == entry_bar else open_[j]

        hit_target = (high[j] >= target_price) if sign > 0 else (low[j] <= target_price)
        hit_stop = (low[j] <= stop_price) if sign > 0 else (high[j] >= stop_price)
        gapped_through_stop = (bar_open <= stop_price) if sign > 0 else (bar_open >= stop_price)

        if hit_stop and gapped_through_stop:
            return j, bar_open, "stop_gap"
        if hit_stop:
            return j, stop_price, "stop"
        if hit_target:
            return j, target_price, "take_profit"
        if j == max_j:
            return j, close[j], "time_exit"
        j += 1

    return max_j, close[max_j], "time_exit"


def _validate(bars: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("bars index must be sorted ascending")
