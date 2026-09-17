"""
Tests for `rsi_rule.py`: RSI causality (truncation invariance), RSI of a
strictly rising series -> 100, and the long/flat state machine on a
hand-built RSI path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rsi_rule import rsi, rsi_state_machine


def _make_random_bars(n: int, seed: int, start_price: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.02, size=n)
    close = start_price * np.cumprod(1.0 + rets)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"close": close}, index=idx)


def _make_trend_bars(n: int, daily_ret: float, start_price: float = 100.0) -> pd.DataFrame:
    t = np.arange(n)
    close = start_price * (1.0 + daily_ret) ** t
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"close": close}, index=idx)


def _corrupt_after(close: pd.Series, t_idx: int, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    corrupted = close.copy()
    n_after = len(close) - (t_idx + 1)
    if n_after <= 0:
        return corrupted
    junk = rng.uniform(0.3, 3.0, size=n_after)
    corrupted.iloc[t_idx + 1 :] = corrupted.iloc[t_idx + 1 :].to_numpy() * junk
    return corrupted


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_rsi_causal_by_truncation(seed):
    bars = _make_random_bars(120, seed=seed)
    t = 60
    baseline = rsi(bars["close"], period=14)
    corrupted = rsi(_corrupt_after(bars["close"], t, seed=seed + 100), period=14)
    pd.testing.assert_series_equal(baseline.iloc[: t + 1], corrupted.iloc[: t + 1])


def test_rsi_strictly_rising_is_100():
    bars = _make_trend_bars(60, daily_ret=0.01)
    values = rsi(bars["close"], period=14)
    tail = values.iloc[20:]
    assert np.allclose(tail.to_numpy(), 100.0)


def test_state_machine_hand_built_rsi_path():
    idx = pd.bdate_range("2020-01-01", periods=10)
    # Hand-built RSI path exercising: warmup NaN, flat->long on <30, hold
    # through the middle band, long->flat on >70, hold flat, and a second
    # flat->long entry near the end.
    rsi_path = pd.Series(
        [np.nan, np.nan, 25.0, 40.0, 60.0, 75.0, 50.0, 20.0, 20.0, 71.0],
        index=idx,
    )
    state = rsi_state_machine(rsi_path)
    expected = pd.Series(
        [0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0],
        index=idx,
        name="target_position",
    )
    pd.testing.assert_series_equal(state, expected)


def test_state_machine_boundary_values_do_not_trigger():
    idx = pd.bdate_range("2020-01-01", periods=4)
    # Exactly 30 and exactly 70 are NOT strict inequalities, so neither
    # should trigger a transition (flat stays flat, long stays long).
    rsi_path = pd.Series([30.0, 30.0, 29.9, 70.0], index=idx)
    state = rsi_state_machine(rsi_path)
    expected = pd.Series([0.0, 0.0, 1.0, 1.0], index=idx, name="target_position")
    pd.testing.assert_series_equal(state, expected)


def test_state_machine_starts_flat_and_long_flat_only():
    idx = pd.bdate_range("2020-01-01", periods=5)
    rsi_path = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0], index=idx)
    state = rsi_state_machine(rsi_path)
    assert state.iloc[0] == 0.0
    assert set(state.unique().tolist()) <= {0.0, 1.0}
