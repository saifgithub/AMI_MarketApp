import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """
    Strategy 1: RSI(2) mean reversion with a 200-day trend filter.
    Long-only, daily bars.

    Entry (at the close, only when flat):
        close > SMA(200) and RSI(2) < 10
    Exit (at the close, first rule to trigger on a bar after the entry bar):
        1. close > SMA(5)
        2. disaster stop: close < entry_price - 3 * ATR(14), with ATR taken at entry
        3. time stop: 10 bars held
    No re-entry on the same bar as an exit, so a stop can't be undone
    by an immediate new entry.

    Returns the target position at each bar's close: 1 = long, 0 = flat
    (the strategy never goes short).
    Every value uses only data up to and including that bar.
    Assumes bars are in ascending chronological order.
    """
    RSI_LEN = 2
    RSI_ENTRY = 10.0
    SMA_TREND = 200
    SMA_EXIT = 5
    ATR_LEN = 14
    ATR_STOP_MULT = 3.0
    MAX_HOLD = 10

    def wilder(x: np.ndarray, n: int) -> np.ndarray:
        # Wilder smoothing. The seed is the simple average of the first n finite
        # values. NaN inputs are skipped, and the previous value is carried forward.
        out = np.full(x.shape[0], np.nan)
        finite = np.isfinite(x)
        idx = np.flatnonzero(finite)
        if idx.size < n:
            return out
        seed_end = idx[n - 1]
        prev = float(np.mean(x[idx[:n]]))
        out[seed_end] = prev
        for i in range(seed_end + 1, x.shape[0]):
            if finite[i]:
                prev = (prev * (n - 1) + x[i]) / n
            out[i] = prev
        return out

    n_bars = len(bars)
    if n_bars == 0:
        return pandas.Series(np.zeros(0, dtype=int), index=bars.index, name="signal")

    close_s = bars["close"].astype(float)
    close = close_s.to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)

    # Moving averages (trailing windows only).
    sma_trend = close_s.rolling(SMA_TREND, min_periods=SMA_TREND).mean().to_numpy()
    sma_exit = close_s.rolling(SMA_EXIT, min_periods=SMA_EXIT).mean().to_numpy()

    # RSI(2) with Wilder smoothing.
    delta = np.diff(close, prepend=np.nan)
    valid_delta = np.isfinite(delta)
    gain = np.where(valid_delta & (delta > 0), delta, 0.0)
    loss = np.where(valid_delta & (delta < 0), -delta, 0.0)
    gain[~valid_delta] = np.nan
    loss[~valid_delta] = np.nan
    avg_gain = wilder(gain, RSI_LEN)
    avg_loss = wilder(loss, RSI_LEN)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    rsi = np.where(avg_loss == 0.0, np.where(avg_gain == 0.0, 50.0, 100.0), rsi)

    # ATR(14) with Wilder smoothing.
    prev_close = np.empty_like(close)
    prev_close[0] = np.nan
    prev_close[1:] = close[:-1]
    tr = np.fmax(
        high - low,
        np.fmax(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    atr = wilder(tr, ATR_LEN)

    # Step through the bars, tracking the open position.
    pos = np.zeros(n_bars, dtype=int)
    in_pos = False
    entry_price = np.nan
    stop_level = np.nan
    bars_held = 0

    for i in range(n_bars):
        c = close[i]

        if in_pos:
            bars_held += 1
            exit_now = (
                (c > sma_exit[i])      # mean-reversion exit
                or (c < stop_level)    # disaster stop
                or (bars_held >= MAX_HOLD)  # time stop
            )
            if exit_now:
                in_pos = False
                entry_price = np.nan
                stop_level = np.nan
                bars_held = 0
                pos[i] = 0
            else:
                pos[i] = 1
            continue

        can_enter = (
            np.isfinite(c)
            and np.isfinite(sma_trend[i])
            and np.isfinite(rsi[i])
            and np.isfinite(atr[i])
        )
        if can_enter and c > sma_trend[i] and rsi[i] < RSI_ENTRY:
            in_pos = True
            entry_price = c
            stop_level = entry_price - ATR_STOP_MULT * atr[i]
            bars_held = 0
            pos[i] = 1

    return pandas.Series(pos, index=bars.index, name="signal")
