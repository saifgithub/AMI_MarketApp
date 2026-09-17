"""
Hand-computed 6-bar timing checks for `run_positions`.

Bars (index 0..5):
    close = [100, 102, 104, 103, 106, 108]
    open  = [100, 101, 103, 105, 104, 107]

target_position = [0, 0, 1, 1, 1, 1] -- i.e. a signal observed at the CLOSE
of bar 2 flips the target from 0 to 1.

For next_open, execution happens at open(3): the position is flat through
close(2)->open(3) and then long open(3)->close(3). The critical assertion
this guards is that bar 3's return must NOT be close(2)->close(3) (which
would silently include the close(1)->close(2) move that produced the
signal, i.e. look-ahead) -- it must be exactly open(3)->close(3), since the
old (flat) position earns the close(2)->open(3) leg and contributes zero.

For same_close, execution happens at close(2) itself: the new position
earns close(2)->close(3), one full bar later than next_open's economic
exposure begins, because there is no explicit open-price leg to split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_positions

_CLOSE = [100, 102, 104, 103, 106, 108]
_OPEN = [100, 101, 103, 105, 104, 107]


def _bars() -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", periods=6, freq="B")
    return pd.DataFrame(
        {
            "open": _OPEN,
            "high": np.maximum(_OPEN, _CLOSE),
            "low": np.minimum(_OPEN, _CLOSE),
            "close": _CLOSE,
            "volume": [1000] * 6,
        },
        index=dates,
    )


def _target() -> pd.Series:
    bars = _bars()
    return pd.Series([0, 0, 1, 1, 1, 1], index=bars.index, dtype=float)


def test_next_open_hand_computed():
    bars = _bars()
    target = _target()
    result = run_positions(bars, target, cost_bps=0.0, execution="next_open")

    expected = [
        0.0,
        0.0,
        0.0,
        _CLOSE[3] / _OPEN[3] - 1.0,  # execution bar: flat leg (0) + long open(3)->close(3)
        _CLOSE[4] / _CLOSE[3] - 1.0,
        _CLOSE[5] / _CLOSE[4] - 1.0,
    ]
    np.testing.assert_allclose(result.daily_returns.to_numpy(), expected, atol=1e-12)
    np.testing.assert_allclose(result.positions_held.to_numpy(), [0, 0, 0, 1, 1, 1], atol=1e-12)


def test_next_open_signal_excludes_prior_close_to_close_move():
    """A signal at close(t) must not earn the close(t-1) -> close(t) move that produced it."""
    bars = _bars()
    target = _target()
    result = run_positions(bars, target, cost_bps=0.0, execution="next_open")

    naive_lookahead_return = _CLOSE[2] / _CLOSE[1] - 1.0
    assert not np.isclose(result.daily_returns.iloc[3], naive_lookahead_return)


def test_same_close_hand_computed():
    bars = _bars()
    target = _target()
    result = run_positions(bars, target, cost_bps=0.0, execution="same_close")

    expected = [
        0.0,
        0.0,
        0.0,
        _CLOSE[3] / _CLOSE[2] - 1.0,
        _CLOSE[4] / _CLOSE[3] - 1.0,
        _CLOSE[5] / _CLOSE[4] - 1.0,
    ]
    np.testing.assert_allclose(result.daily_returns.to_numpy(), expected, atol=1e-12)
    np.testing.assert_allclose(result.positions_held.to_numpy(), [0, 0, 1, 1, 1, 1], atol=1e-12)


def test_next_open_and_same_close_differ_by_one_bar_of_exposure():
    bars = _bars()
    target = _target()
    next_open = run_positions(bars, target, cost_bps=0.0, execution="next_open")
    same_close = run_positions(bars, target, cost_bps=0.0, execution="same_close")

    assert next_open.positions_held.iloc[2] == 0.0
    assert same_close.positions_held.iloc[2] == 1.0
