import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """
    30-period rolling-VWAP cross strategy (mirror of the Pine Script version).

    - VWAP = rolling 30-bar sum(hlc3 * volume) / sum(volume)
    - Close crosses above VWAP -> target +1 (reverses any short)
    - Close crosses below VWAP -> target -1 (reverses any long)
    - Long: +3% take profit / -1% stop loss from the entry price.
      The entry price is the close of the signal bar.
      Starting the bar after entry, the exit triggers if that bar's high/low
      touches either level, and the position is flat at that bar's close.
    - Shorts have no TP/SL by default (use_short_exits = False, same as the
      Pine default); a short closes only on an opposite signal.
    - Each output value uses only data up to and including that bar.
    """
    vwap_len = 30
    tp_pct = 0.03
    sl_pct = 0.01
    use_short_exits = False

    close = bars["close"].astype(float)
    high = bars["high"].astype(float).fillna(close)
    low = bars["low"].astype(float).fillna(close)
    volume = bars["volume"].astype(float)

    # Rolling 30-period VWAP (backward-looking windows only)
    src = (high + low + close) / 3.0
    vol_sum = volume.rolling(vwap_len, min_periods=vwap_len).sum()
    pv_sum = (src * volume).rolling(vwap_len, min_periods=vwap_len).sum()
    vwap = pv_sum / vol_sum.where(vol_sum > 0)

    # Crossover / crossunder, same definition as Pine's ta.crossover / ta.crossunder
    prev_close = close.shift(1)
    prev_vwap = vwap.shift(1)
    long_sig = ((close > vwap) & (prev_close <= prev_vwap)).to_numpy()
    short_sig = ((close < vwap) & (prev_close >= prev_vwap)).to_numpy()

    c = close.to_numpy()
    h = high.to_numpy()
    lo = low.to_numpy()

    n = len(c)
    out = np.zeros(n, dtype=int)
    pos = 0
    entry = np.nan

    for i in range(n):
        # 1) Exits for a position carried in from the previous bar's close
        if pos == 1:
            stop = entry * (1.0 - sl_pct)
            target = entry * (1.0 + tp_pct)
            if lo[i] <= stop or h[i] >= target:
                pos = 0
                entry = np.nan
        elif pos == -1 and use_short_exits:
            stop = entry * (1.0 + sl_pct)
            target = entry * (1.0 - tp_pct)
            if h[i] >= stop or lo[i] <= target:
                pos = 0
                entry = np.nan

        # 2) New signals at this bar's close (no pyramiding: ignore same-side signals)
        if long_sig[i] and pos != 1:
            pos = 1
            entry = c[i]
        elif short_sig[i] and pos != -1:
            pos = -1
            entry = c[i]

        out[i] = pos

    return pandas.Series(out, index=bars.index, name="position")
