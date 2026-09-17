"""
EXPLORATORY -- not pre-registered; written and run after the pre-registered
results were seen.

Tests for the small pure-logic helpers in `posthoc_diagnostic.py`:
`_pct`, `_stop_dist_pct`, and `_side_stats`. The heavier `run_cell_diagnostic`
is exercised end-to-end by actually running the script (see out/ after a
run); these tests check the building blocks in isolation and fast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from posthoc_diagnostic import _pct, _side_stats, _stop_dist_pct


def test_pct_matches_numpy_percentile():
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, np.nan])
    assert _pct(arr, 50) == np.percentile([1, 2, 3, 4, 5], 50)


def test_pct_empty_after_dropping_nan_returns_nan():
    arr = np.array([np.nan, np.nan])
    assert np.isnan(_pct(arr, 50))


def test_stop_dist_pct_skips_skipped_trades_and_matches_manual():
    trades = pd.DataFrame(
        {
            "entry_price": [100.0, 200.0, 50.0],
            "stop_price": [99.0, 196.0, 51.0],
            "skipped": [False, False, True],
        }
    )
    dist = _stop_dist_pct(trades)
    np.testing.assert_allclose(dist, [0.01, 0.02])


def test_side_stats_empty_side_returns_nan_not_crash():
    trades = pd.DataFrame({"net_return": [], "gross_return": []})
    stats = _side_stats(trades)
    assert stats["n"] == 0
    assert np.isnan(stats["net_pct"])
    assert np.isnan(stats["gross_pct"])


def test_side_stats_computes_means():
    trades = pd.DataFrame({"net_return": [0.01, -0.02, 0.03], "gross_return": [0.015, -0.015, 0.035]})
    stats = _side_stats(trades)
    assert stats["n"] == 3
    np.testing.assert_allclose(stats["net_pct"], np.mean([0.01, -0.02, 0.03]))
    np.testing.assert_allclose(stats["gross_pct"], np.mean([0.015, -0.015, 0.035]))
