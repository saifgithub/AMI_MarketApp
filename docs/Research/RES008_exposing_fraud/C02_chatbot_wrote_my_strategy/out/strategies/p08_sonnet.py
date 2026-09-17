import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close'].values
    high = bars['high'].values
    low = bars['low'].values
    n = len(bars)

    # --- RSI(2) ---
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain, index=bars.index).rolling(2).mean().values
    avg_loss = pd.Series(loss, index=bars.index).rolling(2).mean().values

    safe_avg_loss = np.where(avg_loss == 0, 1.0, avg_loss)
    rs = np.where(avg_loss == 0, np.inf, avg_gain / safe_avg_loss)
    rsi2 = 100 - 100 / (1 + rs)
    rsi2 = np.where((avg_gain == 0) & (avg_loss == 0), 50.0, rsi2)
    rsi2 = np.where(np.isnan(avg_gain) | np.isnan(avg_loss), np.nan, rsi2)

    # --- Trend / exit SMAs ---
    close_s = bars['close']
    sma200 = close_s.rolling(200).mean().values
    sma5 = close_s.rolling(5).mean().values

    # --- ATR(14) for stop loss ---
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    atr14 = pd.Series(tr, index=bars.index).rolling(14).mean().values

    pos = np.zeros(n, dtype=int)
    position = 0
    entry_index = -1
    stop_price = np.nan

    for i in range(n):
        if position == 0:
            if (
                not np.isnan(sma200[i])
                and not np.isnan(rsi2[i])
                and close[i] > sma200[i]
                and rsi2[i] < 10
            ):
                position = 1
                entry_price = close[i]
                entry_index = i
                atr_val = atr14[i]
                stop_price = (
                    entry_price - 2 * atr_val
                    if not np.isnan(atr_val)
                    else entry_price * 0.95
                )
            pos[i] = position
        else:
            hold_days = i - entry_index
            exit_now = False
            if low[i] <= stop_price:
                exit_now = True
            elif not np.isnan(rsi2[i]) and rsi2[i] > 70:
                exit_now = True
            elif not np.isnan(sma5[i]) and close[i] > sma5[i]:
                exit_now = True
            elif hold_days >= 10:
                exit_now = True

            if exit_now:
                position = 0
                entry_index = -1
                stop_price = np.nan
                pos[i] = 0
            else:
                pos[i] = 1

    return pd.Series(pos, index=bars.index, name='signal')
