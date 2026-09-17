import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]

    # --- Indicators (all causal: each value uses only current and past rows) ---
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.fillna(100)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    vol_sma20 = volume.rolling(20).mean()

    close_a = close.to_numpy()
    high_a = high.to_numpy()
    low_a = low.to_numpy()
    volume_a = volume.to_numpy()
    ema50_a = ema50.to_numpy()
    ema200_a = ema200.to_numpy()
    atr_a = atr.to_numpy()
    rsi_a = rsi.to_numpy()
    hist_a = hist.to_numpy()
    vol_sma_a = vol_sma20.to_numpy()

    n = len(bars)
    pos_out = np.zeros(n, dtype=int)

    ATR_STOP_MULT = 1.5
    ATR_TARGET_MULT = 2.0
    PULLBACK_ATR_MULT = 1.0
    RSI_LOOKBACK = 5
    MIN_WARMUP = 200  # bars needed before 200 EMA / full stack is considered valid

    position = 0
    stop_price = np.nan
    target_price = np.nan

    for i in range(n):
        # --- Step 1: manage any position carried in from a previous bar,
        # using this bar's high/low (still data up to and including bar i) ---
        if position == 1:
            hit_stop = low_a[i] <= stop_price
            hit_target = high_a[i] >= target_price
            if hit_stop or hit_target:
                position = 0
        elif position == -1:
            hit_stop = high_a[i] >= stop_price
            hit_target = low_a[i] <= target_price
            if hit_stop or hit_target:
                position = 0

        # --- Step 2: if flat, look for a new entry using data through bar i's close ---
        if position == 0 and i >= MIN_WARMUP - 1 and i >= 1:
            if (
                not np.isnan(ema200_a[i])
                and not np.isnan(atr_a[i])
                and not np.isnan(rsi_a[i])
                and not np.isnan(rsi_a[i - 1])
                and not np.isnan(hist_a[i])
                and not np.isnan(hist_a[i - 1])
                and not np.isnan(vol_sma_a[i])
            ):
                uptrend = (
                    close_a[i] > ema50_a[i]
                    and close_a[i] > ema200_a[i]
                    and ema50_a[i] > ema200_a[i]
                )
                downtrend = (
                    close_a[i] < ema50_a[i]
                    and close_a[i] < ema200_a[i]
                    and ema50_a[i] < ema200_a[i]
                )
                pullback = abs(close_a[i] - ema50_a[i]) <= PULLBACK_ATR_MULT * atr_a[i]
                vol_ok = volume_a[i] >= vol_sma_a[i]

                lo = max(0, i - RSI_LOOKBACK)
                rsi_window = rsi_a[lo : i + 1]

                if uptrend and pullback and vol_ok:
                    rsi_cross_up = rsi_a[i - 1] < 50 <= rsi_a[i]
                    shallow = np.nanmin(rsi_window) >= 30
                    macd_bull = hist_a[i] > hist_a[i - 1]
                    if rsi_cross_up and shallow and macd_bull:
                        position = 1
                        entry_price = close_a[i]
                        stop_price = entry_price - ATR_STOP_MULT * atr_a[i]
                        target_price = entry_price + ATR_TARGET_MULT * atr_a[i]

                elif downtrend and pullback and vol_ok:
                    rsi_cross_dn = rsi_a[i - 1] > 50 >= rsi_a[i]
                    shallow = np.nanmax(rsi_window) <= 70
                    macd_bear = hist_a[i] < hist_a[i - 1]
                    if rsi_cross_dn and shallow and macd_bear:
                        position = -1
                        entry_price = close_a[i]
                        stop_price = entry_price + ATR_STOP_MULT * atr_a[i]
                        target_price = entry_price - ATR_TARGET_MULT * atr_a[i]

        pos_out[i] = position

    return pd.Series(pos_out, index=bars.index, name="signal")
