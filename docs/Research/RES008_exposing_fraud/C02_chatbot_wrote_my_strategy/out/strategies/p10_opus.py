import numpy as np
import pandas


def signal(bars: pandas.DataFrame) -> pandas.Series:
    """SuperTrend(10, 3.0) + RSI(14) + ADX/DMI(14, 14) trend-following strategy.

    Returns the target position decided at the close of each bar
    (1 = long, -1 = short, 0 = flat). The value at bar t uses only rows <= t.

    Rules
      Long : SuperTrend flipped up on this bar or within the previous 3 bars,
             ADX >= 20 and ADX > previous ADX, +DI > -DI, 50 < RSI < 70.
      Short: SuperTrend flipped down on this bar or within the previous 3 bars,
             ADX >= 20 and ADX > previous ADX, -DI > +DI, 30 < RSI < 50.
      New entries only when flat. Entry price = signal bar's close.
      Stop : SuperTrend line, updated every bar. Once price touches
             entry +/- 2R, the stop becomes max/min(SuperTrend, entry).
      Exit : stop touched intrabar, or SuperTrend flips against the position.

    Differences forced by the {-1, 0, 1} output:
      * 1%-risk position sizing is not represented (unit position).
      * The 50% partial exit at 2R cannot be expressed. The full position is
        managed like the runner leg (stop moves to breakeven after 2R).
      * An intrabar stop hit on bar t shows up as 0 at bar t's close. A new
        entry can be taken at that same close, as in the Pine version.
    """
    # ---- Parameters --------------------------------------------------------
    ATR_LEN, ST_MULT = 10, 3.0
    RSI_LEN = 14
    DI_LEN, ADX_SMOOTH, ADX_MIN = 14, 14, 20.0
    RSI_LONG_LO, RSI_LONG_HI = 50.0, 70.0
    RSI_SHORT_LO, RSI_SHORT_HI = 30.0, 50.0
    FLIP_WIN = 3
    TP1_R = 2.0

    n = len(bars)
    if n == 0:
        return pandas.Series(np.zeros(0, dtype=int), index=bars.index, name="position")

    h = bars["high"].to_numpy(dtype=float)
    l = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)

    def rma(x, length):
        """Wilder / TradingView ta.rma: SMA seed, then alpha = 1/length. Causal."""
        res = np.full(len(x), np.nan)
        alpha = 1.0 / length
        prev = np.nan
        for k in range(len(x)):
            if np.isnan(prev):
                if k + 1 >= length:
                    window = x[k + 1 - length:k + 1]
                    if not np.isnan(window).any():
                        prev = window.mean()
            elif not np.isnan(x[k]):
                prev = alpha * x[k] + (1.0 - alpha) * prev
            res[k] = prev
        return res

    # ---- True range --------------------------------------------------------
    prev_c = np.concatenate(([np.nan], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))  # NaN on bar 0
    tr_atr = tr.copy()
    tr_atr[0] = h[0] - l[0]  # ta.tr(true) behaviour on the first bar

    # ---- SuperTrend (TradingView ta.supertrend) ----------------------------
    atr = rma(tr_atr, ATR_LEN)
    hl2 = (h + l) / 2.0
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    st = np.full(n, np.nan)
    direction = np.ones(n)  # -1 = uptrend, 1 = downtrend (TradingView convention)
    for i in range(n):
        if np.isnan(atr[i]):
            continue
        ub = hl2[i] + ST_MULT * atr[i]
        lb = hl2[i] - ST_MULT * atr[i]
        if i > 0 and not np.isnan(atr[i - 1]):
            pub, plb = upper[i - 1], lower[i - 1]
            if not (lb > plb or c[i - 1] < plb):
                lb = plb
            if not (ub < pub or c[i - 1] > pub):
                ub = pub
            if st[i - 1] == pub:
                direction[i] = -1.0 if c[i] > ub else 1.0
            else:
                direction[i] = 1.0 if c[i] < lb else -1.0
        else:
            direction[i] = 1.0
        upper[i], lower[i] = ub, lb
        st[i] = lb if direction[i] < 0 else ub

    # ---- RSI (Wilder) ------------------------------------------------------
    delta = np.diff(c, prepend=np.nan)
    avg_gain = rma(np.maximum(delta, 0.0), RSI_LEN)
    avg_loss = rma(np.maximum(-delta, 0.0), RSI_LEN)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(
            avg_loss == 0, 100.0,
            np.where(avg_gain == 0, 0.0, 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)),
        )
    rsi[np.isnan(avg_gain) | np.isnan(avg_loss)] = np.nan

    # ---- DMI / ADX (TradingView ta.dmi) ------------------------------------
    up_move = np.diff(h, prepend=np.nan)
    down_move = -np.diff(l, prepend=np.nan)
    with np.errstate(invalid="ignore"):
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm[np.isnan(up_move)] = np.nan
    minus_dm[np.isnan(down_move)] = np.nan

    tr_s = rma(tr, DI_LEN)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * rma(plus_dm, DI_LEN) / tr_s
        minus_di = 100.0 * rma(minus_dm, DI_LEN) / tr_s
    # fixnan(): carry the last valid value forward (causal)
    plus_di = pandas.Series(plus_di).replace([np.inf, -np.inf], np.nan).ffill().to_numpy()
    minus_di = pandas.Series(minus_di).replace([np.inf, -np.inf], np.nan).ffill().to_numpy()
    di_sum = plus_di + minus_di
    with np.errstate(divide="ignore", invalid="ignore"):
        dx = np.abs(plus_di - minus_di) / np.where(di_sum == 0, 1.0, di_sum)
    adx = 100.0 * rma(dx, ADX_SMOOTH)

    # ---- Bar-by-bar position management ------------------------------------
    out = np.zeros(n, dtype=int)
    pos = 0
    entry = tp1 = stop = np.nan
    tp1_hit = False
    last_flip_up = last_flip_dn = -(10 ** 9)  # "never happened"

    for i in range(n):
        d = direction[i]
        if i > 0:
            if d < 0 and direction[i - 1] > 0:
                last_flip_up = i
            elif d > 0 and direction[i - 1] < 0:
                last_flip_dn = i

        # 1) Intrabar stop / 2R check, using levels fixed at the previous close
        if pos == 1:
            if l[i] <= stop:
                pos = 0
            elif h[i] >= tp1:
                tp1_hit = True
        elif pos == -1:
            if h[i] >= stop:
                pos = 0
            elif l[i] <= tp1:
                tp1_hit = True

        # 2) Entries, only if flat at this close
        flat = pos == 0
        if flat:
            tp1_hit = False
            adx_ok = i > 0 and adx[i] >= ADX_MIN and adx[i] > adx[i - 1]
            if (d < 0 and i - last_flip_up <= FLIP_WIN and adx_ok
                    and plus_di[i] > minus_di[i]
                    and RSI_LONG_LO < rsi[i] < RSI_LONG_HI
                    and c[i] - st[i] > 0):
                pos = 1
                entry = c[i]
                tp1 = entry + TP1_R * (entry - st[i])
            elif (d > 0 and i - last_flip_dn <= FLIP_WIN and adx_ok
                    and minus_di[i] > plus_di[i]
                    and RSI_SHORT_LO < rsi[i] < RSI_SHORT_HI
                    and st[i] - c[i] > 0):
                pos = -1
                entry = c[i]
                tp1 = entry - TP1_R * (st[i] - entry)

        # 3) Exit on SuperTrend flip (held positions) or set the stop for the next bar
        if pos == 1:
            if not flat and d > 0:
                pos = 0
            elif not np.isnan(st[i]):
                stop = max(st[i], entry) if tp1_hit else st[i]
        elif pos == -1:
            if not flat and d < 0:
                pos = 0
            elif not np.isnan(st[i]):
                stop = min(st[i], entry) if tp1_hit else st[i]

        out[i] = pos

    return pandas.Series(out, index=bars.index, name="position")
