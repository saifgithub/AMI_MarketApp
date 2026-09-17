import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    period = 30
    take_profit = 0.03
    stop_loss = 0.01

    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    pv = typical_price * bars["volume"]
    vwap = (pv.rolling(period).sum() / bars["volume"].rolling(period).sum()).to_numpy(dtype=float)

    n = len(bars)
    out = np.zeros(n, dtype=int)

    position = 0
    entry_price = np.nan
    above_prev = False
    have_prev = False

    for i in range(n):
        v = vwap[i]
        c = close[i]
        h = high[i]
        l = low[i]

        cross_up = False
        cross_down = False
        if not np.isnan(v):
            above = c > v
            if have_prev:
                if above and not above_prev:
                    cross_up = True
                elif (not above) and above_prev:
                    cross_down = True
            above_prev = above
            have_prev = True

        if position == 1:
            tp_price = entry_price * (1 + take_profit)
            sl_price = entry_price * (1 - stop_loss)
            if h >= tp_price:
                position = 0
                entry_price = np.nan
            elif l <= sl_price:
                position = 0
                entry_price = np.nan
            elif cross_down:
                position = -1
                entry_price = c
        elif position == -1:
            tp_price = entry_price * (1 - take_profit)
            sl_price = entry_price * (1 + stop_loss)
            if l <= tp_price:
                position = 0
                entry_price = np.nan
            elif h >= sl_price:
                position = 0
                entry_price = np.nan
            elif cross_up:
                position = 1
                entry_price = c

        if position == 0:
            if cross_up:
                position = 1
                entry_price = c
            elif cross_down:
                position = -1
                entry_price = c

        out[i] = position

    return pd.Series(out, index=bars.index, name="signal")
