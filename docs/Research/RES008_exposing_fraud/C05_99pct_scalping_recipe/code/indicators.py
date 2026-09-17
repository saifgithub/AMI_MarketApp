"""
UT Bot and Schaff Trend Cycle (STC), exactly as C05's PREREGISTRATION.md
specifies them.

UT Bot: nLoss = key * ATR(period); a ratcheting trailing stop on close
(the "xATRTrailingStop" of the widely-shared public script) that only ever
tightens toward price while price stays on one side of it and jumps to the
opposite band the instant price crosses through; buy/sell signals fire on
the bar the close crosses the stop. ATR is the Wilder RMA of true range
(`_wilder_rma`, alpha = 1/period, seeded by a plain mean of the first
`period` consecutive non-NaN true-range values -- same construction as
`C03_tune_until_spectacular/code/indicators.py`, reused here rather than
imported because C05 must stand on its own and `common/` is read-only).
With period 1 the RMA recurrence seeds on the very first true-range value
and every step after multiplies the previous value by (1-1)=0 and adds the
new one, so ATR(1) reduces exactly to the bar's own true range -- no
special-casing needed.

STC: macd = EMA(close, fast) - EMA(close, slow); a stochastic (%K-style)
pass over macd across `length` bars, smoothed with factor 0.5 via the
recursive "PF" line (`pf[t] = pf[t-1] + 0.5 * (stoch[t] - pf[t-1])`, the
common public script's own smoothing, not a plain EMA); a second identical
stochastic-then-smooth pass over the first pass's PF line. Both stochastic
passes carry the previous smoothed value forward on a zero denominator
(highest == lowest over the lookback window), per the pre-registration.

Every function here is causal by construction: the value at bar t reads
only bars 0..t. `test_indicators.py` checks this by truncation (re-running
on a prefix must reproduce the same values at every bar of that prefix).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _wilder_rma(x: pd.Series, period: int) -> pd.Series:
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
    """Wilder average true range. period=1 reduces to the bar's own true range."""
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


def ut_bot(bars: pd.DataFrame, key: float, atr_period: int) -> pd.DataFrame:
    """UT Bot trailing stop and buy/sell crosses.

    Returns a DataFrame indexed like `bars` with columns:
      `stop` -- the ratcheting trailing-stop level (NaN until ATR warms up).
      `buy`  -- True on the bar close crosses above `stop` from at/below it.
      `sell` -- True on the bar close crosses below `stop` from at/above it.

    Standard public formula (xATRTrailingStop):
      nLoss = key * ATR(atr_period)
      if close > prevStop and prevClose > prevStop: stop = max(prevStop, close - nLoss)
      elif close < prevStop and prevClose < prevStop: stop = min(prevStop, close + nLoss)
      elif close > prevStop: stop = close - nLoss
      else: stop = close + nLoss
    which ratchets the stop toward price monotonically while price stays on
    one side of it, and jumps to the opposite band the instant price crosses
    through -- the classic "chandelier"/UT Bot construction.
    """
    close = bars["close"].astype(float).to_numpy()
    n = len(bars)
    n_loss = (key * atr(bars, atr_period)).to_numpy()

    stop = np.full(n, np.nan)
    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)

    first_valid = None
    for t in range(n):
        if not np.isnan(n_loss[t]):
            first_valid = t
            break
    if first_valid is None:
        return pd.DataFrame({"stop": stop, "buy": buy, "sell": sell}, index=bars.index)

    stop[first_valid] = close[first_valid] - n_loss[first_valid]

    for t in range(first_valid + 1, n):
        prev_stop = stop[t - 1]
        prev_close = close[t - 1]
        c = close[t]
        nl = n_loss[t]
        if np.isnan(nl) or np.isnan(prev_stop):
            continue

        if c > prev_stop and prev_close > prev_stop:
            stop[t] = max(prev_stop, c - nl)
        elif c < prev_stop and prev_close < prev_stop:
            stop[t] = min(prev_stop, c + nl)
        elif c > prev_stop:
            stop[t] = c - nl
        else:
            stop[t] = c + nl

        if c > stop[t] and prev_close <= prev_stop:
            buy[t] = True
        elif c < stop[t] and prev_close >= prev_stop:
            sell[t] = True

    return pd.DataFrame({"stop": stop, "buy": buy, "sell": sell}, index=bars.index)


def _stoch_smooth_pass(x: pd.Series, length: int, smooth: float) -> pd.Series:
    """One STC stochastic-then-smooth pass over `x`.

    `stoch[t] = 100 * (x[t] - lowest(x, length)[t]) / (highest(x, length)[t] - lowest(x, length)[t])`,
    carrying the PREVIOUS SMOOTHED value forward (not just the raw stoch)
    when the denominator is zero over the lookback window, per the
    pre-registration ("where the stochastic denominator is zero carry the
    previous value forward"). `pf[t] = pf[t-1] + smooth * (stoch[t] - pf[t-1])`,
    the common public script's own recursive smoothing (not a plain EMA),
    seeded with `pf = stoch` on the first bar where `x` itself is valid.
    """
    vals = x.astype(float).to_numpy()
    n = len(vals)
    lowest = x.rolling(length, min_periods=length).min().to_numpy()
    highest = x.rolling(length, min_periods=length).max().to_numpy()

    pf = np.full(n, np.nan)
    prev_pf = np.nan
    for t in range(n):
        if np.isnan(vals[t]) or np.isnan(lowest[t]) or np.isnan(highest[t]):
            continue
        denom = highest[t] - lowest[t]
        if denom == 0:
            stoch_t = prev_pf if not np.isnan(prev_pf) else 50.0
        else:
            stoch_t = 100.0 * (vals[t] - lowest[t]) / denom

        if np.isnan(prev_pf):
            pf[t] = stoch_t
        else:
            pf[t] = prev_pf + smooth * (stoch_t - prev_pf)
        prev_pf = pf[t]

    return pd.Series(pf, index=x.index)


def stc(close: pd.Series, length: int, fast: int, slow: int, smooth: float = 0.5) -> pd.Series:
    """Schaff Trend Cycle: two stochastic-then-smooth(0.5) passes over MACD.

    macd = EMA(close, fast) - EMA(close, slow); first pass is the
    stochastic-then-smooth of macd over `length`; second pass is the
    stochastic-then-smooth of the FIRST pass's output, again over `length`.
    Output is clamped to [0, 100] (the standard STC construction; the
    recursive PF smoothing can otherwise drift a hair outside the raw
    stochastic's [0, 100] range on the bar the denominator is exactly zero
    and a carried-forward value from a prior pass sits outside it).
    """
    close = close.astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow

    pass1 = _stoch_smooth_pass(macd, length, smooth)
    pass2 = _stoch_smooth_pass(pass1, length, smooth)

    return pass2.clip(lower=0.0, upper=100.0)
