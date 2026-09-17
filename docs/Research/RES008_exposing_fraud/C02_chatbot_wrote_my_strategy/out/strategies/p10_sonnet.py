import numpy as np
import pandas as pd


def signal(bars: pd.DataFrame) -> pd.Series:
    n = len(bars)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    # ---- parameters ----
    st_period, st_mult = 10, 3.0
    rsi_period = 14
    adx_period = 14
    adx_entry_th = 25.0
    adx_exit_th = 20.0
    rsi_lo, rsi_hi, rsi_mid = 40.0, 60.0, 50.0
    rsi_ob, rsi_os = 70.0, 30.0
    atr_stop_mult = 1.5

    # ---- True Range / ATRs ----
    prev_close = np.empty(n)
    prev_close[0] = np.nan
    prev_close[1:] = close[:-1]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr_s = pd.Series(tr)
    atr10 = tr_s.ewm(alpha=1 / st_period, adjust=False, min_periods=st_period).mean().to_numpy()
    atr14 = tr_s.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean().to_numpy()

    # ---- RSI(14) ----
    c_s = pd.Series(close)
    delta = c_s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = (100 - 100 / (1 + rs)).to_numpy()
    ag, al = avg_gain.to_numpy(), avg_loss.to_numpy()
    rsi = np.where((al == 0) & (ag > 0), 100.0, rsi)
    rsi = np.where((al == 0) & (ag == 0), 50.0, rsi)

    # ---- ADX(14) ----
    up_move = np.empty(n)
    up_move[0] = np.nan
    up_move[1:] = high[1:] - high[:-1]
    down_move = np.empty(n)
    down_move[0] = np.nan
    down_move[1:] = low[:-1] - low[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm[0] = 0.0
    minus_dm[0] = 0.0
    plus_dm_s = pd.Series(plus_dm).ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean()
    minus_dm_s = pd.Series(minus_dm).ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean()
    atr14_s = pd.Series(atr14).replace(0.0, np.nan)
    plus_di = 100 * plus_dm_s / atr14_s
    minus_di = 100 * minus_dm_s / atr14_s
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean().to_numpy()

    # ---- SuperTrend(10, 3.0) ----
    hl2 = (high + low) / 2.0
    basic_ub = hl2 + st_mult * atr10
    basic_lb = hl2 - st_mult * atr10
    final_ub = np.full(n, np.nan)
    final_lb = np.full(n, np.nan)
    st_line = np.full(n, np.nan)
    st_dir = np.zeros(n, dtype=int)

    for i in range(n):
        if np.isnan(atr10[i]):
            continue
        if np.isnan(final_ub[i - 1]) if i > 0 else True:
            final_ub[i] = basic_ub[i]
            final_lb[i] = basic_lb[i]
            st_dir[i] = 1 if close[i] >= final_lb[i] else -1
            st_line[i] = final_lb[i] if st_dir[i] == 1 else final_ub[i]
            continue
        final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]) else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]) else final_lb[i - 1]
        if st_line[i - 1] == final_ub[i - 1]:
            if close[i] <= final_ub[i]:
                st_line[i], st_dir[i] = final_ub[i], -1
            else:
                st_line[i], st_dir[i] = final_lb[i], 1
        else:
            if close[i] >= final_lb[i]:
                st_line[i], st_dir[i] = final_lb[i], 1
            else:
                st_line[i], st_dir[i] = final_ub[i], -1

    # ---- position state machine ----
    positions = np.zeros(n, dtype=int)
    pos = 0
    stop_level = np.nan

    for i in range(n):
        if np.isnan(atr10[i]) or np.isnan(rsi[i]) or np.isnan(adx[i]) or np.isnan(st_line[i]):
            pos = 0
            positions[i] = 0
            continue

        dir_i = st_dir[i]
        dir_prev = st_dir[i - 1] if i > 0 else 0
        rsi_i = rsi[i]
        rsi_prev = rsi[i - 1] if (i > 0 and not np.isnan(rsi[i - 1])) else np.nan
        adx_i = adx[i]

        long_cond = (
            dir_i == 1 and dir_prev == -1 and adx_i > adx_entry_th
            and not np.isnan(rsi_prev) and rsi_prev <= rsi_mid and rsi_i > rsi_mid
            and rsi_lo <= rsi_i <= rsi_hi
        )
        short_cond = (
            dir_i == -1 and dir_prev == 1 and adx_i > adx_entry_th
            and not np.isnan(rsi_prev) and rsi_prev >= rsi_mid and rsi_i < rsi_mid
            and rsi_lo <= rsi_i <= rsi_hi
        )

        if pos == 1:
            exit_flip = dir_i == -1
            trail_stop = max(st_line[i], stop_level)
            stop_hit = low[i] <= trail_stop
            rsi_exhaustion = (not np.isnan(rsi_prev)) and rsi_prev > rsi_ob and rsi_i < rsi_prev
            adx_weak = adx_i < adx_exit_th
            if exit_flip or stop_hit or rsi_exhaustion or adx_weak:
                pos = 0
                stop_level = np.nan
        elif pos == -1:
            exit_flip = dir_i == 1
            trail_stop = min(st_line[i], stop_level)
            stop_hit = high[i] >= trail_stop
            rsi_exhaustion = (not np.isnan(rsi_prev)) and rsi_prev < rsi_os and rsi_i > rsi_prev
            adx_weak = adx_i < adx_exit_th
            if exit_flip or stop_hit or rsi_exhaustion or adx_weak:
                pos = 0
                stop_level = np.nan

        if pos == 0:
            if long_cond:
                pos = 1
                stop_level = close[i] - atr_stop_mult * atr10[i]
            elif short_cond:
                pos = -1
                stop_level = close[i] + atr_stop_mult * atr10[i]

        positions[i] = pos

    return pd.Series(positions, index=bars.index, name="signal")
