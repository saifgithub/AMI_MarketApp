"""
Position- and bracket-based backtest engines for RES008.

The one property every test in `tests/test_no_lookahead.py` exists to defend:
a result computed through date d must not change no matter what happens to
bars strictly after d. Two execution conventions are supported because the
claims being tested use both, and conflating them is itself a common source
of phantom edges:

    next_open (default) — target_position[t] is decided using information
    available at the CLOSE of bar t. The change is executed at the OPEN of
    bar t+1. Timeline for a signal observed at close(t):

        ... close(t-1)   close(t)        open(t+1)   close(t+1) ...
                             |  signal        |            |
                             |  decided       |  filled    |
                    old pos earns this <-------> new pos earns this
                    [close(t-1) -> open(t+1)]   [open(t+1) -> close(t+1)]

    On the execution bar (t+1) P&L is split in two and COMPOUNDED (not
    summed): the OLD position earns close(t) -> open(t+1), then the NEW
    position earns open(t+1) -> close(t+1). Compounding (rather than adding)
    the two legs is what makes an unchanged position's bar return reduce
    exactly to plain close-to-close, matching buy-and-hold when the target
    never changes. This is what makes next-day execution honest — a signal
    at close(t) never earns the close(t-1) -> close(t) move that produced it.

    same_close — decided and filled at close(t); the new position starts
    earning from close(t) onward (i.e. it earns close(t) -> close(t+1)).
    Many tutorials implicitly assume this. It is look-ahead-free only
    because the position is not applied to the bar that produced the signal,
    just cheaper/instant to fill; that instantaneousness is the assumption
    being reproduced "as taught", not endorsed.

Costs are charged in `cost_bps` per unit of absolute position change,
on the bar where the change is executed. A flip from +1 to -1 changes
|position| by 2 and pays 2x cost_bps; a flat->long->flat round trip pays
cost_bps on entry and cost_bps on exit.

No Sharpe ratio anywhere in this module or its outputs — house rule, not an
oversight (see repo README, "Method standard" #5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

_REQUIRED_COLS = ["open", "high", "low", "close"]


def _validate_bars(bars: pd.DataFrame) -> None:
    missing = set(_REQUIRED_COLS) - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("bars index must be sorted ascending")


@dataclass
class BacktestResult:
    daily_returns: pd.Series
    gross_daily_returns: pd.Series
    positions_held: pd.Series
    trades: pd.DataFrame
    _bars: pd.DataFrame = field(repr=False)

    def summary(self) -> dict:
        return _summarize(self)


def _trade_span(start: int, end: int, n: int) -> tuple[int, int]:
    """The (entry_bar, exit_bar) a run start..end actually earns P&L on.

    A run `start..end` in `positions_held` is a maximal same-sign stretch.
    The run's own bars only carry the position's middle life -- economically
    the trade is established AT `start` (already the execution bar in both
    conventions) and unwound at `end + 1`, the bar where `run_positions`
    charged the exit turnover/cost -- unless the run reaches the last bar,
    in which case there is no bar `end + 1` and the trade simply ends at the
    last bar with no exit leg/cost, matching what `run_positions` charged.
    """
    exit_bar = end + 1 if end + 1 < n else n - 1
    return start, exit_bar


def _leg_return(sign: float, entry_price: float, mid_price: float) -> float:
    return sign * (mid_price / entry_price - 1.0)


def _trade_gross_return(
    open_: np.ndarray, close: np.ndarray, start: int, end: int, exit_bar: int, sign: float, execution: str
) -> float:
    """Compound a trade's own per-bar legs exactly as `run_positions` would.

    A constant SHORT position does not compound to a simple
    `sign * (exit_price / entry_price - 1)`: unlike a long, negating a
    price-ratio return and then compounding across many bars is not the
    same as compounding `(1 + sign * (leg_ratio - 1))` bar by bar (there is
    no closed form in the two endpoint prices alone for sign=-1). So this
    replays every bar in the trade's span using the identical leg formula
    `run_positions` uses, rather than taking an entry/exit price shortcut --
    the only way to guarantee `prod(1 + trades.gross_return)` reproduces
    `prod(1 + gross_daily_returns)` for both signs and both conventions.
    """
    growth = 1.0

    if execution == "next_open":
        # Bar `start`: already the execution bar, so the WHOLE bar is priced
        # off the entry (open[start]) rather than split old/new-leg, since
        # there is no "old position" before this trade begins.
        growth *= 1.0 + _leg_return(sign, open_[start], close[start])
        for t in range(start + 1, end + 1):
            leg1 = _leg_return(sign, close[t - 1], open_[t])
            leg2 = _leg_return(sign, open_[t], close[t])
            growth *= (1.0 + leg1) * (1.0 + leg2)
        if exit_bar > end:
            # Old position earns close(end) -> open(exit_bar); the new
            # target's leg on this bar belongs to a DIFFERENT trade.
            growth *= 1.0 + _leg_return(sign, close[end], open_[exit_bar])
    else:
        # same_close: bar `start` is decided+filled at close(start) itself
        # and earns close(start) -> close(start+1) on the FIRST run bar,
        # i.e. the trade's own legs start at bar start+1, not bar start.
        for t in range(start + 1, end + 1):
            growth *= 1.0 + _leg_return(sign, close[t - 1], close[t])
        if exit_bar > end:
            growth *= 1.0 + _leg_return(sign, close[end], close[exit_bar])

    return growth - 1.0


def _extract_trades(
    positions_held: pd.Series,
    bars: pd.DataFrame,
    execution: str,
    cost_rate: float,
) -> pd.DataFrame:
    """Derive a trades table from a realised position series.

    A "trade" is a maximal run of a single non-zero sign in `positions_held`.
    Assumes a constant position size within a run (true for every RES008
    use: positions are drawn from {-1, 0, +1}) -- if size varies inside a
    run, the size at the run's first bar is used and this is a
    simplification, not an exact accounting of a resized position.

    gross_return replays the trade's own per-bar legs (see
    `_trade_gross_return`) so that compounding every trade's net_return
    reproduces `daily_returns` bar for bar, including the exit leg and exit
    cost that a naive "price ratio within the run" reading would drop or
    (for shorts) get algebraically wrong. entry_price/exit_price are
    reported for readability (the prices at the trade's economic entry/exit
    bars) but are not themselves used to derive gross_return.
    net_return subtracts `cost_rate` once for opening and once for closing
    (a flip closes one trade and opens another on the same bar, so each
    trade carries exactly its own 1 unit of open + 1 unit of close cost) --
    except when the run reaches the last bar, where there is no exit
    bar/cost to charge, matching what `run_positions` actually charged.
    """
    records = []
    idx = positions_held.index
    signs = np.sign(positions_held.to_numpy())
    pos_units = np.abs(positions_held.to_numpy())
    open_ = bars["open"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    n = len(signs)
    i = 0
    while i < n:
        if signs[i] == 0:
            i += 1
            continue
        side_sign = float(signs[i])
        start = i
        while i < n and signs[i] == side_sign:
            i += 1
        end = i - 1

        units = float(pos_units[start])
        entry_bar, exit_bar = _trade_span(start, end, n)
        entry_price = float(open_[entry_bar] if execution == "next_open" else close[entry_bar])
        exit_price = float(open_[exit_bar] if execution == "next_open" else close[exit_bar])

        gross_return = _trade_gross_return(open_, close, start, end, exit_bar, side_sign, execution)

        closes_within_series = exit_bar > end
        units_opened = units
        units_closed = units if closes_within_series else 0.0
        cost = cost_rate * (units_opened + units_closed)
        net_return = gross_return - cost

        records.append(
            {
                "entry_date": idx[start],
                "exit_date": idx[exit_bar],
                "side": "long" if side_sign > 0 else "short",
                "entry_price": entry_price,
                "exit_price": exit_price,
                "bars_held": end - start + 1,
                "gross_return": gross_return,
                "net_return": net_return,
            }
        )

    return pd.DataFrame(
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
        ],
    )


def run_positions(
    bars: pd.DataFrame,
    target_position: pd.Series,
    cost_bps: float,
    execution: str = "next_open",
) -> BacktestResult:
    """Backtest a target-position series against OHLC bars.

    `target_position[t]` in [-1, 1] must be decided from information known
    at the close of bar t (the caller's responsibility — this function does
    not shift anything for you beyond applying the chosen execution rule).
    """
    _validate_bars(bars)
    if execution not in ("next_open", "same_close"):
        raise ValueError(f"unknown execution {execution!r}")

    target = target_position.reindex(bars.index).ffill().fillna(0.0)
    n = len(bars)

    close = bars["close"].to_numpy(dtype=float)
    open_ = bars["open"].to_numpy(dtype=float)
    target_arr = target.to_numpy(dtype=float)

    gross = np.zeros(n)
    net = np.zeros(n)
    held = np.zeros(n)
    cost_rate = cost_bps / 10_000.0

    if execution == "same_close":
        # Position decided+filled at close(t) earns close(t) -> close(t+1).
        # held[t] is the position earning the bar-t return realized at close(t).
        prev_pos = 0.0
        for t in range(n):
            pos_active_this_bar = prev_pos
            if t == 0:
                bar_gross = 0.0
            else:
                bar_gross = pos_active_this_bar * (close[t] / close[t - 1] - 1.0)
            new_pos = target_arr[t]
            turnover = abs(new_pos - prev_pos)
            cost = turnover * cost_rate
            gross[t] = bar_gross
            net[t] = bar_gross - cost
            held[t] = new_pos
            prev_pos = new_pos
    else:
        # next_open: target decided at close(t) is executed at open(t+1).
        # On bar t+1: old position earns close(t) -> open(t+1), new position
        # earns open(t+1) -> close(t+1). The two legs are COMPOUNDED into one
        # bar-t+1 return, not summed (see below).
        prev_pos = 0.0
        pending_target = None  # target decided at close(t-1), to be executed at open(t)
        for t in range(n):
            old_pos = prev_pos
            if t == 0:
                gross[t] = 0.0
                net[t] = 0.0
                held[t] = old_pos
                pending_target = target_arr[t]
                continue

            new_pos = pending_target if pending_target is not None else old_pos

            leg1 = old_pos * (open_[t] / close[t - 1] - 1.0)
            leg2 = new_pos * (close[t] / open_[t] - 1.0)
            # Compounded, not summed: leg1 and leg2 are sequential sub-period
            # returns of the SAME bar (old position until the open, new
            # position after it). Summing them would only match compounding
            # when one leg is zero (i.e. old_pos == 0 or new_pos == 0), and
            # would otherwise understate/overstate a fully-held position's
            # return relative to plain close-to-close -- which must match
            # buy-and-hold exactly when the position never changes.
            bar_gross = (1.0 + leg1) * (1.0 + leg2) - 1.0

            turnover = abs(new_pos - old_pos)
            cost = turnover * cost_rate

            gross[t] = bar_gross
            net[t] = bar_gross - cost
            held[t] = new_pos

            prev_pos = new_pos
            pending_target = target_arr[t]

    gross_daily_returns = pd.Series(gross, index=bars.index, name="gross_daily_returns")
    net_daily_returns = pd.Series(net, index=bars.index, name="daily_returns")
    positions_held = pd.Series(held, index=bars.index, name="positions_held")

    trades = _extract_trades(positions_held, bars, execution, cost_rate)

    return BacktestResult(
        daily_returns=net_daily_returns,
        gross_daily_returns=gross_daily_returns,
        positions_held=positions_held,
        trades=trades,
        _bars=bars,
    )


def _summarize(result: BacktestResult) -> dict:
    bars = result._bars
    net = result.daily_returns
    held = result.positions_held
    trades = result.trades

    total_return = float((1.0 + net).prod() - 1.0)

    close = bars["close"]
    buy_hold_return = float(close.iloc[-1] / close.iloc[0] - 1.0) if len(close) > 1 else 0.0

    n_trades = len(trades)
    if n_trades > 0:
        wins = trades[trades["net_return"] > 0]
        losses = trades[trades["net_return"] <= 0]
        win_rate = len(wins) / n_trades
        avg_win = float(wins["net_return"].mean()) if len(wins) else 0.0
        avg_loss = float(losses["net_return"].mean()) if len(losses) else 0.0
        payoff_ratio = float(avg_win / abs(avg_loss)) if avg_loss != 0 else float("nan")
        gross_profit = float(wins["net_return"].sum()) if len(wins) else 0.0
        gross_loss = float(-losses["net_return"].sum()) if len(losses) else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss != 0 else float("nan")
        expectancy_per_trade = float(trades["net_return"].mean())
    else:
        win_rate = float("nan")
        avg_win = float("nan")
        avg_loss = float("nan")
        payoff_ratio = float("nan")
        profit_factor = float("nan")
        expectancy_per_trade = float("nan")

    equity = (1.0 + net).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0

    exposure = float((held != 0).mean()) if len(held) else 0.0

    return {
        "total_return": total_return,
        "buy_hold_return": buy_hold_return,
        "n_trades": n_trades,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff_ratio,
        "profit_factor": profit_factor,
        "expectancy_per_trade": expectancy_per_trade,
        "max_drawdown": max_drawdown,
        "exposure": exposure,
    }


def run_brackets(
    bars: pd.DataFrame,
    entries: pd.Series,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_bars: int,
    cost_bps: float,
    side: str = "long",
) -> BacktestResult:
    """Backtest fixed take-profit/stop-loss brackets triggered by `entries`.

    `entries` is a boolean Series (or a Series of side strings/signs, one
    entry signal per bar) aligned to `bars.index`; a truthy value at bar i
    means "signal observed at close of bar i". Entry fills at open(i+1).
    Exits are evaluated bar by bar from the entry bar onward using each
    bar's high/low: if both the take-profit and stop-loss levels are inside
    the SAME bar's [low, high] range, the STOP is assumed to trigger first
    (the conservative assumption — we cannot know intrabar path order from
    daily/intraday OHLC alone, and assuming the friendlier outcome would
    flatter every strategy tested here). A gap that opens through the stop
    level fills at that bar's open (worse than the nominal stop price), not
    at the stop price itself. If neither level is touched within `max_bars`
    bars of the entry bar, the position is closed at that bar's close.

    Only one position is open at a time; entry signals arriving while a
    position is open are ignored.
    """
    _validate_bars(bars)
    if "low" not in bars.columns or "high" not in bars.columns:
        raise ValueError("bars must include 'high' and 'low' for bracket exits")
    if side not in ("long", "short"):
        raise ValueError(f"unknown side {side!r}")

    n = len(bars)
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    signal = entries.reindex(bars.index).fillna(False)
    if signal.dtype != bool:
        signal = signal.astype(bool)
    signal_arr = signal.to_numpy()

    cost_rate = cost_bps / 10_000.0
    sign = 1.0 if side == "long" else -1.0

    held = np.zeros(n)
    gross = np.zeros(n)
    net = np.zeros(n)
    records = []

    i = 0
    while i < n - 1:
        if not signal_arr[i]:
            i += 1
            continue

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
