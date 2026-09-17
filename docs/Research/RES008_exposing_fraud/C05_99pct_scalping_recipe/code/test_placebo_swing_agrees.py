"""
Proves the pure-numpy `placebo_swing._resolve_one_trade` reproduces
`swing_stop_resolver.run_swing_r_brackets` exactly, trade for trade, on the
same signals -- the placebo's speed-motivated numpy reimplementation must
not silently diverge from the resolver it is supposed to be a random-entry
control for.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.data import load_daily

from placebo_swing import _resolve_one_trade
from swing_stop_resolver import run_swing_r_brackets


@pytest.fixture(scope="module")
def spy_bars() -> pd.DataFrame:
    return load_daily(["SPY"], "2018-01-01", "2020-12-31")["SPY"]


@pytest.mark.parametrize("side_is_long", [True, False])
@pytest.mark.parametrize("target_r", [1.5, 2.0])
def test_single_trade_matches_resolver(spy_bars, side_is_long, target_r):
    open_ = spy_bars["open"].to_numpy(dtype=float)
    high = spy_bars["high"].to_numpy(dtype=float)
    low = spy_bars["low"].to_numpy(dtype=float)
    close = spy_bars["close"].to_numpy(dtype=float)
    n = len(spy_bars)

    cost_bps = 5.0
    cost_rate = cost_bps / 10_000.0

    rng = np.random.default_rng(3)
    signal_bars = rng.choice(np.arange(20, n - 210), size=20, replace=False)

    for signal_bar in signal_bars:
        signal_bar = int(signal_bar)
        skipped, exit_bar, net_r, gross_r = _resolve_one_trade(
            open_, high, low, close, signal_bar, side_is_long, target_r, cost_rate,
            max_bars=200, lookback=10, n=n,
        )

        signals = pd.DataFrame({"long": False, "short": False}, index=spy_bars.index)
        col = "long" if side_is_long else "short"
        signals.loc[spy_bars.index[signal_bar], col] = True

        result = run_swing_r_brackets(
            spy_bars, signals, target_r=target_r, cost_bps=cost_bps, max_bars=200, lookback=10
        )
        row = result.trades.iloc[0]

        assert skipped == bool(row["skipped"])
        if not skipped:
            np.testing.assert_allclose(net_r, row["net_r"], atol=1e-9)
            np.testing.assert_allclose(gross_r, row["gross_r"], atol=1e-9)
