"""
Placebo control checks: replications match the real trades' count and
holding-period multiset, seeded runs reproduce, and on a driftless random
walk a signal with no real edge lands roughly uniformly against its own
matched-random distribution.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_positions
from common.placebo import _price_placed_trade, matched_random_entries, percentile_of
from common.tests.conftest import make_random_bars


def _driftless_bars(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    log_returns = rng.normal(loc=0.0, scale=0.01, size=n)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    open_ = np.roll(close, 1)
    open_[0] = 100.0
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998
    volume = rng.integers(1000, 10000, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates
    )


def _random_signal_trades(bars: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    target = pd.Series(0.0, index=bars.index)
    n = len(bars)
    i = 0
    while i < n - 10:
        if rng.random() < 0.1:
            hold = rng.integers(2, 8)
            target.iloc[i : i + hold] = 1.0
            i += hold
        else:
            i += 1
    result = run_positions(bars, target, cost_bps=1.0, execution="next_open")
    return result


def test_matched_random_entries_preserve_trade_count_and_holding_periods():
    bars = make_random_bars(n=150, seed=7)
    result = _random_signal_trades(bars, seed=8)
    trades = result.trades
    assert len(trades) > 0

    rng_seed = 123
    dist = matched_random_entries(bars, trades, n_reps=20, cost_bps=1.0, seed=rng_seed)
    assert dist["total_returns"].shape == (20,)
    assert dist["mean_trade_returns"].shape == (20,)


def test_matched_random_entries_reproducible_with_same_seed():
    bars = make_random_bars(n=150, seed=9)
    result = _random_signal_trades(bars, seed=10)
    trades = result.trades

    dist_a = matched_random_entries(bars, trades, n_reps=15, cost_bps=2.0, seed=555)
    dist_b = matched_random_entries(bars, trades, n_reps=15, cost_bps=2.0, seed=555)

    np.testing.assert_array_equal(dist_a["total_returns"], dist_b["total_returns"])
    np.testing.assert_array_equal(dist_a["mean_trade_returns"], dist_b["mean_trade_returns"])


def test_matched_random_entries_different_seed_generally_differs():
    bars = make_random_bars(n=150, seed=11)
    result = _random_signal_trades(bars, seed=12)
    trades = result.trades

    dist_a = matched_random_entries(bars, trades, n_reps=15, cost_bps=2.0, seed=1)
    dist_b = matched_random_entries(bars, trades, n_reps=15, cost_bps=2.0, seed=2)

    assert not np.array_equal(dist_a["total_returns"], dist_b["total_returns"])


@pytest.mark.parametrize("execution", ["next_open", "same_close"])
def test_pricing_actual_trades_own_starts_reproduces_their_net_returns_exactly(execution):
    """
    Feeding the placebo pricer the REAL trades' own (start, length, side)
    must reproduce their real net_return exactly -- that is what proves
    the placebo's execution convention is identical to run_positions', not
    merely similar. Before this fix, matched_random_entries always exited
    at that day's close (missing the overnight leg a next_open trade earns),
    which is exactly the case this test would have caught.
    """
    bars = make_random_bars(n=150, seed=20)
    rng = np.random.default_rng(21)
    target = pd.Series(rng.choice([-1.0, 0.0, 1.0], size=len(bars)), index=bars.index)
    cost_bps = 6.0
    result = run_positions(bars, target, cost_bps=cost_bps, execution=execution)
    trades = result.trades
    assert len(trades) > 0

    open_ = bars["open"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    cost_rate = cost_bps / 10_000.0

    for _, row in trades.iterrows():
        start = bars.index.get_loc(row["entry_date"])
        length = int(row["bars_held"])
        side = row["side"]

        gross, exit_bar = _price_placed_trade(open_, close, start, length, side, execution)
        end = start + length - 1
        closes_within_series = exit_bar > end
        cost = cost_rate * (1.0 + (1.0 if closes_within_series else 0.0))
        net = gross - cost

        np.testing.assert_allclose(net, row["net_return"], atol=1e-12)


def test_matched_random_entries_default_execution_matches_next_open():
    bars = make_random_bars(n=150, seed=22)
    result = _random_signal_trades(bars, seed=23)
    trades = result.trades

    dist_default = matched_random_entries(bars, trades, n_reps=10, cost_bps=1.0, seed=42)
    dist_explicit = matched_random_entries(
        bars, trades, n_reps=10, cost_bps=1.0, seed=42, execution="next_open"
    )
    np.testing.assert_array_equal(dist_default["total_returns"], dist_explicit["total_returns"])


def test_percentile_of_random_strategy_on_driftless_walk_is_roughly_uniform():
    percentiles = []
    for trial_seed in range(30):
        bars = _driftless_bars(n=200, seed=1000 + trial_seed)
        result = _random_signal_trades(bars, seed=2000 + trial_seed)
        trades = result.trades
        if len(trades) < 3:
            continue

        actual_total_return = float(result.summary()["total_return"])
        dist = matched_random_entries(bars, trades, n_reps=200, cost_bps=1.0, seed=3000 + trial_seed)
        pct = percentile_of(actual_total_return, dist["total_returns"])
        percentiles.append(pct)

    percentiles = np.array(percentiles)
    assert len(percentiles) >= 15
    # Loose tolerance: a signal with no real edge should not systematically
    # land near 0 or 1 across many independent driftless trials.
    mean_percentile = percentiles.mean()
    assert 0.25 < mean_percentile < 0.75
