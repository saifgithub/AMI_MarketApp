"""
Proves `run_mixed_brackets` agrees EXACTLY with `common.backtest.run_brackets`
when every trade uses the same side, on real SPY daily bars. This is the
pre-registration's required guardrail before the mixed-side draws in
`run_c04.py` can be trusted: the mixed engine must not be a second,
subtly-different implementation of the bracket rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.backtest import run_brackets
from common.data import load_daily

from brackets_mixed import run_mixed_brackets

_GEOMETRIES = [
    (0.005, 0.05),
    (0.01, 0.05),
    (0.01, 0.03),
    (0.01, 0.01),
    (0.02, 0.01),
    (0.03, 0.01),
    (0.05, 0.01),
]


@pytest.fixture(scope="module")
def spy_bars() -> pd.DataFrame:
    return load_daily(["SPY"], "2015-01-01", "2020-12-31")["SPY"]


def _random_entries(bars: pd.DataFrame, seed: int, p: float = 0.03) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.random(len(bars)) < p, index=bars.index)


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("take_profit_pct,stop_loss_pct", _GEOMETRIES)
def test_uniform_side_matches_run_brackets_exactly(spy_bars, side, take_profit_pct, stop_loss_pct):
    entries = _random_entries(spy_bars, seed=42)
    sides = pd.Series(side, index=spy_bars.index)

    reference = run_brackets(
        spy_bars,
        entries,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        max_bars=60,
        cost_bps=5,
        side=side,
    )
    mixed = run_mixed_brackets(
        spy_bars,
        entries,
        sides,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        max_bars=60,
        cost_bps=5,
    )

    assert len(mixed.trades) == len(reference.trades)
    assert len(reference.trades) > 0

    pd.testing.assert_series_equal(
        mixed.trades["entry_date"], reference.trades["entry_date"], check_names=False
    )
    pd.testing.assert_series_equal(
        mixed.trades["exit_date"], reference.trades["exit_date"], check_names=False
    )
    pd.testing.assert_series_equal(
        mixed.trades["exit_reason"], reference.trades["exit_reason"], check_names=False
    )
    np.testing.assert_allclose(
        mixed.trades["net_return"].to_numpy(), reference.trades["net_return"].to_numpy()
    )
    np.testing.assert_allclose(
        mixed.trades["gross_return"].to_numpy(), reference.trades["gross_return"].to_numpy()
    )
    np.testing.assert_allclose(
        mixed.daily_returns.to_numpy(), reference.daily_returns.to_numpy()
    )
    np.testing.assert_allclose(
        mixed.positions_held.to_numpy(), reference.positions_held.to_numpy()
    )
