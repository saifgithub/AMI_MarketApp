import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    # --- Indicators (causal only) ---
    ema_fast = close.ewm(span=50, adjust=False).mean()
    ema_slow = close.ewm(span=200, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / 14, adjust=False).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=bars.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=bars.index
    )

    atr_wilder = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / atr_wilder
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / atr_wilder
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1.0 / 14, adjust=False).mean()

    donchian_high_20 = high.rolling(20).max().shift(1)
    donchian_low_20 = low.rolling(20).min().shift(1)
    donchian_high_10 = high.rolling(10).max().shift(1)
    donchian_low_10 = low.rolling(10).min().shift(1)

    long_bias = (ema_fast > ema_slow) & (adx > 20)
    short_bias = (ema_fast < ema_slow) & (adx > 20)

    n = len(bars)
    pos_arr = np.zeros(n, dtype=int)

    position = 0
    highest_close = np.nan
    lowest_close = np.nan
    stop_price = np.nan

    close_v = close.values
    high_v = high.values
    low_v = low.values
    ema_fast_v = ema_fast.values
    ema_slow_v = ema_slow.values
    atr_v = atr.values
    dhi20 = donchian_high_20.values
    dlo20 = donchian_low_20.values
    dhi10 = donchian_high_10.values
    dlo10 = donchian_low_10.values
    lbias = long_bias.values
    sbias = short_bias.values

    for i in range(n):
        c = close_v[i]
        h = high_v[i]
        l = low_v[i]
        a = atr_v[i]

        if position == 1:
            if not np.isnan(c):
                highest_close = c if np.isnan(highest_close) else max(highest_close, c)
            if not np.isnan(a) and not np.isnan(highest_close):
                trail = highest_close - 3.0 * a
                stop_price = trail if np.isnan(stop_price) else max(stop_price, trail)

            exit_now = False
            if not np.isnan(stop_price) and l <= stop_price:
                exit_now = True
            elif (
                not np.isnan(ema_fast_v[i])
                and not np.isnan(ema_slow_v[i])
                and ema_fast_v[i] < ema_slow_v[i]
            ):
                exit_now = True
            elif not np.isnan(dlo10[i]) and c < dlo10[i]:
                exit_now = True

            if exit_now:
                position = 0
                highest_close = np.nan
                stop_price = np.nan

        elif position == -1:
            if not np.isnan(c):
                lowest_close = c if np.isnan(lowest_close) else min(lowest_close, c)
            if not np.isnan(a) and not np.isnan(lowest_close):
                trail = lowest_close + 3.0 * a
                stop_price = trail if np.isnan(stop_price) else min(stop_price, trail)

            exit_now = False
            if not np.isnan(stop_price) and h >= stop_price:
                exit_now = True
            elif (
                not np.isnan(ema_fast_v[i])
                and not np.isnan(ema_slow_v[i])
                and ema_fast_v[i] > ema_slow_v[i]
            ):
                exit_now = True
            elif not np.isnan(dhi10[i]) and c > dhi10[i]:
                exit_now = True

            if exit_now:
                position = 0
                lowest_close = np.nan
                stop_price = np.nan

        if position == 0:
            if lbias[i] and not np.isnan(dhi20[i]) and not np.isnan(a) and c > dhi20[i]:
                position = 1
                highest_close = c
                stop_price = c - 2.0 * a
            elif sbias[i] and not np.isnan(dlo20[i]) and not np.isnan(a) and c < dlo20[i]:
                position = -1
                lowest_close = c
                stop_price = c + 2.0 * a

        pos_arr[i] = position

    return pd.Series(pos_arr, index=bars.index, name="signal")
