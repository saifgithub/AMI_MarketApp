"""
data.py checks: split/dividend adjustment math on a synthetic frame (no
network), plus a single explicit network smoke test skipped by default.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.data import _clean_bars


def _synthetic_yfinance_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=5, freq="B")
    raw_close = [100.0, 102.0, 51.5, 52.0, 53.0]  # a 2:1 split between day 2 and day 3
    raw_open = [99.0, 101.0, 51.0, 51.5, 52.5]
    raw_high = [101.0, 103.0, 52.0, 52.5, 53.5]
    raw_low = [98.5, 100.5, 50.5, 51.0, 52.0]
    # adj_close reflects the split retroactively: pre-split rows are halved.
    adj_close = [50.0, 51.0, 51.5, 52.0, 53.0]
    volume = [1000, 1100, 2200, 1200, 1300]

    return pd.DataFrame(
        {
            "Open": raw_open,
            "High": raw_high,
            "Low": raw_low,
            "Close": raw_close,
            "Adj Close": adj_close,
            "Volume": volume,
        },
        index=dates,
    )


def test_adjustment_scales_ohlc_by_adj_close_ratio():
    raw = _synthetic_yfinance_frame()
    cleaned = _clean_bars(raw, "SYN")

    expected_ratio = np.array(raw["Adj Close"]) / np.array(raw["Close"])
    expected_close = np.array(raw["Close"]) * expected_ratio
    expected_open = np.array(raw["Open"]) * expected_ratio
    expected_high = np.array(raw["High"]) * expected_ratio
    expected_low = np.array(raw["Low"]) * expected_ratio

    np.testing.assert_allclose(cleaned["close"].to_numpy(), expected_close, atol=1e-9)
    np.testing.assert_allclose(cleaned["open"].to_numpy(), expected_open, atol=1e-9)
    np.testing.assert_allclose(cleaned["high"].to_numpy(), expected_high, atol=1e-9)
    np.testing.assert_allclose(cleaned["low"].to_numpy(), expected_low, atol=1e-9)
    # Pre-split adjusted close must match the post-split adjusted close basis:
    # a 2:1 split day should show continuous (non-jumping) adjusted prices.
    np.testing.assert_allclose(cleaned["close"].iloc[1], 51.0, atol=1e-9)
    np.testing.assert_allclose(cleaned["close"].iloc[2], 51.5, atol=1e-9)


def test_clean_bars_drops_nan_and_zero_price_rows():
    raw = _synthetic_yfinance_frame()
    raw.loc[raw.index[2], "Close"] = 0.0
    raw.loc[raw.index[3], "Open"] = float("nan")

    cleaned = _clean_bars(raw, "SYN")

    assert len(cleaned) == 3
    assert (cleaned[["open", "high", "low", "close"]] > 0).all().all()
    assert not cleaned.isna().any().any()


def test_clean_bars_raises_on_empty_input():
    empty = pd.DataFrame()
    with pytest.raises(ValueError):
        _clean_bars(empty, "EMPTY")


def test_clean_bars_raises_on_missing_columns():
    dates = pd.date_range("2023-01-02", periods=3, freq="B")
    bad = pd.DataFrame({"Open": [1, 2, 3], "Close": [1, 2, 3]}, index=dates)
    with pytest.raises(ValueError):
        _clean_bars(bad, "BAD")


@pytest.mark.network
def test_load_daily_spy_network_smoke():
    from common.data import load_daily

    result = load_daily(["SPY"], start="2023-01-01", end="2023-02-01")
    assert "SPY" in result
    df = result["SPY"]
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert (df[["open", "high", "low", "close"]] > 0).all().all()
