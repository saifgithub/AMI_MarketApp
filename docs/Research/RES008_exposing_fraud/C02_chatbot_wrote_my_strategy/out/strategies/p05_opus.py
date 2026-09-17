import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    # RSI(2) pullback in an uptrend, long-only, daily bars. Decisions are made at each bar's close.
    # Entry (when flat): close > SMA(200) and RSI(2) < 10.
    # Exit (first to trigger): close > SMA(5); 10 bars held;
    #   disaster stop: close < entry_price - 2.5 * ATR(10), with ATR measured on the entry bar.
    SMA_TREND = 200
    SMA_EXIT = 5
    RSI_LEN = 2
    RSI_ENTRY = 10.0
    MAX_HOLD = 10
    ATR_LEN = 10
    ATR_STOP_MULT = 2.5
    USE_STOP = True

    n = len(bars)
    if n == 0:
        return pandas.Series(np.zeros(0, dtype=np.int64), index=bars.index, name="signal")

    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    # Trailing (causal) moving averages
    sma_trend = close.rolling(SMA_TREND, min_periods=SMA_TREND).mean()
    sma_exit = close.rolling(SMA_EXIT, min_periods=SMA_EXIT).mean()

    # Wilder RSI (recursive EWM, causal)
    delta = close.diff()
    avg_up = delta.clip(lower=0).ewm(alpha=1.0 / RSI_LEN, adjust=False).mean()
    avg_dn = (-delta.clip(upper=0)).ewm(alpha=1.0 / RSI_LEN, adjust=False).mean()
    rsi = 100.0 - 100.0 / (1.0 + avg_up / avg_dn)  # avg_dn == 0 -> inf -> RSI 100

    # Wilder ATR (causal)
    prev_close = close.shift(1)
    true_range = pandas.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / ATR_LEN, adjust=False).mean()

    c = close.to_numpy()
    st = sma_trend.to_numpy()
    se = sma_exit.to_numpy()
    r = rsi.to_numpy()
    a = atr.to_numpy()

    pos = np.zeros(n, dtype=np.int64)
    in_pos = False
    entry_px = np.nan
    stop_px = np.nan
    entry_i = -1

    for i in range(n):
        if in_pos:
            held = i - entry_i
            exit_ma = c[i] > se[i]
            exit_time = held >= MAX_HOLD
            exit_stop = USE_STOP and (c[i] < stop_px)
            if exit_ma or exit_time or exit_stop:
                in_pos = False
                entry_px = np.nan
                stop_px = np.nan
                entry_i = -1
                pos[i] = 0  # flat at this close; no re-entry on the exit bar
            else:
                pos[i] = 1
        else:
            if c[i] > st[i] and r[i] < RSI_ENTRY:
                in_pos = True
                entry_px = c[i]
                entry_i = i
                stop_px = entry_px - ATR_STOP_MULT * a[i]
                pos[i] = 1
            else:
                pos[i] = 0

    return pandas.Series(pos, index=bars.index, name="signal")
