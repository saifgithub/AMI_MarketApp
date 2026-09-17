import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """RSI(2) mean-reversion strategy, long-only, daily bars.

    Entry (at the close, only when flat):
        close > 200-day SMA  and  RSI(2) < 10
    Exit (at the close, first condition met):
        1. close > 5-day SMA                      (profit exit)
        2. 10 trading days since the entry bar    (time stop)
        3. close <= 90% of entry price            (disaster stop)
    No re-entry on the same bar as an exit.

    Returns the target position decided at each bar's close:
    1 = long, 0 = flat (this strategy never returns -1).
    Uses only data up to and including each bar.
    """
    if not bars.index.is_monotonic_increasing:
        raise ValueError("bars.index must be sorted in ascending order")

    RSI_PERIOD = 2
    RSI_ENTRY = 10.0
    TREND_LEN = 200
    EXIT_MA_LEN = 5
    MAX_HOLD_BARS = 10
    STOP_PCT = 0.10

    close = bars["close"].astype(float)

    # Trailing simple moving averages (causal).
    sma_trend = close.rolling(TREND_LEN, min_periods=TREND_LEN).mean()
    sma_exit = close.rolling(EXIT_MA_LEN, min_periods=EXIT_MA_LEN).mean()

    # Wilder's RSI: Wilder smoothing == EMA with alpha = 1 / period (causal).
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    alpha = 1.0 / RSI_PERIOD
    avg_gain = gain.ewm(alpha=alpha, adjust=False, min_periods=RSI_PERIOD).mean().to_numpy()
    avg_loss = loss.ewm(alpha=alpha, adjust=False, min_periods=RSI_PERIOD).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    # No losses in the window: RSI = 100 (or 50 if there was no movement at all).
    rsi = np.where(avg_loss == 0.0, np.where(avg_gain == 0.0, 50.0, 100.0), rsi)

    c = close.to_numpy()
    s_trend = sma_trend.to_numpy()
    s_exit = sma_exit.to_numpy()

    n = len(c)
    pos = np.zeros(n, dtype=int)
    in_pos = False
    entry_price = np.nan
    entry_idx = -1

    for i in range(n):
        ci = c[i]

        # No valid price on this bar: cannot act, keep the current position.
        if not np.isfinite(ci):
            pos[i] = 1 if in_pos else 0
            continue

        if in_pos:
            profit_exit = ci > s_exit[i]
            time_exit = (i - entry_idx) >= MAX_HOLD_BARS
            stop_exit = ci <= entry_price * (1.0 - STOP_PCT)
            if profit_exit or time_exit or stop_exit:
                in_pos = False
                entry_price = np.nan
                entry_idx = -1
        elif ci > s_trend[i] and rsi[i] < RSI_ENTRY:
            # NaN indicators (warm-up period) compare False, so no entry.
            in_pos = True
            entry_price = ci
            entry_idx = i

        pos[i] = 1 if in_pos else 0

    return pandas.Series(pos, index=bars.index, name="signal")
