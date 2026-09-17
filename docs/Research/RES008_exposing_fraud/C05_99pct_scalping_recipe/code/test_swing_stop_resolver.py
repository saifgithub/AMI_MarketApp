"""
Direct unit tests for `swing_stop_resolver.run_swing_r_brackets`: the
wrong-side-stop skip rule, one-position-at-a-time, and no-look-ahead by
truncation on a realistic mixed long/short signal series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from swing_stop_resolver import run_swing_r_brackets, swing_stop_distance


def _flat_bars(n: int, price: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": price, "high": price + 0.5, "low": price - 0.5, "close": price}, index=idx
    )


def test_long_signal_skipped_when_swing_low_at_or_above_entry_open():
    n = 20
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 100.0)  # swing low == every bar's open: stop == entry open
    close = np.full(n, 100.0)
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)
    signals = pd.DataFrame({"long": False, "short": False}, index=idx)
    signals.loc[idx[5], "long"] = True

    result = run_swing_r_brackets(bars, signals, target_r=1.5, cost_bps=5.0)
    row = result.trades.iloc[0]
    assert bool(row["skipped"])
    assert result.n_skipped == 1


def test_short_signal_skipped_when_swing_high_at_or_below_entry_open():
    n = 20
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.0)  # swing high == every bar's open: stop == entry open
    low = np.full(n, 99.5)
    close = np.full(n, 100.0)
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)
    signals = pd.DataFrame({"long": False, "short": False}, index=idx)
    signals.loc[idx[5], "short"] = True

    result = run_swing_r_brackets(bars, signals, target_r=1.5, cost_bps=5.0)
    row = result.trades.iloc[0]
    assert bool(row["skipped"])
    assert result.n_skipped == 1


def test_valid_long_trade_hits_target():
    n = 30
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.2)
    low = np.full(n, 99.8)
    close = np.full(n, 100.0)
    # signal bar 10: swing low over bars 1..10 is 99.0 (set only there),
    # so stop = 99.0, entry (open of bar 11) = 100.0, r = 1.0, target (1.5R)=101.5.
    # Every OTHER bar's low/high stays tight around 100 so the stop (99.0)
    # is never touched before bar 15's high reaches the target.
    low[10] = 99.0
    high[15] = 102.0  # bar 15 hits the 101.5 target
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

    signals = pd.DataFrame({"long": False, "short": False}, index=idx)
    signals.loc[idx[10], "long"] = True

    result = run_swing_r_brackets(bars, signals, target_r=1.5, cost_bps=0.0, max_bars=200)
    row = result.trades.iloc[0]
    assert not bool(row["skipped"])
    assert row["exit_reason"] == "take_profit"
    assert row["entry_date"] == idx[11]
    assert row["exit_date"] == idx[15]
    np.testing.assert_allclose(row["gross_r"], 1.5, atol=1e-9)


def test_one_position_at_a_time_ignores_signal_while_open():
    n = 40
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.2)
    low = np.full(n, 99.9)  # tight range: neither stop (99.0) nor target hit before time_exit
    close = np.full(n, 100.0)
    low[5] = 99.0  # swing low seen by the signal at bar 5 only
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

    signals = pd.DataFrame({"long": False, "short": False}, index=idx)
    signals.loc[idx[5], "long"] = True
    signals.loc[idx[7], "long"] = True  # fires while bar 5's trade is still open (time_exit ends it later)

    result = run_swing_r_brackets(bars, signals, target_r=1.5, cost_bps=0.0, max_bars=10)
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["exit_reason"] == "time_exit"


def test_swing_stop_distance_uses_only_10_bars_up_to_and_including_signal():
    n = 30
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    low = np.full(n, 100.0)
    low[3] = 50.0  # far outside the 10-bar lookback from signal bar 20
    low[15] = 80.0  # inside the lookback (bars 11..20)
    bars = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": low, "close": 100.0}, index=idx
    )
    stop = swing_stop_distance(bars, signal_bar=20, side="long", lookback=10)
    assert stop == 80.0


def test_no_lookahead_by_truncation_on_mixed_signals():
    n = 200
    rng = np.random.default_rng(11)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    rets = rng.normal(0.0002, 0.01, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    open_ = np.empty(n)
    open_[0] = 100.0
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

    long_sig = rng.random(n) < 0.05
    short_sig = (~long_sig) & (rng.random(n) < 0.05)
    signals = pd.DataFrame({"long": long_sig, "short": short_sig}, index=idx)

    full = run_swing_r_brackets(bars, signals, target_r=1.5, cost_bps=5.0, max_bars=50)

    cut = 150
    trunc_bars = bars.iloc[:cut]
    trunc_signals = signals.iloc[:cut]
    truncated = run_swing_r_brackets(trunc_bars, trunc_signals, target_r=1.5, cost_bps=5.0, max_bars=50)

    full_before_cut = full.trades[full.trades["signal_date"] < idx[cut - 20]].reset_index(drop=True)
    trunc_before_cut = truncated.trades[truncated.trades["signal_date"] < idx[cut - 20]].reset_index(drop=True)

    pd.testing.assert_series_equal(
        full_before_cut["exit_reason"], trunc_before_cut["exit_reason"], check_names=False
    )
    np.testing.assert_allclose(
        full_before_cut["net_r"].to_numpy(), trunc_before_cut["net_r"].to_numpy()
    )
