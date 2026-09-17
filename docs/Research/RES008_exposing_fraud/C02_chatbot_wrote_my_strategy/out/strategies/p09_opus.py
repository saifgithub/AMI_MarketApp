import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    # 200-day SMA trend strategy: long when the close is above the SMA, flat when below.
    # Long-only (never -1). The strategy has no stop loss or profit target, so no
    # entry price needs to be tracked. The SMA cross is the only exit.
    close = bars["close"].astype(float)

    # Trailing window that includes the current bar only, so there is no lookahead.
    sma = close.rolling(window=200, min_periods=200).mean()

    c = close.to_numpy()
    s = sma.to_numpy()
    out = np.zeros(len(c), dtype=int)

    pos = 0
    for i in range(len(c)):
        # Before the 200-bar warmup, or on missing data, there is no signal: keep the current state.
        if not (np.isnan(c[i]) or np.isnan(s[i])):
            if pos == 0 and c[i] > s[i]:
                pos = 1  # entry: close above the SMA
            elif pos == 1 and c[i] < s[i]:
                pos = 0  # exit: close below the SMA
            # close == SMA: neither rule triggers, so hold the current state
        out[i] = pos

    return pandas.Series(out, index=bars.index, name="signal")
