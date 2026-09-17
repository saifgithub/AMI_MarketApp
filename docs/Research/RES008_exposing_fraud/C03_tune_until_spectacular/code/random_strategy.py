"""
Part 2's placebo family: random long/flat strategies matched to the grid's
MEDIAN exposure and trade count on a given instrument's tuning window.

Distinct from `common.placebo.matched_random_entries` (which matches an
individual real trade list's exact holding-period multiset) -- here there is
no single "real" trade list to match; the spec calls for matching the GRID's
median trade count and median exposure instead. Spell lengths are drawn by a
random composition of the total in-market bars into that many parts (each
part >= 1), then placed at a uniformly random non-overlapping start within
the window, mirroring `common.placebo`'s non-overlapping-placement approach
but built for this median-matching target rather than an exact list.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _random_composition(total: int, parts: int, rng: np.random.Generator) -> list[int]:
    """`parts` positive integers summing to `total`, drawn uniformly among such compositions."""
    if parts <= 0 or total < parts:
        raise ValueError(f"cannot split total={total} into {parts} positive parts")
    if parts == 1:
        return [total]
    cuts = rng.choice(np.arange(1, total), size=parts - 1, replace=False)
    cuts = np.sort(cuts)
    bounds = np.concatenate(([0], cuts, [total]))
    lengths = np.diff(bounds).tolist()
    return [int(x) for x in lengths]


def _draw_non_overlapping_starts(
    n_bars: int, lengths: list[int], rng: np.random.Generator, max_attempts: int = 500
) -> list[int] | None:
    for _ in range(max_attempts):
        order = rng.permutation(len(lengths))
        occupied = np.zeros(n_bars, dtype=bool)
        starts = [None] * len(lengths)
        ok = True
        for idx in order:
            length = lengths[idx]
            if length > n_bars:
                ok = False
                break
            candidates = [s for s in range(0, n_bars - length + 1) if not occupied[s : s + length].any()]
            if not candidates:
                ok = False
                break
            s = candidates[rng.integers(0, len(candidates))]
            occupied[s : s + length] = True
            starts[idx] = s
        if ok:
            return starts
    return None


def random_long_flat_position(
    n_bars: int, n_spells: int, total_bars_in_market: int, rng: np.random.Generator
) -> np.ndarray:
    """One random long/flat position path over `n_bars`, matched on spell count and total exposure."""
    if n_spells <= 0 or total_bars_in_market <= 0:
        return np.zeros(n_bars)

    n_spells = min(n_spells, total_bars_in_market)
    lengths = _random_composition(total_bars_in_market, n_spells, rng)
    starts = _draw_non_overlapping_starts(n_bars, lengths, rng)
    if starts is None:
        raise ValueError(
            f"could not place {n_spells} non-overlapping spells totalling "
            f"{total_bars_in_market} bars within a {n_bars}-bar window"
        )

    position = np.zeros(n_bars)
    for start, length in zip(starts, lengths):
        position[start : start + length] = 1.0
    return position


def generate_random_configs(
    bars: pd.DataFrame,
    n_configs: int,
    median_trades: int,
    median_exposure: float,
    seed: int,
) -> list[pd.Series]:
    """`n_configs` random long/flat target-position series over `bars`.

    Each has `n_spells = median_trades` non-overlapping long spells totalling
    `round(median_exposure * len(bars))` bars in market, spell lengths drawn
    by a random composition, placement uniform over the window.
    """
    n_bars = len(bars)
    total_bars_in_market = int(round(median_exposure * n_bars))
    total_bars_in_market = max(0, min(total_bars_in_market, n_bars))

    n_spells = int(round(median_trades))
    rng = np.random.default_rng(seed)

    series_list = []
    for _ in range(n_configs):
        position = random_long_flat_position(n_bars, n_spells, total_bars_in_market, rng)
        series_list.append(pd.Series(position, index=bars.index, name="target_position"))
    return series_list
