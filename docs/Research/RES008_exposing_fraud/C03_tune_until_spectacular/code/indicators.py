"""
Causal indicators for C03: SuperTrend, RSI, ADX -- all Wilder-family smoothing.

Every function here is computed once over a full price series and is safe to
slice afterward: the value at bar t is a function of bars 0..t only, never of
anything later. That property (not any particular numeric library) is what
`test_indicators.py`'s truncation tests check. Callers that need a windowed
backtest should compute indicators on the FULL series first and slice the
resulting position/indicator series down to the window afterward, so the
window's first bars are not artificially flat for lack of warmup history.

Wilder smoothing (RMA) is the exponential average with alpha = 1/period,
seeded by a plain mean of the first `period` consecutive non-NaN values (so a
leading NaN from an upstream diff/warmup does not poison every value after
it) -- the same recurrence used by ATR, RSI and ADX in Wilder's original "New
Concepts in Technical Trading Systems" (1978).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _wilder_rma(x: pd.Series, period: int) -> pd.Series:
    """Wilder RMA, seeded once `period` consecutive non-NaN values exist.

    A leading run of NaN (e.g. a diff series' first bar, or an upstream
    indicator's own warmup) is skipped rather than poisoning the seed mean --
    seeding starts at the first bar `s` such that x[s-period+1 : s+1] has no
    NaN, using a plain mean over exactly those `period` values, still a
    function of history up to and including bar s only.
    """
    x = x.astype(float)
    n = len(x)
    out = np.full(n, np.nan)

    vals = x.to_numpy()
    valid = ~np.isnan(vals)

    seed_end = None
    run = 0
    for t in range(n):
        run = run + 1 if valid[t] else 0
        if run >= period:
            seed_end = t
            break
    if seed_end is None:
        return pd.Series(out, index=x.index)

    seed = vals[seed_end - period + 1 : seed_end + 1].mean()
    out[seed_end] = seed
    prev = seed
    for t in range(seed_end + 1, n):
        v = vals[t]
        if np.isnan(v):
            out[t] = np.nan
            prev = np.nan
        elif np.isnan(prev):
            out[t] = np.nan
        else:
            prev = (prev * (period - 1) + v) / period
            out[t] = prev
    return pd.Series(out, index=x.index)


def atr(bars: pd.DataFrame, period: int) -> pd.Series:
    """Wilder average true range."""
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    tr.iloc[0] = high.iloc[0] - low.iloc[0]

    return _wilder_rma(tr, period)


def supertrend(bars: pd.DataFrame, atr_period: int, multiplier: float) -> pd.DataFrame:
    """SuperTrend: ATR bands on hl2, ratcheting final bands, trend flips on close crossing.

    Returns a DataFrame with columns `supertrend` (the active final band level)
    and `trend` (+1 uptrend / -1 downtrend), indexed like `bars`. Bars before
    the ATR warms up carry NaN/trend=+1 placeholders that are never used by a
    caller who slices to a window starting after warmup (BTC, which has no
    pre-window history, is the one instrument where this floor bites -- see
    DEVIATIONS.md).

    Standard construction (Pine Script `ta.supertrend`, matching the widely
    used reference implementation):
      hl2 = (high + low) / 2
      upper_basic = hl2 + multiplier * atr
      lower_basic = hl2 - multiplier * atr
      final upper band: ratchets DOWN only (tightens) while price stays below
        it, or resets to the fresh basic band if price closes above the prior
        final upper band or the prior final upper band was undercut.
      final lower band: mirror image, ratchets UP only.
      trend flips to down when close crosses below the final upper band;
      flips to up when close crosses above the final lower band.
    """
    high = bars["high"].astype(float).to_numpy()
    low = bars["low"].astype(float).to_numpy()
    close = bars["close"].astype(float).to_numpy()
    n = len(bars)

    atr_vals = atr(bars, atr_period).to_numpy()
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_vals
    basic_lower = hl2 - multiplier * atr_vals

    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    trend = np.ones(n, dtype=int)
    st = np.full(n, np.nan)

    first_valid = int(np.argmax(~np.isnan(atr_vals))) if np.any(~np.isnan(atr_vals)) else n

    for t in range(n):
        if t < first_valid:
            trend[t] = 1
            continue

        if t == first_valid:
            final_upper[t] = basic_upper[t]
            final_lower[t] = basic_lower[t]
            trend[t] = 1 if close[t] >= final_lower[t] else -1
            st[t] = final_lower[t] if trend[t] == 1 else final_upper[t]
            continue

        if basic_upper[t] < final_upper[t - 1] or close[t - 1] > final_upper[t - 1]:
            final_upper[t] = basic_upper[t]
        else:
            final_upper[t] = final_upper[t - 1]

        if basic_lower[t] > final_lower[t - 1] or close[t - 1] < final_lower[t - 1]:
            final_lower[t] = basic_lower[t]
        else:
            final_lower[t] = final_lower[t - 1]

        prev_trend = trend[t - 1]
        if prev_trend == 1:
            trend[t] = -1 if close[t] < final_lower[t] else 1
        else:
            trend[t] = 1 if close[t] > final_upper[t] else -1

        st[t] = final_lower[t] if trend[t] == 1 else final_upper[t]

    return pd.DataFrame({"supertrend": st, "trend": trend}, index=bars.index)


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder RSI: 100 - 100 / (1 + RMA(gains) / RMA(losses))."""
    close = close.astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    if len(close) > 0:
        gain.iloc[0] = 0.0
        loss.iloc[0] = 0.0

    avg_gain = _wilder_rma(gain, period)
    avg_loss = _wilder_rma(loss, period)

    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~(avg_gain == 0) | ~(avg_loss == 0), 50.0)
    return out


def adx(bars: pd.DataFrame, period: int) -> pd.DataFrame:
    """Wilder ADX with +DI/-DI. Returns columns `plus_di`, `minus_di`, `adx`."""
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=bars.index)
    minus_dm = pd.Series(minus_dm, index=bars.index)
    if len(bars) > 0:
        plus_dm.iloc[0] = 0.0
        minus_dm.iloc[0] = 0.0

    tr_atr = atr(bars, period)

    smoothed_plus_dm = _wilder_rma(plus_dm, period)
    smoothed_minus_dm = _wilder_rma(minus_dm, period)

    plus_di = 100.0 * smoothed_plus_dm / tr_atr
    minus_di = 100.0 * smoothed_minus_dm / tr_atr

    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    dx = dx.where(di_sum != 0, 0.0)

    adx_vals = _wilder_rma(dx, period)

    return pd.DataFrame(
        {"plus_di": plus_di, "minus_di": minus_di, "adx": adx_vals}, index=bars.index
    )
