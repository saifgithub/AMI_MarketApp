"""
run_brackets exit-priority checks: TP-only, SL-only, both-in-one-bar (stop
wins), gap-through-stop (fills at open, worse than the nominal stop), and
time exit. Entry is always at open(1) after a signal at bar 0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_brackets

_DATES = pd.date_range("2022-01-01", periods=8, freq="B")
_ENTRIES = pd.Series([True] + [False] * 7, index=_DATES)


def _bars(open_, high, low, close) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": [1000] * 8},
        index=_DATES,
    )


def test_take_profit_only_hit():
    open_ = [100, 100, 103, 104, 105, 106, 107, 108]
    high = [100, 101, 106, 104, 105, 106, 107, 108]
    low = [100, 99, 100, 103, 104, 105, 106, 107]
    close = [100, 100, 104, 103, 104, 105, 106, 107]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=5, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    np.testing.assert_allclose(trade["entry_price"], 100.0)
    np.testing.assert_allclose(trade["exit_price"], 105.0)
    np.testing.assert_allclose(trade["net_return"], 0.05)


def test_stop_loss_only_hit():
    open_ = [100, 100, 99, 100, 100, 100, 100, 100]
    high = [100, 101, 99.5, 100, 100, 100, 100, 100]
    low = [100, 99, 96, 99, 100, 100, 100, 100]
    close = [100, 100, 97, 100, 100, 100, 100, 100]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=5, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop"
    np.testing.assert_allclose(trade["exit_price"], 97.0)
    np.testing.assert_allclose(trade["net_return"], -0.03)


def test_both_tp_and_sl_in_same_bar_assumes_stop_first():
    open_ = [100, 100, 99, 100, 100, 100, 100, 100]
    high = [100, 101, 110, 100, 100, 100, 100, 100]
    low = [100, 99, 95, 99, 100, 100, 100, 100]
    close = [100, 100, 102, 100, 100, 100, 100, 100]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=5, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop"
    np.testing.assert_allclose(trade["exit_price"], 97.0)


def test_gap_through_stop_fills_at_open_worse_than_stop():
    open_ = [100, 100, 90, 100, 100, 100, 100, 100]
    high = [100, 101, 91, 100, 100, 100, 100, 100]
    low = [100, 99, 88, 99, 100, 100, 100, 100]
    close = [100, 100, 90, 100, 100, 100, 100, 100]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=5, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_gap"
    np.testing.assert_allclose(trade["exit_price"], 90.0)
    nominal_stop_price = 100.0 * (1 - 0.03)
    assert trade["exit_price"] < nominal_stop_price


def test_time_exit_when_neither_level_hit():
    open_ = [100, 100, 100.5, 100.8, 101, 101.2, 100, 100]
    high = [100, 101, 101, 101.3, 101.5, 101.7, 100, 100]
    low = [100, 99, 100, 100.5, 100.8, 101, 100, 100]
    close = [100, 100, 100.8, 101, 101.2, 101.4, 100, 100]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=4, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "time_exit"
    assert trade["bars_held"] == 4
    np.testing.assert_allclose(trade["exit_price"], close[4])


def test_signal_ignored_while_position_open():
    open_ = [100, 100, 100.5, 100.8, 101, 101.2, 100, 100]
    high = [100, 101, 101, 101.3, 101.5, 101.7, 100, 100]
    low = [100, 99, 100, 100.5, 100.8, 101, 100, 100]
    close = [100, 100, 100.8, 101, 101.2, 101.4, 100, 100]
    bars = _bars(open_, high, low, close)
    entries = pd.Series([True, True, True, False, False, False, False, False], index=_DATES)

    result = run_brackets(
        bars, entries, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=4, cost_bps=0, side="long"
    )

    assert len(result.trades) == 1


def test_brackets_pay_cost_on_entry_and_exit():
    open_ = [100, 100, 103, 104, 105, 106, 107, 108]
    high = [100, 101, 106, 104, 105, 106, 107, 108]
    low = [100, 99, 100, 103, 104, 105, 106, 107]
    close = [100, 100, 104, 103, 104, 105, 106, 107]
    bars = _bars(open_, high, low, close)

    result = run_brackets(
        bars, _ENTRIES, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=5, cost_bps=10, side="long"
    )

    trade = result.trades.iloc[0]
    np.testing.assert_allclose(trade["net_return"], trade["gross_return"] - 2 * 10 / 10_000.0)
