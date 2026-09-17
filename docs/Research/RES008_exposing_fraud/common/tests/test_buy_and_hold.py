"""A constant +1 position with zero cost must reproduce buy-and-hold exactly."""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.backtest import run_positions
from common.tests.conftest import make_random_bars


def test_constant_long_position_matches_close_to_close_buy_and_hold():
    bars = make_random_bars(n=50, seed=42)
    target = pd.Series(1.0, index=bars.index)

    result = run_positions(bars, target, cost_bps=0.0, execution="next_open")

    close = bars["close"]
    open_ = bars["open"]

    # target[0]=1 is only known at close(0), so the position cannot be
    # established before open(1) -- bar 1 (the execution bar) earns
    # open(1) -> close(1) only, not the full close(0) -> close(1) move.
    np.testing.assert_allclose(
        result.daily_returns.iloc[1], close.iloc[1] / open_.iloc[1] - 1.0, atol=1e-12
    )

    # From bar 2 onward the position is unchanged (always 1), so each bar's
    # return must reduce exactly to plain close-to-close buy-and-hold.
    expected_returns = close.pct_change().iloc[2:]
    np.testing.assert_allclose(
        result.daily_returns.iloc[2:].to_numpy(),
        expected_returns.to_numpy(),
        atol=1e-12,
    )

    summary = result.summary()
    expected_buy_hold_return = float(close.iloc[-1] / close.iloc[0] - 1.0)
    np.testing.assert_allclose(summary["buy_hold_return"], expected_buy_hold_return, atol=1e-10)

    # Strategy total_return differs from raw buy-and-hold only by the
    # open(1)-vs-close(0) entry-timing gap (position starts one leg later).
    expected_strategy_total_return = float(close.iloc[-1] / open_.iloc[1] - 1.0)
    np.testing.assert_allclose(summary["total_return"], expected_strategy_total_return, atol=1e-10)


def test_constant_long_position_same_close_matches_buy_and_hold_from_bar_zero():
    bars = make_random_bars(n=30, seed=43)
    target = pd.Series(1.0, index=bars.index)

    result = run_positions(bars, target, cost_bps=0.0, execution="same_close")

    close = bars["close"]
    expected_returns = close.pct_change().fillna(0.0)
    np.testing.assert_allclose(
        result.daily_returns.to_numpy(), expected_returns.to_numpy(), atol=1e-12
    )
