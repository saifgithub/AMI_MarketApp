import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars["close"]
    sma50 = close.rolling(window=50, min_periods=50).mean()

    pos = np.zeros(len(bars), dtype=int)
    entry_price = np.nan

    for i in range(len(bars)):
        if np.isnan(sma50.iloc[i]):
            pos[i] = 0
            continue

        prev_pos = pos[i - 1] if i > 0 else 0
        c = close.iloc[i]

        if prev_pos == 1:
            # No stop loss / profit target defined for this strategy;
            # stay long as long as price remains above the 50 SMA.
            if c > sma50.iloc[i]:
                pos[i] = 1
            else:
                pos[i] = 0
                entry_price = np.nan
        else:
            if c > sma50.iloc[i]:
                pos[i] = 1
                entry_price = c
            else:
                pos[i] = 0

    return pd.Series(pos, index=bars.index, name="signal")
