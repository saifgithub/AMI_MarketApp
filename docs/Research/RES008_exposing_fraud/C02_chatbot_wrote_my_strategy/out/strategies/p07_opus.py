import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """RSI + MACD trend-pullback strategy (daily bars).

    Returns the target position decided at each bar's close (1 long, -1 short, 0 flat).
    Orders are assumed to fill at the next bar's open, so each trade's entry price is the
    open of the bar after its signal. Stop, target and breakeven are tracked internally from
    that price. When a level is touched intrabar, the target becomes 0 at that bar's close.
    Every value uses only rows up to and including its own bar.
    """
    # ---- Parameters -------------------------------------------------------
    rsi_len, macd_fast, macd_slow, macd_sig = 14, 12, 26, 9
    ema_len, atr_len, lookback = 200, 14, 5
    rsi_pull_long, rsi_pull_short, rsi_ob, rsi_os = 40.0, 60.0, 70.0, 30.0
    stop_atr, target_atr, be_atr, max_bars = 1.5, 3.0, 1.5, 20

    o = bars["open"].astype(float)
    h = bars["high"].astype(float)
    l = bars["low"].astype(float)
    c = bars["close"].astype(float)

    # ---- Indicators (all causal) ------------------------------------------
    # RSI, Wilder smoothing
    delta = c.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / rsi_len, min_periods=rsi_len, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / rsi_len, min_periods=rsi_len, adjust=False).mean()
    rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    # MACD 12/26/9
    macd = c.ewm(span=macd_fast, adjust=False).mean() - c.ewm(span=macd_slow, adjust=False).mean()
    macd_signal = macd.ewm(span=macd_sig, adjust=False).mean()

    # 200 EMA trend filter
    ema = c.ewm(span=ema_len, min_periods=ema_len, adjust=False).mean()

    # ATR 14, Wilder smoothing
    prev_close = c.shift(1)
    true_range = pandas.concat(
        [h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / atr_len, min_periods=atr_len, adjust=False).mean()

    # MACD crosses on the current bar
    cross_up = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
    cross_dn = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))

    # Entry conditions (current RSI bounds force the pullback extreme into the prior 5 bars)
    rsi_lo = rsi.rolling(lookback + 1).min()
    rsi_hi = rsi.rolling(lookback + 1).max()
    long_entry = (
        (c > ema)
        & (rsi_lo <= rsi_pull_long)
        & (rsi > rsi_pull_long)
        & (rsi < rsi_ob)
        & cross_up
    )
    short_entry = (
        (c < ema)
        & (rsi_hi >= rsi_pull_short)
        & (rsi > rsi_os)
        & (rsi < rsi_pull_short)
        & cross_dn
    )

    # ---- Bar-by-bar state machine -----------------------------------------
    O, H, L, C = o.to_numpy(), h.to_numpy(), l.to_numpy(), c.to_numpy()
    R, A = rsi.to_numpy(), atr.to_numpy()
    x_up, x_dn = cross_up.to_numpy(), cross_dn.to_numpy()
    le, se = long_entry.to_numpy(), short_entry.to_numpy()

    n = len(bars)
    out = np.zeros(n, dtype=int)

    side = 0        # position held during the current bar
    pending = 0     # new trade decided at the previous close, filled at this bar's open
    entry = stop = target = atr_e = 0.0
    entry_bar = 0

    for i in range(n):
        # 1) Fill a new trade at this bar's open
        if pending != 0:
            side = pending
            entry = O[i] if np.isfinite(O[i]) else C[i - 1]
            atr_e = A[i - 1]  # ATR of the signal bar, fixed for the trade
            stop = entry - side * stop_atr * atr_e
            target = entry + side * target_atr * atr_e
            entry_bar = i
            pending = 0

        exit_now = False
        block = 0  # side that may not be re-entered this bar (after a signal exit)

        if side != 0:
            # 2) Intrabar stop first (conservative), then profit target
            if (side == 1 and L[i] <= stop) or (side == -1 and H[i] >= stop):
                exit_now = True
            elif (side == 1 and H[i] >= target) or (side == -1 and L[i] <= target):
                exit_now = True
            else:
                # 3) Move the stop to breakeven after +1R (takes effect from the next bar)
                if (side == 1 and H[i] >= entry + be_atr * atr_e) or (
                    side == -1 and L[i] <= entry - be_atr * atr_e
                ):
                    stop = entry

                # 4) Close-of-bar exit signals
                if side == 1:
                    macd_exit = bool(x_dn[i])
                    rsi_exit = bool(R[i - 1] >= rsi_ob and R[i] < rsi_ob)
                else:
                    macd_exit = bool(x_up[i])
                    rsi_exit = bool(R[i - 1] <= rsi_os and R[i] > rsi_os)
                time_exit = (i - entry_bar + 1) >= max_bars

                if macd_exit or rsi_exit or time_exit:
                    exit_now = True
                    block = side

        # Hold the open position
        if side != 0 and not exit_now:
            out[i] = side
            continue

        # 5) Flat or exiting: look for a new entry (reversals allowed, same-side re-entry is not)
        atr_ok = bool(np.isfinite(A[i]) and A[i] > 0)
        new = 0
        if atr_ok and le[i] and block != 1:
            new = 1
        elif atr_ok and se[i] and block != -1:
            new = -1

        out[i] = new
        pending = new
        side = 0

    return pandas.Series(out, index=bars.index, name="signal")
