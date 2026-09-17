"""
Proves `run_swing_r_brackets` agrees EXACTLY with `common.backtest.run_brackets`
on a case where the two coincide: a FIXED percentage stop/target (entry * (1
+/- pct), not a real 10-bar swing low/high) and a single side, on real SPY
daily bars. This is the pre-registration's required guardrail before the
per-trade swing-stop resolver used by `run_c05.py` can be trusted -- it must
not be a second, subtly different implementation of the same bracket rules
`common/` already tests.

To force the fixed-percentage case, this monkeypatches
`swing_stop_resolver.swing_stop_distance` for the duration of the test so
the "swing stop" it returns is `entry * (1 -/+ stop_pct)` instead of a real
window min/max -- everything downstream (entry timing, stop-first-in-bar,
gap-through-fill, per-side costs, one-position-at-a-time) is exercised
unchanged. `take_profit_pct`/`stop_loss_pct` map onto this module's
`target_r`/implied-stop-distance by setting target_r = take_profit_pct /
stop_loss_pct, so `target_price` in both engines lands on the identical
price level.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_brackets
from common.data import load_daily

import swing_stop_resolver as ssr
from swing_stop_resolver import run_swing_r_brackets

_GEOMETRIES = [
    (0.01, 0.01),
    (0.015, 0.01),
    (0.02, 0.01),
    (0.01, 0.02),
    (0.03, 0.02),
]


@pytest.fixture(scope="module")
def spy_bars() -> pd.DataFrame:
    return load_daily(["SPY"], "2015-01-01", "2020-12-31")["SPY"]


def _random_signal_bars(bars: pd.DataFrame, seed: int, p: float = 0.03) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.random(len(bars)) < p, index=bars.index)


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("take_profit_pct,stop_loss_pct", _GEOMETRIES)
def test_fixed_pct_single_side_matches_run_brackets_exactly(
    spy_bars, monkeypatch, side, take_profit_pct, stop_loss_pct
):
    entries = _random_signal_bars(spy_bars, seed=7)

    reference = run_brackets(
        spy_bars,
        entries,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        max_bars=60,
        cost_bps=5.0,
        side=side,
    )

    def fixed_pct_stop(bars, signal_bar, side_, lookback=10):
        entry_price = bars["open"].iloc[signal_bar + 1]
        if side_ == "long":
            return entry_price * (1.0 - stop_loss_pct)
        return entry_price * (1.0 + stop_loss_pct)

    monkeypatch.setattr(ssr, "swing_stop_distance", fixed_pct_stop)

    signals = pd.DataFrame(
        {
            "long": entries if side == "long" else pd.Series(False, index=spy_bars.index),
            "short": entries if side == "short" else pd.Series(False, index=spy_bars.index),
        }
    )
    target_r = take_profit_pct / stop_loss_pct

    swing = run_swing_r_brackets(
        spy_bars, signals, target_r=target_r, cost_bps=5.0, max_bars=60, lookback=10
    )

    swing_trades = swing.trades[~swing.trades["skipped"]].reset_index(drop=True)

    assert len(swing_trades) == len(reference.trades)
    assert len(reference.trades) > 0
    assert swing.n_skipped == 0

    pd.testing.assert_series_equal(
        swing_trades["entry_date"], reference.trades["entry_date"], check_names=False
    )
    pd.testing.assert_series_equal(
        swing_trades["exit_date"], reference.trades["exit_date"], check_names=False
    )
    pd.testing.assert_series_equal(
        swing_trades["exit_reason"], reference.trades["exit_reason"], check_names=False
    )
    np.testing.assert_allclose(
        swing_trades["net_return"].to_numpy(), reference.trades["net_return"].to_numpy()
    )
    np.testing.assert_allclose(
        swing_trades["gross_return"].to_numpy(), reference.trades["gross_return"].to_numpy()
    )
