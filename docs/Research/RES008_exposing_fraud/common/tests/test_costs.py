"""Cost-charging checks for run_positions: turnover-proportional, on the execution bar only."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_positions
from common.tests.conftest import make_random_bars


def _total_cost_paid(bars, target, cost_bps, execution="next_open"):
    result = run_positions(bars, target, cost_bps=cost_bps, execution=execution)
    return float((result.gross_daily_returns - result.daily_returns).sum())


def test_flat_long_flat_pays_exactly_two_times_cost():
    bars = make_random_bars(n=6, seed=10)
    target = pd.Series([0, 1, 1, 0, 0, 0], index=bars.index, dtype=float)
    cost_bps = 10.0
    total_cost = _total_cost_paid(bars, target, cost_bps)
    np.testing.assert_allclose(total_cost, 2 * cost_bps / 10_000.0, atol=1e-12)


def test_long_to_short_flip_pays_two_times_cost_on_one_bar():
    # target[0] = 1 is already pending at t=0, so the position goes flat->long
    # executing at t=1 (cost there); the long->short flip is decided at
    # close(3) and executes at t=4 (cost there); t=2,3,5 have zero turnover.
    bars = make_random_bars(n=6, seed=11)
    target = pd.Series([1, 1, 1, -1, -1, -1], index=bars.index, dtype=float)
    cost_bps = 15.0
    result = run_positions(bars, target, cost_bps=cost_bps, execution="next_open")

    per_bar_cost = result.gross_daily_returns - result.daily_returns
    flip_bar_cost = per_bar_cost.iloc[4]
    np.testing.assert_allclose(flip_bar_cost, 2 * cost_bps / 10_000.0, atol=1e-12)

    other_bars_cost = per_bar_cost.drop(per_bar_cost.index[[1, 4]])
    np.testing.assert_allclose(other_bars_cost.to_numpy(), 0.0, atol=1e-12)
    np.testing.assert_allclose(per_bar_cost.iloc[1], cost_bps / 10_000.0, atol=1e-12)


def test_zero_trade_series_pays_zero_cost():
    bars = make_random_bars(n=20, seed=12)
    target = pd.Series(0.0, index=bars.index)
    cost_bps = 25.0
    total_cost = _total_cost_paid(bars, target, cost_bps)
    np.testing.assert_allclose(total_cost, 0.0, atol=1e-12)


def test_always_long_pays_zero_cost_after_initial_entry():
    bars = make_random_bars(n=20, seed=13)
    target = pd.Series(1.0, index=bars.index)
    cost_bps = 25.0
    result = run_positions(bars, target, cost_bps=cost_bps, execution="next_open")
    per_bar_cost = result.gross_daily_returns - result.daily_returns

    np.testing.assert_allclose(per_bar_cost.iloc[1], cost_bps / 10_000.0, atol=1e-12)
    np.testing.assert_allclose(per_bar_cost.iloc[2:].to_numpy(), 0.0, atol=1e-12)
