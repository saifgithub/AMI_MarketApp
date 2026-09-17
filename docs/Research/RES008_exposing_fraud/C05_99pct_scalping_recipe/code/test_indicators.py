"""
Tests for `indicators.py`: causality by truncation, UT Bot stop-ratchet
monotonicity, STC range, and a hand-computed 8-bar UT Bot example.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators import atr, stc, ut_bot


def _make_random_bars(n: int, seed: int, start_price: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0003, 0.015, size=n)
    close = start_price * np.cumprod(1.0 + rets)
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0, 0.01, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0, 0.01, size=n))
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def test_atr_causal_by_truncation():
    bars = _make_random_bars(300, seed=1)
    full = atr(bars, period=14)
    for cut in (50, 100, 200):
        truncated = atr(bars.iloc[:cut], period=14)
        pd.testing.assert_series_equal(full.iloc[:cut], truncated, check_names=False)


def test_atr_period_1_equals_true_range():
    bars = _make_random_bars(50, seed=2)
    high = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    close = bars["close"].to_numpy()
    tr = np.empty(len(bars))
    tr[0] = high[0] - low[0]
    for t in range(1, len(bars)):
        tr[t] = max(high[t] - low[t], abs(high[t] - close[t - 1]), abs(low[t] - close[t - 1]))
    got = atr(bars, period=1).to_numpy()
    np.testing.assert_allclose(got, tr)


def test_ut_bot_causal_by_truncation():
    bars = _make_random_bars(300, seed=3)
    full = ut_bot(bars, key=2.0, atr_period=6)
    for cut in (50, 120, 250):
        truncated = ut_bot(bars.iloc[:cut], key=2.0, atr_period=6)
        pd.testing.assert_frame_equal(full.iloc[:cut], truncated, check_names=False)


def test_ut_bot_v2_instances_causal_by_truncation():
    bars = _make_random_bars(400, seed=4)
    full_buy = ut_bot(bars, key=2.0, atr_period=1)
    full_sell = ut_bot(bars, key=2.0, atr_period=300)
    for cut in (310, 350, 399):
        trunc_buy = ut_bot(bars.iloc[:cut], key=2.0, atr_period=1)
        trunc_sell = ut_bot(bars.iloc[:cut], key=2.0, atr_period=300)
        pd.testing.assert_frame_equal(full_buy.iloc[:cut], trunc_buy, check_names=False)
        pd.testing.assert_frame_equal(full_sell.iloc[:cut], trunc_sell, check_names=False)


def test_ut_bot_stop_ratchets_monotonically_in_uptrend():
    n = 100
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    close = 100.0 + np.arange(n) * 1.0
    bars = pd.DataFrame(
        {"open": close - 0.2, "high": close + 0.3, "low": close - 0.3, "close": close}, index=idx
    )
    result = ut_bot(bars, key=2.0, atr_period=6)
    stop = result["stop"].dropna().to_numpy()
    diffs = np.diff(stop)
    assert np.all(diffs >= -1e-9), "stop must never move down while price stays above it"


def test_ut_bot_stop_ratchets_monotonically_in_downtrend():
    """After the warm-up seed and the sell cross that follows it, the
    short-side stop must only ratchet down toward price.

    The seed bar (`first_valid`) always plants a long-side stop
    (`close - nLoss`), unconditional of the trend already in force; in a
    steady downtrend that seed is on the wrong side and price crosses it
    (firing a sell) within a couple of bars -- the monotonicity guarantee
    applies to the ratchet mechanism once a regime is adopted, not to the
    arbitrary warm-up seed itself, so this checks from the first sell cross
    onward.
    """
    n = 100
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    close = 200.0 - np.arange(n) * 1.0
    bars = pd.DataFrame(
        {"open": close + 0.2, "high": close + 0.3, "low": close - 0.3, "close": close}, index=idx
    )
    result = ut_bot(bars, key=2.0, atr_period=6)
    first_sell = result.index[result["sell"]][0]
    stop = result.loc[first_sell:, "stop"].to_numpy()
    diffs = np.diff(stop)
    assert np.all(diffs <= 1e-9), "stop must never move up while price stays below it"


def test_ut_bot_hand_computed_8_bars():
    """Hand-traced 8-bar example, key=2, ATR period=1 (ATR == true range).

    Bars 0-4 ratchet the long-side stop up under a steady uptrend; bar 5's
    range widens (high=12.5) enough to hold the stop flat one more bar
    despite the close pulling back; bar 6 crosses below the held stop and
    fires a sell; bar 7 stays below the new (short-side) stop, no re-cross.
    Values below were computed by hand-replaying the documented recurrence
    (see PREREGISTRATION.md's UT Bot formula) bar by bar; see the
    implementation task notes for the full trace.
    """
    data = {
        "open": [10, 10.5, 11, 11.5, 12, 11, 10, 9],
        "high": [10.5, 11, 11.5, 12, 12.5, 11.5, 10.5, 9.5],
        "low": [9.5, 10, 10.5, 11, 11.5, 10, 9, 8.5],
        "close": [10, 10.8, 11.3, 11.8, 12.2, 10.5, 9.5, 8.8],
    }
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    bars = pd.DataFrame(data, index=idx)

    result = ut_bot(bars, key=2.0, atr_period=1)

    expected_stop = [8.0, 8.8, 9.3, 9.8, 10.2, 10.2, 12.5, 10.8]
    expected_buy = [False] * 8
    expected_sell = [False, False, False, False, False, False, True, False]

    np.testing.assert_allclose(result["stop"].to_numpy(), expected_stop)
    assert result["buy"].tolist() == expected_buy
    assert result["sell"].tolist() == expected_sell


def test_stc_causal_by_truncation():
    bars = _make_random_bars(400, seed=5)
    full = stc(bars["close"], length=80, fast=27, slow=50)
    for cut in (250, 320, 399):
        truncated = stc(bars["close"].iloc[:cut], length=80, fast=27, slow=50)
        pd.testing.assert_series_equal(full.iloc[:cut], truncated, check_names=False)


def test_stc_stays_within_0_100():
    bars = _make_random_bars(600, seed=6)
    s = stc(bars["close"], length=80, fast=27, slow=50)
    valid = s.dropna()
    assert len(valid) > 0
    assert (valid >= 0.0).all()
    assert (valid <= 100.0).all()


def test_stc_flat_series_does_not_crash_on_zero_denominator():
    n = 200
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    close = pd.Series(100.0, index=idx)
    s = stc(close, length=80, fast=27, slow=50)
    valid = s.dropna()
    if len(valid) > 0:
        assert (valid >= 0.0).all()
        assert (valid <= 100.0).all()
