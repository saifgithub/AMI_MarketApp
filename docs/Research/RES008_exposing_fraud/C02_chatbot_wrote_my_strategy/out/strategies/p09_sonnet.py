import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars["close"].astype(float)

    fast_len = 50
    slow_len = 200

    sma_fast = close.rolling(window=fast_len, min_periods=fast_len).mean()
    sma_slow = close.rolling(window=slow_len, min_periods=slow_len).mean()

    fast_vals = sma_fast.to_numpy()
    slow_vals = sma_slow.to_numpy()
    close_vals = close.to_numpy()

    n = len(bars)
    pos_vals = np.zeros(n, dtype=int)  # writable array, independent of pandas internals

    in_position = False
    entry_price = np.nan  # tracked for completeness; this strategy uses no
                           # stop loss / profit target, only the MA crossover

    for i in range(n):
        f = fast_vals[i]
        s = slow_vals[i]

        if np.isnan(f) or np.isnan(s):
            pos_vals[i] = pos_vals[i - 1] if i > 0 else 0
            continue

        if f > s:
            if not in_position:
                in_position = True
                entry_price = close_vals[i]
            pos_vals[i] = 1
        elif f < s:
            if in_position:
                in_position = False
                entry_price = np.nan
            pos_vals[i] = 0
        else:
            pos_vals[i] = pos_vals[i - 1] if i > 0 else 0

    return pd.Series(pos_vals, index=bars.index, dtype=int)
