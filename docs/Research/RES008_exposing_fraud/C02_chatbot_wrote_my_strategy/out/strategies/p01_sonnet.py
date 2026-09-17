import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]
    n = len(bars)

    pos = pd.Series(0, index=bars.index, dtype=int)
    if n == 0:
        return pos

    # --- Indicators (use only data up to and including current bar) ---
    sma200 = close.rolling(200).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    vol_sma20 = volume.rolling(20).mean()

    # Donchian breakout level: highest close of the PRIOR 20 bars (excludes today)
    donchian_high = close.shift(1).rolling(20).max()

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr14 = tr.rolling(14).mean()
    atr22 = tr.rolling(22).mean()

    in_position = False
    entry_price = np.nan
    initial_stop = np.nan
    highest_close_since_entry = np.nan
    entry_index = -1

    for i in range(n):
        c = close.iloc[i]

        if in_position:
            if c > highest_close_since_entry:
                highest_close_since_entry = c

            a22 = atr22.iloc[i]
            trailing_stop = (
                highest_close_since_entry - 3 * a22 if not np.isnan(a22) else -np.inf
            )
            stop_level = max(initial_stop, trailing_stop)

            days_held = i - entry_index
            r = entry_price - initial_stop
            unrealized = c - entry_price

            exit_trade = False
            if c < stop_level:
                exit_trade = True
            elif days_held >= 20 and unrealized < r:
                exit_trade = True

            if exit_trade:
                in_position = False
                entry_price = np.nan
                initial_stop = np.nan
                highest_close_since_entry = np.nan
                entry_index = -1
                pos.iloc[i] = 0
            else:
                pos.iloc[i] = 1
        else:
            s200 = sma200.iloc[i]
            e50 = ema50.iloc[i]
            dhigh = donchian_high.iloc[i]
            vsma = vol_sma20.iloc[i]
            a14 = atr14.iloc[i]

            if (
                not np.isnan(s200)
                and not np.isnan(e50)
                and not np.isnan(dhigh)
                and not np.isnan(vsma)
                and not np.isnan(a14)
            ):
                cond_uptrend = c > s200
                cond_trend_align = e50 > s200
                cond_breakout = c > dhigh
                cond_volume = volume.iloc[i] > 1.2 * vsma

                if cond_uptrend and cond_trend_align and cond_breakout and cond_volume:
                    in_position = True
                    entry_price = c
                    initial_stop = c - 2.5 * a14
                    highest_close_since_entry = c
                    entry_index = i
                    pos.iloc[i] = 1
                else:
                    pos.iloc[i] = 0
            else:
                pos.iloc[i] = 0

    return pos
