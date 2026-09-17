"""
The SuperTrend(+RSI)(+ADX) long-only strategy under test, and the 420-config grid.

Position rule (the operationalisation recorded in DEVIATIONS.md, since the
source video does not specify one): position = 1 while SuperTrend is in an
uptrend, 0 otherwise. ENTRY (flat -> long) additionally requires every
enabled filter to pass ON THE ENTRY BAR (RSI > threshold; ADX > threshold,
both read at the same bar the entry is being considered). Once long, the
position is held through the same uptrend regardless of what the filters do
next -- exit is SuperTrend flipping down, never a filter failing while
already long. If the filters fail at the bar SuperTrend first flips up, no
position is taken yet; the strategy re-checks the filters on every
subsequent bar of the SAME uptrend run and enters on the first one where
they pass. If they never pass before the uptrend ends, no trade happens for
that run.

All indicator values are computed over the FULL series (so RSI/ADX/SuperTrend
are properly warmed up on history before a window starts) and the resulting
`target_position` is sliced down to a window only at the very end -- see
`run_c03.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from indicators import adx, rsi, supertrend

ATR_PERIODS = [7, 10, 14, 21]
MULTIPLIERS = [2, 3, 4]
RSI_LENGTHS = [14, 28]
RSI_THRESHOLDS = [40, 50, 60]
ADX_LENGTHS = [7, 14]
ADX_THRESHOLDS = [20, 30]


@dataclass(frozen=True)
class Config:
    atr_period: int
    multiplier: float
    rsi_length: int | None
    rsi_threshold: int | None
    adx_length: int | None
    adx_threshold: int | None

    @property
    def label(self) -> str:
        rsi_part = "none" if self.rsi_length is None else f"{self.rsi_length}>{self.rsi_threshold}"
        adx_part = "none" if self.adx_length is None else f"{self.adx_length}>{self.adx_threshold}"
        return f"st{self.atr_period}x{self.multiplier}_rsi{rsi_part}_adx{adx_part}"


def build_grid() -> list[Config]:
    """All 420 configurations: 4 ATR periods x 3 multipliers x 5 RSI options x 7 ADX options."""
    rsi_options: list[tuple[int | None, int | None]] = [(None, None)]
    for length in RSI_LENGTHS:
        for threshold in RSI_THRESHOLDS:
            rsi_options.append((length, threshold))

    adx_options: list[tuple[int | None, int | None]] = [(None, None)]
    for length in ADX_LENGTHS:
        for threshold in ADX_THRESHOLDS:
            adx_options.append((length, threshold))

    grid = []
    for atr_period in ATR_PERIODS:
        for multiplier in MULTIPLIERS:
            for rsi_length, rsi_threshold in rsi_options:
                for adx_length, adx_threshold in adx_options:
                    grid.append(
                        Config(
                            atr_period=atr_period,
                            multiplier=multiplier,
                            rsi_length=rsi_length,
                            rsi_threshold=rsi_threshold,
                            adx_length=adx_length,
                            adx_threshold=adx_threshold,
                        )
                    )
    assert len(grid) == 420, f"expected 420 configs, built {len(grid)}"
    return grid


def _filters_pass(
    t: int,
    rsi_vals: np.ndarray | None,
    rsi_threshold: float | None,
    adx_vals: np.ndarray | None,
    adx_threshold: float | None,
) -> bool:
    if rsi_vals is not None:
        v = rsi_vals[t]
        if np.isnan(v) or not (v > rsi_threshold):
            return False
    if adx_vals is not None:
        v = adx_vals[t]
        if np.isnan(v) or not (v > adx_threshold):
            return False
    return True


def compute_target_position(bars: pd.DataFrame, config: Config) -> pd.Series:
    """Target position (0/1) for `config` over the FULL `bars` series.

    `target_position[t]` is decided from information available at the close
    of bar t (SuperTrend trend, RSI, ADX all read at bar t), matching what
    `common.backtest.run_positions` expects -- it applies the next_open
    execution shift itself.
    """
    st = supertrend(bars, atr_period=config.atr_period, multiplier=config.multiplier)
    trend = st["trend"].to_numpy()

    rsi_vals = rsi(bars["close"], config.rsi_length).to_numpy() if config.rsi_length else None
    adx_vals = adx(bars, config.adx_length)["adx"].to_numpy() if config.adx_length else None

    n = len(bars)
    position = np.zeros(n)
    is_long = False

    for t in range(n):
        uptrend = trend[t] == 1

        if not uptrend:
            is_long = False
            position[t] = 0.0
            continue

        if is_long:
            position[t] = 1.0
            continue

        if _filters_pass(t, rsi_vals, config.rsi_threshold, adx_vals, config.adx_threshold):
            is_long = True
            position[t] = 1.0
        else:
            position[t] = 0.0

    return pd.Series(position, index=bars.index, name="target_position")
