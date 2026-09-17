import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]

    # ---------- RSI(14), Wilder smoothing ----------
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1 / 14, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / 14, adjust=False).mean()

    au = avg_up.values
    ad = avg_down.values
    rs = np.divide(au, ad, out=np.full_like(au, np.nan), where=ad != 0)
    rsi_arr = 100.0 - 100.0 / (1.0 + rs)
    rsi_arr = np.where(ad == 0, np.where(au == 0, 50.0, 100.0), rsi_arr)

    # ---------- MACD(12,26,9) ----------
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    # ---------- ATR(14), Wilder smoothing ----------
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # ---------- Trend / trailing EMAs ----------
    ema200 = close.ewm(span=200, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()

    n = len(bars)
    rsi_v = rsi_arr
    macd_v = macd_line.values
    sig_v = signal_line.values
    hist_v = hist.values
    atr_v = atr.values
    close_v = close.values
    high_v = high.values
    low_v = low.values
    ema200_v = ema200.values
    ema20_v = ema20.values

    pos = np.zeros(n, dtype=int)

    position = 0
    entry_price = np.nan
    stop_loss = np.nan
    take_profit = np.nan
    overbought_flag = False
    oversold_flag = False

    for i in range(1, n):
        # ---------- Manage open position: exits ----------
        if position == 1:
            exit_now = False
            if low_v[i] <= stop_loss:
                exit_now = True
            elif high_v[i] >= take_profit:
                exit_now = True
            else:
                macd_bear_cross = macd_v[i - 1] >= sig_v[i - 1] and macd_v[i] < sig_v[i]
                if rsi_v[i] > 70:
                    overbought_flag = True
                rsi_turn_down = overbought_flag and rsi_v[i] < rsi_v[i - 1]
                if macd_bear_cross or rsi_turn_down:
                    exit_now = True
                else:
                    if close_v[i] > entry_price and close_v[i] > ema20_v[i]:
                        stop_loss = max(stop_loss, ema20_v[i])

            if exit_now:
                position = 0
                entry_price = stop_loss = take_profit = np.nan
                overbought_flag = False
                oversold_flag = False

        elif position == -1:
            exit_now = False
            if high_v[i] >= stop_loss:
                exit_now = True
            elif low_v[i] <= take_profit:
                exit_now = True
            else:
                macd_bull_cross = macd_v[i - 1] <= sig_v[i - 1] and macd_v[i] > sig_v[i]
                if rsi_v[i] < 30:
                    oversold_flag = True
                rsi_turn_up = oversold_flag and rsi_v[i] > rsi_v[i - 1]
                if macd_bull_cross or rsi_turn_up:
                    exit_now = True
                else:
                    if close_v[i] < entry_price and close_v[i] < ema20_v[i]:
                        stop_loss = min(stop_loss, ema20_v[i])

            if exit_now:
                position = 0
                entry_price = stop_loss = take_profit = np.nan
                overbought_flag = False
                oversold_flag = False

        # ---------- Flat: check entries ----------
        if position == 0:
            macd_bull_cross = macd_v[i - 1] <= sig_v[i - 1] and macd_v[i] > sig_v[i]
            macd_bear_cross = macd_v[i - 1] >= sig_v[i - 1] and macd_v[i] < sig_v[i]

            rsi_ok_long = (40.0 <= rsi_v[i] <= 60.0) or (rsi_v[i - 1] < 30.0 <= rsi_v[i])
            rsi_ok_short = (40.0 <= rsi_v[i] <= 60.0) or (rsi_v[i - 1] > 70.0 >= rsi_v[i])
            extreme_ok = 20.0 < rsi_v[i] < 80.0

            long_entry = (
                macd_bull_cross
                and hist_v[i] > 0
                and rsi_ok_long
                and extreme_ok
                and close_v[i] > ema200_v[i]
                and not np.isnan(atr_v[i])
            )
            short_entry = (
                macd_bear_cross
                and hist_v[i] < 0
                and rsi_ok_short
                and extreme_ok
                and close_v[i] < ema200_v[i]
                and not np.isnan(atr_v[i])
            )

            if long_entry:
                position = 1
                entry_price = close_v[i]
                stop_loss = entry_price - 1.5 * atr_v[i]
                risk = entry_price - stop_loss
                take_profit = entry_price + 2.0 * risk
            elif short_entry:
                position = -1
                entry_price = close_v[i]
                stop_loss = entry_price + 1.5 * atr_v[i]
                risk = stop_loss - entry_price
                take_profit = entry_price - 2.0 * risk

        pos[i] = position

    return pd.Series(pos, index=bars.index, name="signal")
