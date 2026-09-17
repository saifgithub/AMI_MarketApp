"""
EXPLORATORY -- not pre-registered; written and run after the pre-registered
results were seen.

Tests for `posthoc_placebo.py`'s new logic: the distance-matched rejection
rule (`min_stop_dist_pct`), and that `run_placebo_replications_ext` still
agrees with the pre-registered `placebo_swing.run_placebo_replications` on
R-normalised win/expectancy when no floor is applied (same seed, same
draws) -- the extended per-trade bookkeeping must not silently change the
numbers the pre-registered pipeline already reported.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.data import load_daily

from placebo_swing import run_placebo_replications
from posthoc_placebo import _stop_dist_pct_for_signal, run_placebo_replications_ext


@pytest.fixture(scope="module")
def spy_bars() -> pd.DataFrame:
    return load_daily(["SPY"], "2015-01-01", "2020-12-31")["SPY"]


def test_ext_matches_original_placebo_with_no_floor(spy_bars):
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    close = spy_bars["close"].to_numpy(dtype=float)

    kwargs = dict(
        open_=open_, high=high, low=low, close=close,
        n_trades=40, n_long=20, target_r=1.5, cost_rate=0.0005,
        max_bars=60, lookback=10, n_reps=50, seed=123,
    )
    original = run_placebo_replications(**kwargs)
    extended = run_placebo_replications_ext(**kwargs, min_stop_dist_pct=None)

    np.testing.assert_array_equal(original["win_count"], extended["win_count"])
    np.testing.assert_array_equal(original["n_realised"], extended["n_realised"])
    np.testing.assert_allclose(original["sum_net_r"], extended["sum_net_r"])
    np.testing.assert_allclose(original["sum_gross_r"], extended["sum_gross_r"])
    assert extended["n_floor_exhausted"] == 0


def test_distance_matched_floor_never_returns_a_trade_below_floor(spy_bars):
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    close = spy_bars["close"].to_numpy(dtype=float)

    floor = 0.02
    result = run_placebo_replications_ext(
        open_=open_, high=high, low=low, close=close,
        n_trades=15, n_long=8, target_r=1.5, cost_rate=0.0005,
        max_bars=60, lookback=10, n_reps=30, seed=7,
        min_stop_dist_pct=floor,
    )
    stop_dists = result["stop_dist_pcts"]
    assert len(stop_dists) > 0
    below_floor = stop_dists < floor
    n_below = int(below_floor.sum())
    # Every below-floor trade realised must correspond to a floor-exhausted
    # placement (the only path that can accept a sub-floor draw).
    assert n_below <= result["n_floor_exhausted"]


def test_distance_matched_floor_raises_median_stop_distance(spy_bars):
    """A binding floor should make the realised stop distances larger on
    average than with no floor at all, on the same draws otherwise."""
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    close = spy_bars["close"].to_numpy(dtype=float)

    unfloored = run_placebo_replications_ext(
        open_=open_, high=high, low=low, close=close,
        n_trades=30, n_long=15, target_r=1.5, cost_rate=0.0005,
        max_bars=60, lookback=10, n_reps=80, seed=99,
        min_stop_dist_pct=None,
    )
    floored = run_placebo_replications_ext(
        open_=open_, high=high, low=low, close=close,
        n_trades=30, n_long=15, target_r=1.5, cost_rate=0.0005,
        max_bars=60, lookback=10, n_reps=80, seed=99,
        min_stop_dist_pct=0.03,
    )
    assert np.median(floored["stop_dist_pcts"]) >= np.median(unfloored["stop_dist_pcts"])


def test_stop_dist_pct_for_signal_matches_manual_computation(spy_bars):
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    n = len(spy_bars)

    signal_bar = 500
    dist = _stop_dist_pct_for_signal(open_, high, low, signal_bar, side_is_long=True, lookback=10, n=n)
    entry_price = open_[signal_bar + 1]
    expected_stop = float(np.min(low[signal_bar - 9 : signal_bar + 1]))
    expected = abs(entry_price - expected_stop) / entry_price
    assert dist == pytest.approx(expected)


def test_stop_dist_pct_for_signal_none_at_series_end(spy_bars):
    n = len(spy_bars)
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    dist = _stop_dist_pct_for_signal(open_, high, low, n - 1, side_is_long=True, lookback=10, n=n)
    assert dist is None
