"""
Wilder RSI(14) and the long/flat state machine under test in C07 Part 1.

RSI is computed once over the FULL price series (never re-seeded inside a
sliced window) so that a `DEFINE`/`HOLDOUT`/intraday window never starts
"cold" -- the caller slices the resulting position series down to the
window afterward, exactly as `common/backtest.py` and C03's `indicators.py`
already do. `_wilder_rma` and `rsi` below are the same Wilder recurrence as
C03's `indicators.py` (seeded by a plain mean of the first `period`
consecutive non-NaN values, then the `(prev*(period-1)+v)/period` update);
re-derived here rather than imported because C07 may only write inside its
own folder.

State machine (long/flat only, as pre-registered): starts flat.
  flat -> long the first bar RSI < 30
  long -> flat the first bar RSI > 70
Anything else holds the current state (including RSI == 30 or RSI == 70
exactly, and any NaN warmup bar, which is treated as "no signal").
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


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
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


def rsi_state_machine(rsi_values: pd.Series) -> pd.Series:
    """Long/flat position decided at each bar's close from that bar's RSI.

    flat -> long the first bar rsi < 30; long -> flat the first bar rsi > 70;
    otherwise holds. A NaN RSI (warmup) never triggers a transition. The
    returned series is `target_position[t]` as `common.backtest.run_positions`
    expects it: decided from information at the close of bar t, not yet
    shifted for execution.
    """
    vals = rsi_values.to_numpy(dtype=float)
    n = len(vals)
    state = np.zeros(n)
    pos = 0.0
    for t in range(n):
        v = vals[t]
        if not np.isnan(v):
            if pos == 0.0 and v < 30.0:
                pos = 1.0
            elif pos == 1.0 and v > 70.0:
                pos = 0.0
        state[t] = pos
    return pd.Series(state, index=rsi_values.index, name="target_position")
