"""Shared fixtures for the RES008 common test suite: synthetic OHLC bars only, no network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_random_bars(n: int = 120, seed: int = 0, start_price: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")

    log_returns = rng.normal(loc=0.0002, scale=0.01, size=n)
    close = start_price * np.exp(np.cumsum(log_returns))

    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1] * (1.0 + rng.normal(0.0, 0.002, size=n - 1))

    intraday_range = np.abs(rng.normal(0.005, 0.003, size=n))
    high = np.maximum(open_, close) * (1.0 + intraday_range)
    low = np.minimum(open_, close) * (1.0 - intraday_range)

    volume = rng.integers(1_000, 100_000, size=n)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def random_bars() -> pd.DataFrame:
    return make_random_bars()
