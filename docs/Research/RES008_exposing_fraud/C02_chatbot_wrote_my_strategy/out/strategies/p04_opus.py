import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """
    RSI(2) mean-reversion pullback (Connors-style), long only, daily bars.

    Entry, evaluated at the bar's close:
        close > SMA(200) and RSI(2) < 10
    Exit, evaluated at the bar's close; the first one triggered wins:
        - profit exit:       close > SMA(5)
        - time stop:         10 trading days after the entry bar
        - catastrophic stop: bar's low <= entry close - 3 * ATR(14) at entry
          (The target position goes flat at that bar's close. A live stop
          order would fill intraday, at or below the stop price.)
    There is no re-entry on the same bar as an exit.

    Returns the target position at each bar's close: 1 = long, 0 = flat.
    It never returns -1, because shorting is disabled.
    Each value uses only data up to and including that bar.
    """
    RSI_LEN = 2
    RSI_ENTRY = 10.0
    TREND_LEN = 200
    EXIT_SMA_LEN = 5
    ATR_LEN = 14
    ATR_STOP_MULT = 3.0
    MAX_HOLD = 10

    if len(bars) == 0:
        return pandas.Series([], index=bars.index, dtype=int, name="signal")

    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    # Trailing moving averages (causal)
    sma_trend = close.rolling(TREND_LEN, min_periods=TREND_LEN).mean()
    sma_exit = close.rolling(EXIT_SMA_LEN, min_periods=EXIT_SMA_LEN).mean()

    # RSI(2) with Wilder smoothing (causal)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / RSI_LEN, adjust=False, min_periods=RSI_LEN).mean()
    avg_loss = loss.ewm(alpha=1.0 / RSI_LEN, adjust=False, min_periods=RSI_LEN).mean()
    denom = avg_gain + avg_loss
    rsi = 100.0 * avg_gain / denom.where(denom > 0)

    # ATR(14) with Wilder smoothing (causal)
    prev_close = close.shift(1)
    true_range = pandas.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / ATR_LEN, adjust=False, min_periods=ATR_LEN).mean()

    # NaN comparisons evaluate False, so there are no entries during warm-up
    entry_ok = ((close > sma_trend) & (rsi < RSI_ENTRY) & atr.notna()).to_numpy()

    c = close.to_numpy()
    lo = low.to_numpy()
    s_exit = sma_exit.to_numpy()
    a = atr.to_numpy()

    n = len(bars)
    pos = np.zeros(n, dtype=int)

    in_position = False
    entry_price = np.nan
    stop_price = np.nan
    bars_held = 0

    for i in range(n):
        if in_position:
            bars_held += 1
            hit_stop = lo[i] <= stop_price
            hit_profit_exit = c[i] > s_exit[i]
            timed_out = bars_held >= MAX_HOLD

            if hit_stop or hit_profit_exit or timed_out:
                in_position = False
                entry_price = np.nan
                stop_price = np.nan
                bars_held = 0
                pos[i] = 0
            else:
                pos[i] = 1
            continue  # no re-entry on the bar that was held or just exited

        if entry_ok[i]:
            in_position = True
            entry_price = c[i]
            stop_price = entry_price - ATR_STOP_MULT * a[i]
            bars_held = 0
            pos[i] = 1

    return pandas.Series(pos, index=bars.index, name="signal")
