import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close']
    high = bars['high']
    low = bars['low']

    # --- Indicators (causal, use only current and past bars) ---
    sma200 = close.rolling(200, min_periods=200).mean()
    sma5 = close.rolling(5, min_periods=5).mean()

    # RSI(2), Wilder's smoothing
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    period = 2
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi2 = 100 - (100 / (1 + rs))
    rsi2 = rsi2.fillna(100.0)  # no losses -> RSI = 100

    # ATR(14), Wilder's smoothing
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1
    ).max(axis=1)
    atr14 = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    close_v = close.values
    low_v = low.values
    sma200_v = sma200.values
    sma5_v = sma5.values
    rsi2_v = rsi2.values
    atr14_v = atr14.values

    n = len(bars)
    position = np.zeros(n)

    in_position = False
    entry_price = np.nan
    entry_atr = np.nan
    entry_idx = -1

    for i in range(n):
        if in_position:
            exit_now = False

            stop_price = entry_price - 2 * entry_atr
            if low_v[i] <= stop_price:
                exit_now = True
            elif not np.isnan(rsi2_v[i]) and rsi2_v[i] > 70:
                exit_now = True
            elif not np.isnan(sma5_v[i]) and close_v[i] > sma5_v[i]:
                exit_now = True
            elif (i - entry_idx) >= 10:
                exit_now = True

            if exit_now:
                in_position = False
                entry_price = np.nan
                entry_atr = np.nan
                entry_idx = -1
                position[i] = 0.0
            else:
                position[i] = 1.0
        else:
            if (
                i >= 1
                and not np.isnan(sma200_v[i])
                and not np.isnan(rsi2_v[i])
                and not np.isnan(atr14_v[i])
                and close_v[i] > sma200_v[i]
                and rsi2_v[i] < 10
                and close_v[i] < close_v[i - 1]
            ):
                in_position = True
                entry_price = close_v[i]
                entry_atr = atr14_v[i]
                entry_idx = i
                position[i] = 1.0
            else:
                position[i] = 0.0

    return pd.Series(position, index=bars.index, name='signal')
