import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    # 50 SMA trend filter, long-only, with no stop loss or profit target.
    # Go long on a close above the 50 SMA and go flat on a close below it.
    # Otherwise keep the previous position.
    close = bars["close"].astype(float)
    sma50 = close.rolling(window=50, min_periods=50).mean()  # causal: uses bars up to and including i

    c = close.to_numpy()
    s = sma50.to_numpy()
    pos = np.zeros(len(bars), dtype=int)

    in_position = False
    for i in range(len(bars)):
        if not (np.isnan(c[i]) or np.isnan(s[i])):
            if not in_position and c[i] > s[i]:
                in_position = True
            elif in_position and c[i] < s[i]:
                in_position = False
        pos[i] = 1 if in_position else 0

    return pandas.Series(pos, index=bars.index, name="signal")
