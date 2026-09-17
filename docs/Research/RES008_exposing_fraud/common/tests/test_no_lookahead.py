"""
The point of this library: nothing computed through date d may depend on
bars strictly after d. Corrupting the future and recomputing must leave the
past bit-identical, for every execution mode.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.backtest import run_brackets, run_positions
from common.tests.conftest import make_random_bars


def _corrupt_after(bars: pd.DataFrame, d: pd.Timestamp, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    corrupted = bars.copy()
    mask = corrupted.index > d
    n = mask.sum()
    junk = rng.uniform(0.2, 5.0, size=n)
    for col in ("open", "high", "low", "close"):
        corrupted.loc[mask, col] = corrupted.loc[mask, col].to_numpy() * junk
    corrupted.loc[mask, "high"] = corrupted.loc[mask, ["open", "high", "low", "close"]].max(axis=1)
    corrupted.loc[mask, "low"] = corrupted.loc[mask, ["open", "high", "low", "close"]].min(axis=1)
    return corrupted


def _random_target_position(bars: pd.DataFrame, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    values = rng.choice([-1.0, 0.0, 1.0], size=len(bars))
    return pd.Series(values, index=bars.index)


def test_no_lookahead_next_open():
    bars = make_random_bars(n=80, seed=1)
    target = _random_target_position(bars, seed=2)
    d = bars.index[40]

    baseline = run_positions(bars, target, cost_bps=5, execution="next_open")
    corrupted_bars = _corrupt_after(bars, d, seed=99)
    corrupted = run_positions(corrupted_bars, target, cost_bps=5, execution="next_open")

    up_to_d = bars.index <= d
    pd.testing.assert_series_equal(
        baseline.daily_returns[up_to_d], corrupted.daily_returns[up_to_d]
    )
    pd.testing.assert_series_equal(
        baseline.gross_daily_returns[up_to_d], corrupted.gross_daily_returns[up_to_d]
    )
    pd.testing.assert_series_equal(
        baseline.positions_held[up_to_d], corrupted.positions_held[up_to_d]
    )


def test_no_lookahead_same_close():
    bars = make_random_bars(n=80, seed=3)
    target = _random_target_position(bars, seed=4)
    d = bars.index[40]

    baseline = run_positions(bars, target, cost_bps=5, execution="same_close")
    corrupted_bars = _corrupt_after(bars, d, seed=98)
    corrupted = run_positions(corrupted_bars, target, cost_bps=5, execution="same_close")

    up_to_d = bars.index <= d
    pd.testing.assert_series_equal(
        baseline.daily_returns[up_to_d], corrupted.daily_returns[up_to_d]
    )
    pd.testing.assert_series_equal(
        baseline.positions_held[up_to_d], corrupted.positions_held[up_to_d]
    )


def test_no_lookahead_run_brackets():
    bars = make_random_bars(n=100, seed=5)
    rng = np.random.default_rng(6)
    entries = pd.Series(rng.random(len(bars)) < 0.15, index=bars.index)
    d = bars.index[50]

    baseline = run_brackets(
        bars, entries, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=10, cost_bps=5, side="long"
    )
    corrupted_bars = _corrupt_after(bars, d, seed=97)
    corrupted = run_brackets(
        corrupted_bars, entries, take_profit_pct=0.05, stop_loss_pct=0.03, max_bars=10, cost_bps=5, side="long"
    )

    up_to_d = bars.index <= d
    pd.testing.assert_series_equal(
        baseline.daily_returns[up_to_d], corrupted.daily_returns[up_to_d]
    )
    pd.testing.assert_series_equal(
        baseline.positions_held[up_to_d], corrupted.positions_held[up_to_d]
    )

    trades_before = baseline.trades[baseline.trades["exit_date"] <= d]
    trades_before_corrupted = corrupted.trades[corrupted.trades["exit_date"] <= d]
    pd.testing.assert_frame_equal(
        trades_before.reset_index(drop=True), trades_before_corrupted.reset_index(drop=True)
    )
