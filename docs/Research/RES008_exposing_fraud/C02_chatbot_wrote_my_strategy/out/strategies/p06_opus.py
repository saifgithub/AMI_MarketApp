import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """
    Donchian breakout + EMA trend filter with a 3x ATR trailing stop.

    Long entry : 50 EMA > 200 EMA and close > prior 55-day highest high.
    Short entry: 50 EMA < 200 EMA and close < prior 55-day lowest low.
    Long exit  : close < trailing stop (highest close since entry - 3*ATR20,
                 ratchets up only) or close < prior 20-day lowest low.
    Short exit : close > trailing stop (lowest close since entry + 3*ATR20,
                 ratchets down only) or close > prior 20-day highest high.

    Signals are decided at each bar's close. The entry reference price is the
    open of the bar after the signal, so the initial stop is
    entry_open -/+ 3*ATR20 (ATR taken from the signal bar). That open is only
    used once that bar is being processed, so no bar uses later data.
    Position sizing and portfolio risk limits are left to the execution layer.
    """
    FAST, SLOW = 50, 200
    ENTRY_N, EXIT_N = 55, 20
    ATR_N, ATR_MULT = 20, 3.0
    ALLOW_SHORT = True

    o = bars["open"].astype(float)
    h = bars["high"].astype(float)
    l = bars["low"].astype(float)
    c = bars["close"].astype(float)

    # Trend filter
    ema_f = c.ewm(span=FAST, adjust=False).mean().to_numpy()
    ema_s = c.ewm(span=SLOW, adjust=False).mean().to_numpy()

    # Wilder ATR
    prev_c = c.shift(1)
    tr = pandas.concat(
        [h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / ATR_N, adjust=False).mean().to_numpy()

    # Donchian channels built from prior bars only (shifted by one)
    hh_entry = h.rolling(ENTRY_N).max().shift(1).to_numpy()
    ll_entry = l.rolling(ENTRY_N).min().shift(1).to_numpy()
    ll_exit = l.rolling(EXIT_N).min().shift(1).to_numpy()
    hh_exit = h.rolling(EXIT_N).max().shift(1).to_numpy()

    op = o.to_numpy()
    cl = c.to_numpy()
    n = len(bars)
    out = np.zeros(n, dtype=int)

    pos = 0
    pending_fill = False
    entry_px = extreme = stop = sig_atr = np.nan

    for i in range(n):
        # Record the fill of the entry decided at the previous bar's close
        if pending_fill:
            entry_px = op[i] if np.isfinite(op[i]) else cl[i - 1]
            extreme = entry_px
            stop = entry_px - pos * ATR_MULT * sig_atr
            pending_fill = False

        ci, ai = cl[i], atr[i]

        if pos == 1:
            if np.isfinite(ci):
                extreme = max(extreme, ci)
                if np.isfinite(ai):
                    stop = max(stop, extreme - ATR_MULT * ai)
                if ci < stop or ci < ll_exit[i]:
                    pos = 0

        elif pos == -1:
            if np.isfinite(ci):
                extreme = min(extreme, ci)
                if np.isfinite(ai):
                    stop = min(stop, extreme + ATR_MULT * ai)
                if ci > stop or ci > hh_exit[i]:
                    pos = 0

        elif i >= SLOW and np.isfinite(ci) and np.isfinite(ai) and ai > 0:
            if ci > hh_entry[i] and ema_f[i] > ema_s[i]:
                pos, sig_atr, pending_fill = 1, ai, True
            elif ALLOW_SHORT and ci < ll_entry[i] and ema_f[i] < ema_s[i]:
                pos, sig_atr, pending_fill = -1, ai, True

        out[i] = pos

    return pandas.Series(out, index=bars.index, name="signal")
