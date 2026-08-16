#!/usr/bin/env python3
"""
LightGBM baseline for INTRADAY price-movement prediction.

Same anti-leakage discipline as lgbm_baseline.py, adapted for intraday bars:
  * Overnight gaps are excluded from labels -- a forward return is only used
    when entry and exit bars fall on the SAME session. Otherwise the label
    mostly measures the overnight jump, not intraday movement.
  * Rolling features are computed within-session (grouped by date) so windows
    never straddle the close/open boundary.
  * Walk-forward with a purge gap of `horizon` bars, same as daily.

yfinance intraday limits (verified 2026-08-15):
    1m  -> 7 days      5m/15m/30m -> 60 days      1h -> unavailable
"""
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, accuracy_score

warnings.filterwarnings("ignore")

SEED = 42
N_SPLITS = 5

# (interval, period, [horizons in BARS])
CONFIGS = [
    ("1m",  "7d",  [1, 5, 15, 30]),        # 1min .. 30min ahead
    ("5m",  "60d", [1, 3, 6, 12]),         # 5min .. 1hr ahead
    ("15m", "60d", [1, 2, 4, 8]),          # 15min .. 2hr ahead
    ("30m", "60d", [1, 2, 4]),             # 30min .. 2hr ahead
]


def fetch(ticker, interval, period):
    df = yf.download(ticker, interval=interval, period=period,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def rsi(close, n=14):
    d = close.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def build_features(df, bars_per_session=None):
    """Within-session features only -- rolling windows never cross sessions.

    Window sizes are scaled to the session length: a 60-bar window is fine on
    1m bars (390/session) but exceeds a 15m session (26 bars) entirely, which
    would NaN out every row. Windows are capped at ~1/3 of the session.
    """
    X = pd.DataFrame(index=df.index)
    c, v, h, lo = df["Close"], df["Volume"], df["High"], df["Low"]
    day = df.index.date

    if bars_per_session is None:
        bars_per_session = int(pd.Series(day).value_counts().median())
    cap = max(3, bars_per_session // 3)
    windows = sorted({w for w in (5, 10, 20, 60) if w <= cap} | {3})
    lags = [l for l in (1, 2, 3, 5, 10, 20) if l <= cap]
    rsi_n = min(14, cap)
    bb_n = min(20, cap)

    g = c.groupby(day)
    ret1 = g.pct_change()

    for lag in lags:
        X[f"ret_{lag}b"] = g.pct_change(lag)
    for lag in [l for l in (1, 2, 3, 5) if l <= cap]:
        X[f"ret1_lag{lag}"] = ret1.groupby(day).shift(lag)

    for w in windows:
        ma = c.groupby(day).transform(lambda s, w=w: s.rolling(w).mean())
        X[f"px_over_ma{w}"] = c / ma - 1
        X[f"vol_{w}b"] = ret1.groupby(day).transform(
            lambda s, w=w: s.rolling(w).std())

    X["hl_range"] = (h - lo) / c
    X["vol_chg"] = v.groupby(day).pct_change()
    X["vol_over_ma"] = v / v.groupby(day).transform(
        lambda s: s.rolling(bb_n).mean()) - 1

    X["rsi"] = c.groupby(day).transform(lambda s: rsi(s, rsi_n))
    m20 = c.groupby(day).transform(lambda s: s.rolling(bb_n).mean())
    s20 = c.groupby(day).transform(lambda s: s.rolling(bb_n).std())
    X["bb_pos"] = (c - m20) / (2 * s20)

    # position within the session (open drift / close auction effects)
    X["bar_of_day"] = pd.Series(
        np.arange(len(df)), index=df.index).groupby(day).rank()
    sess_open = c.groupby(day).transform("first")
    X["px_over_open"] = c / sess_open - 1
    X["dow"] = df.index.dayofweek

    return X


def make_label(df, horizon):
    """Forward return over `horizon` bars, ONLY within the same session."""
    day = pd.Series(df.index.date, index=df.index)
    fwd_px = df["Close"].shift(-horizon)
    fwd_day = day.shift(-horizon)
    same = (day == fwd_day)                       # exclude overnight crossings
    fwd = (fwd_px / df["Close"] - 1).where(same)
    return (fwd > 0).astype(int).where(fwd.notna()), fwd


def walk_forward(X, y, horizon, n_splits=N_SPLITS):
    n = len(X)
    fold = n // (n_splits + 1)
    rows = []
    for k in range(n_splits):
        tr_end = fold * (k + 1)
        te_start = tr_end + horizon
        te_end = min(tr_end + fold, n)
        if te_start >= te_end:
            continue
        Xtr, ytr = X.iloc[:tr_end], y.iloc[:tr_end]
        Xte, yte = X.iloc[te_start:te_end], y.iloc[te_start:te_end]
        if ytr.nunique() < 2 or yte.nunique() < 2:
            continue
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.03, num_leaves=15, max_depth=5,
            min_child_samples=40, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
            random_state=SEED, verbose=-1, n_jobs=4)
        m.fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
        pred = (p > 0.5).astype(int)
        maj = int(ytr.mean() > 0.5)
        rows.append({
            "auc": roc_auc_score(yte, p),
            "acc": accuracy_score(yte, pred),
            "base": accuracy_score(yte, np.full(len(yte), maj)),
        })
    return rows


def main():
    tickers = sys.argv[1:] or ["AAPL", "NVDA", "SPY"]
    results = []

    for interval, period, horizons in CONFIGS:
        bar_min = int(interval.replace("m", ""))
        print(f"\n{'='*74}\n{interval} bars (period={period})\n{'='*74}")
        for t in tickers:
            try:
                df = fetch(t, interval, period)
            except Exception as e:
                print(f"  !! {t} fetch failed: {type(e).__name__}")
                continue
            if len(df) < 400:
                print(f"  !! {t}: only {len(df)} bars, skipping")
                continue

            X_all = build_features(df)
            for hb in horizons:
                y, fwd = make_label(df, hb)
                d = X_all.copy()
                d["_y"] = y
                d = d.dropna()
                if len(d) < 300:
                    continue
                X, yy = d.drop(columns=["_y"]), d["_y"].astype(int)
                folds = walk_forward(X, yy, hb)
                if not folds:
                    continue
                auc = np.mean([f["auc"] for f in folds])
                acc = np.mean([f["acc"] for f in folds])
                base = np.mean([f["base"] for f in folds])
                mins = hb * bar_min
                results.append({
                    "interval": interval, "ticker": t, "bars": hb,
                    "minutes": mins, "n": len(X), "auc": auc,
                    "acc": acc, "base": base, "edge": acc - base})
                print(f"  {t:5s} h={hb:3d} bars ({mins:4d} min)  n={len(X):5d}  "
                      f"AUC {auc:.4f}  acc {acc:.4f} vs base {base:.4f}  "
                      f"edge {acc-base:+.4f}")

    if not results:
        print("\nNo results.")
        return

    res = pd.DataFrame(results)
    res.to_csv("/opt/saiful/llm_research/quant_finance/tmp/results_intraday.csv",
               index=False)

    print(f"\n{'='*74}\nBY HORIZON IN MINUTES (averaged across tickers/intervals)\n{'='*74}")
    print(res.groupby("minutes").agg(
        auc=("auc", "mean"), acc=("acc", "mean"),
        base=("base", "mean"), edge=("edge", "mean"),
        n_cells=("ticker", "count")).round(4).to_string())

    print(f"\n{'='*74}\nBY BAR INTERVAL\n{'='*74}")
    print(res.groupby("interval").agg(
        auc=("auc", "mean"), edge=("edge", "mean"),
        n_cells=("ticker", "count")).round(4).to_string())

    best = res.loc[res["auc"].idxmax()]
    print(f"\nBest cell: {best['ticker']} {best['interval']} bars, "
          f"{int(best['minutes'])}min horizon -> AUC {best['auc']:.4f}, "
          f"edge {best['edge']:+.4f}")
    print(f"\nCells with AUC > 0.55: {(res['auc'] > 0.55).sum()} / {len(res)}")
    print(f"Cells with positive edge vs baseline: {(res['edge'] > 0).sum()} / {len(res)}")


if __name__ == "__main__":
    main()
