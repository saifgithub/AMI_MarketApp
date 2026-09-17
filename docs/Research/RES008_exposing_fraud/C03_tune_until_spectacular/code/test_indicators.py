"""
Tests for `indicators.py`: causality (truncation invariance), and known
closed-form behaviour on synthetic series (monotone RSI, trending/reversing
SuperTrend, ADX range).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indicators import adx, atr, rsi, supertrend


def _make_random_bars(n: int, seed: int, start_price: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.02, size=n)
    close = start_price * np.cumprod(1.0 + rets)
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0, 0.01, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0, 0.01, size=n))
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def _make_trend_bars(n: int, daily_ret: float, start_price: float = 100.0) -> pd.DataFrame:
    t = np.arange(n)
    close = start_price * (1.0 + daily_ret) ** t
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def _corrupt_after(bars: pd.DataFrame, t_idx: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    corrupted = bars.copy()
    n_after = len(bars) - (t_idx + 1)
    if n_after <= 0:
        return corrupted
    junk = rng.uniform(0.3, 3.0, size=n_after)
    for col in ("open", "high", "low", "close"):
        corrupted.iloc[t_idx + 1 :, corrupted.columns.get_loc(col)] = (
            corrupted.iloc[t_idx + 1 :][col].to_numpy() * junk
        )
    cols = ["open", "high", "low", "close"]
    corrupted.iloc[t_idx + 1 :, [corrupted.columns.get_loc(c) for c in cols]]
    corrupted.loc[corrupted.index[t_idx + 1 :], "high"] = corrupted.loc[
        corrupted.index[t_idx + 1 :], ["open", "high", "low", "close"]
    ].max(axis=1)
    corrupted.loc[corrupted.index[t_idx + 1 :], "low"] = corrupted.loc[
        corrupted.index[t_idx + 1 :], ["open", "high", "low", "close"]
    ].min(axis=1)
    return corrupted


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_atr_causal(seed):
    bars = _make_random_bars(120, seed=seed)
    t = 60
    baseline = atr(bars, period=14)
    corrupted = atr(_corrupt_after(bars, t, seed=seed + 100), period=14)
    pd.testing.assert_series_equal(baseline.iloc[: t + 1], corrupted.iloc[: t + 1])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_rsi_causal(seed):
    bars = _make_random_bars(120, seed=seed)
    t = 60
    baseline = rsi(bars["close"], period=14)
    corrupted = rsi(_corrupt_after(bars, t, seed=seed + 100)["close"], period=14)
    pd.testing.assert_series_equal(baseline.iloc[: t + 1], corrupted.iloc[: t + 1])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_adx_causal(seed):
    bars = _make_random_bars(120, seed=seed)
    t = 60
    baseline = adx(bars, period=14)
    corrupted = adx(_corrupt_after(bars, t, seed=seed + 100), period=14)
    pd.testing.assert_frame_equal(baseline.iloc[: t + 1], corrupted.iloc[: t + 1])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_supertrend_causal(seed):
    bars = _make_random_bars(150, seed=seed)
    t = 80
    baseline = supertrend(bars, atr_period=10, multiplier=3.0)
    corrupted = supertrend(_corrupt_after(bars, t, seed=seed + 100), atr_period=10, multiplier=3.0)
    pd.testing.assert_frame_equal(baseline.iloc[: t + 1], corrupted.iloc[: t + 1])


def test_rsi_strictly_rising_is_100():
    bars = _make_trend_bars(60, daily_ret=0.01)
    values = rsi(bars["close"], period=14)
    tail = values.iloc[20:]
    assert np.allclose(tail.to_numpy(), 100.0)


def test_supertrend_long_throughout_steady_uptrend():
    bars = _make_trend_bars(150, daily_ret=0.006)
    result = supertrend(bars, atr_period=10, multiplier=3.0)
    tail_trend = result["trend"].iloc[30:]
    assert (tail_trend == 1).all()


def test_supertrend_flips_on_sharp_sustained_reversal():
    up = _make_trend_bars(100, daily_ret=0.01, start_price=100.0)
    down_start = up["close"].iloc[-1]
    down = _make_trend_bars(60, daily_ret=-0.03, start_price=down_start)
    down.index = pd.bdate_range(up.index[-1] + pd.Timedelta(days=1), periods=len(down))
    bars = pd.concat([up, down])

    result = supertrend(bars, atr_period=10, multiplier=3.0)
    pre_reversal = result["trend"].iloc[60:100]
    assert (pre_reversal == 1).all()

    post_reversal = result["trend"].iloc[-10:]
    assert (post_reversal == -1).all()


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_adx_in_range(seed):
    bars = _make_random_bars(200, seed=seed)
    values = adx(bars, period=14)["adx"].dropna()
    assert (values >= 0).all()
    assert (values <= 100).all()


def test_adx_in_range_on_trend():
    bars = _make_trend_bars(100, daily_ret=0.01)
    values = adx(bars, period=14)["adx"].dropna()
    assert (values >= 0).all()
    assert (values <= 100).all()
