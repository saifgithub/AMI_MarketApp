"""
`_draw_non_overlapping_starts` checks: the O(k) uniform-composition
placement never overlaps or runs out of range, its marginal start position
is approximately uniform, and it is fast enough for RES008's actual scale
(thousands of bars, hundreds of trades, hundreds of replications, across
hundreds of (strategy, ticker) pairs) -- the earlier O(n_bars * n_trades)
rejection sampler was not.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from common.placebo import _draw_non_overlapping_starts, matched_random_entries


def test_placements_never_overlap_or_leave_range():
    rng = np.random.default_rng(0)
    for trial in range(1000):
        n_bars = int(rng.integers(5, 200))
        k = int(rng.integers(1, 10))
        max_len = max(1, n_bars // (k * 2))
        holding_periods = rng.integers(1, max_len + 1, size=k).tolist()
        if sum(holding_periods) > n_bars:
            continue

        starts = _draw_non_overlapping_starts(n_bars, holding_periods, rng)

        occupied = np.zeros(n_bars, dtype=int)
        for start, length in zip(starts, holding_periods):
            assert start >= 0
            assert start + length <= n_bars, (trial, start, length, n_bars)
            occupied[start : start + length] += 1

        assert occupied.max() <= 1, f"overlap detected on trial {trial}"


def test_placement_raises_when_intervals_cannot_fit():
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError):
        _draw_non_overlapping_starts(10, [6, 6], rng)


def test_single_trade_start_is_approximately_uniform():
    n_bars = 20
    length = 3
    n_valid_starts = n_bars - length + 1  # 18

    rng = np.random.default_rng(2)
    draws = np.array([_draw_non_overlapping_starts(n_bars, [length], rng)[0] for _ in range(50_000)])

    assert draws.min() == 0
    assert draws.max() == n_valid_starts - 1

    counts = np.bincount(draws, minlength=n_valid_starts)
    expected = len(draws) / n_valid_starts
    # Loose tolerance: each bin should land within 15% of the uniform
    # expectation over 50,000 draws.
    assert np.all(np.abs(counts - expected) < 0.15 * expected)


def test_matched_random_entries_scales_to_res008_worst_case():
    bars_n = 5000
    n_trades = 200
    n_reps = 500

    dates = pd.date_range("2000-01-01", periods=bars_n, freq="B")
    rng = np.random.default_rng(3)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, size=bars_n)))
    open_ = np.roll(close, 1)
    open_[0] = 100.0
    bars = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close,
            "volume": rng.integers(1000, 10000, size=bars_n),
        },
        index=dates,
    )

    lengths = rng.integers(2, 15, size=n_trades)
    while lengths.sum() > bars_n * 0.8:
        lengths = rng.integers(2, 15, size=n_trades)
    sides = rng.choice(["long", "short"], size=n_trades)
    trades = pd.DataFrame({"side": sides, "bars_held": lengths})

    start = time.perf_counter()
    dist = matched_random_entries(bars, trades, n_reps=n_reps, cost_bps=5.0, seed=4)
    elapsed = time.perf_counter() - start

    assert dist["total_returns"].shape == (n_reps,)
    assert elapsed < 5.0, f"matched_random_entries took {elapsed:.2f}s, expected < 5s"
