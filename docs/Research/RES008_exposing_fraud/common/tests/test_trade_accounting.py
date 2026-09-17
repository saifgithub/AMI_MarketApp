"""
Trade-table accounting checks (DEF: `_extract_trades` was dropping the exit
leg and exit cost -- a run start..end really earns its exit leg one bar
OUTSIDE the run, on the bar `run_positions` itself charges the turnover
cost). These tests pin down that compounding every trade's return
reproduces the authoritative daily series, for both execution conventions,
including flips and a position still open on the last bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_positions
from common.tests.conftest import make_random_bars

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


def test_hand_computed_single_long_trade_next_open():
    # pending_target sequencing: target[0]=0 decided "at t=0" fills at t=1
    # (still flat); target[1]=1 decided at close(1) fills at open(2) --
    # position becomes 1 starting bar 2; target[2]=1 and target[3]=1 keep it
    # long through bars 3 and 4; target[4]=0 decided at close(4) fills at
    # open(5), which is where the OLD long position's exit leg (and exit
    # cost) land. So the realised run is bars 2..4 and the trade's true
    # price span is open(2) -> open(5).
    bars = _bars()
    target = pd.Series([0, 1, 1, 1, 0, 0], index=bars.index, dtype=float)
    result = run_positions(bars, target, cost_bps=10.0, execution="next_open")

    assert result.positions_held.tolist() == [0.0, 0.0, 1.0, 1.0, 1.0, 0.0]
    assert len(result.trades) == 1
    trade = result.trades.iloc[0]

    expected_entry_price = _OPEN[2]
    expected_exit_price = _OPEN[5]
    expected_gross = expected_exit_price / expected_entry_price - 1.0
    expected_net = expected_gross - 2 * 10.0 / 10_000.0

    assert trade["side"] == "long"
    np.testing.assert_allclose(trade["entry_price"], expected_entry_price)
    np.testing.assert_allclose(trade["exit_price"], expected_exit_price)
    assert trade["bars_held"] == 3
    np.testing.assert_allclose(trade["gross_return"], expected_gross, atol=1e-12)
    np.testing.assert_allclose(trade["net_return"], expected_net, atol=1e-12)


def _random_target(bars: pd.DataFrame, seed: int, choices=(-1.0, 0.0, 1.0)) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.choice(choices, size=len(bars)), index=bars.index)


@pytest.mark.parametrize("execution", ["next_open", "same_close"])
@pytest.mark.parametrize("seed", range(15))
def test_trade_table_reproduces_daily_series_zero_cost(execution, seed):
    bars = make_random_bars(n=150, seed=seed)
    target = _random_target(bars, seed=seed + 1000)
    result = run_positions(bars, target, cost_bps=0.0, execution=execution)

    if len(result.trades) == 0:
        pytest.skip("no trades generated for this seed")

    trades_total = float((1.0 + result.trades["net_return"]).prod() - 1.0)
    daily_total = float((1.0 + result.daily_returns).prod() - 1.0)

    np.testing.assert_allclose(trades_total, daily_total, atol=1e-9)


@pytest.mark.parametrize("execution", ["next_open", "same_close"])
@pytest.mark.parametrize("seed", range(15))
def test_trade_table_reproduces_daily_series_with_cost(execution, seed):
    bars = make_random_bars(n=150, seed=seed)
    target = _random_target(bars, seed=seed + 2000)
    cost_bps = 5.0
    result = run_positions(bars, target, cost_bps=cost_bps, execution=execution)

    if len(result.trades) == 0:
        pytest.skip("no trades generated for this seed")

    # Gross (no cost involved) must match to floating-point precision --
    # this is the actual price-accounting invariant fix 1 exists to defend.
    trades_gross_total = float((1.0 + result.trades["gross_return"]).prod() - 1.0)
    daily_gross_total = float((1.0 + result.gross_daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_gross_total, daily_gross_total, atol=1e-9)

    # Net differs from the daily series only by additive-vs-compounded cost
    # drag: run_positions subtracts each cost as it is incurred and
    # compounds it forward through every later bar, while the trade table
    # subtracts each trade's cost once from that trade's own compounded
    # gross return. That drag is second-order in cost_rate (a product of
    # two small numbers: the cost itself and the return it compounds
    # against) and accumulates additively across trades, so an absolute
    # tolerance scaled by trade count -- not a fixed relative tolerance,
    # which breaks down whenever the total return is small -- is the
    # faithful check.
    cost_rate = cost_bps / 10_000.0
    n_trades = len(result.trades)
    tolerance = max(5e-4, 20.0 * n_trades * cost_rate * cost_rate)

    trades_net_total = float((1.0 + result.trades["net_return"]).prod() - 1.0)
    daily_net_total = float((1.0 + result.daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_net_total, daily_net_total, atol=tolerance)


def test_trade_table_with_direct_flip_next_open():
    bars = make_random_bars(n=40, seed=5)
    target = pd.Series(0.0, index=bars.index)
    target.iloc[5:15] = 1.0
    target.iloc[15:25] = -1.0  # direct flip, no flat gap
    result = run_positions(bars, target, cost_bps=3.0, execution="next_open")

    assert len(result.trades) == 2
    assert list(result.trades["side"]) == ["long", "short"]

    trades_total = float((1.0 + result.trades["net_return"]).prod() - 1.0)
    daily_total = float((1.0 + result.daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_total, daily_total, rtol=1e-3, atol=5e-4)


def test_trade_table_with_direct_flip_same_close():
    bars = make_random_bars(n=40, seed=6)
    target = pd.Series(0.0, index=bars.index)
    target.iloc[5:15] = -1.0
    target.iloc[15:25] = 1.0
    result = run_positions(bars, target, cost_bps=3.0, execution="same_close")

    assert len(result.trades) == 2
    assert list(result.trades["side"]) == ["short", "long"]

    trades_total = float((1.0 + result.trades["net_return"]).prod() - 1.0)
    daily_total = float((1.0 + result.daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_total, daily_total, rtol=1e-3, atol=5e-4)


@pytest.mark.parametrize("execution", ["next_open", "same_close"])
def test_position_still_open_on_last_bar_has_no_phantom_exit_cost(execution):
    bars = make_random_bars(n=30, seed=7)
    target = pd.Series(0.0, index=bars.index)
    target.iloc[10:] = 1.0  # never closed before the series ends
    result = run_positions(bars, target, cost_bps=8.0, execution=execution)

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]

    # Only the entry cost was ever charged by run_positions (no bar exists
    # to charge an exit cost on), so net_return should be gross - 1 unit,
    # not gross - 2 units.
    np.testing.assert_allclose(trade["gross_return"] - trade["net_return"], 8.0 / 10_000.0, atol=1e-12)

    # Gross must match exactly -- the trade replays the exact same per-bar
    # legs run_positions computed, with no cost involved.
    trades_gross_total = float((1.0 + result.trades["gross_return"]).prod() - 1.0)
    daily_gross_total = float((1.0 + result.gross_daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_gross_total, daily_gross_total, atol=1e-9)

    # Net differs only by additive-vs-compounded cost drag: run_positions
    # subtracts the cost from one bar's gross return and compounds it
    # through every later bar, while the trade table subtracts the same
    # cost once from the trade's total compounded gross return.
    trades_net_total = float((1.0 + result.trades["net_return"]).prod() - 1.0)
    daily_net_total = float((1.0 + result.daily_returns).prod() - 1.0)
    np.testing.assert_allclose(trades_net_total, daily_net_total, rtol=1e-3)
