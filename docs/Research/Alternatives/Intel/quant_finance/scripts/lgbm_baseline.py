#!/usr/bin/env python3
"""
LightGBM baseline for stock price-movement prediction.

Tests MULTIPLE prediction horizons (1/5/10/20 trading days) to find which is
most predictable. Uses strict walk-forward (expanding-window) validation --
no shuffling, no lookahead.

Anti-leakage rules enforced here:
  * Features at bar t use only data known at close of t.
  * Label = sign of forward return from close[t] -> close[t+h]; last h rows dropped.
  * Splits are strictly chronological; test always comes after train.
  * Cross-asset series are reindexed onto the ticker's calendar and forward-filled
    (never back-filled -- back-fill would leak future values backwards).
  * No scaling/imputation fit on full data (LightGBM needs none).

Usage: python3 lgbm_baseline.py [TICKER ...]
"""
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, accuracy_score

warnings.filterwarnings("ignore")

HORIZONS = [1, 5, 10, 20]          # trading days ahead
START = "2015-01-01"
END = "2026-08-01"
N_SPLITS = 5                        # walk-forward folds
SEED = 42


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def fetch(ticker, start=START, end=END):
    df = yf.download(ticker, start=start, end=end, progress=False,
                     auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def build_features(df, cross=None):
    """All features use only information available at the close of bar t."""
    X = pd.DataFrame(index=df.index)
    c, v = df["Close"], df["Volume"]
    ret1 = c.pct_change()

    # --- momentum / lagged returns ---
    for lag in (1, 2, 3, 5, 10, 20):
        X[f"ret_{lag}d"] = c.pct_change(lag)
    for lag in (1, 2, 3, 5):
        X[f"ret1_lag{lag}"] = ret1.shift(lag)

    # --- moving-average relationships ---
    for w in (5, 10, 20, 50, 200):
        ma = c.rolling(w).mean()
        X[f"px_over_ma{w}"] = c / ma - 1
    X["ma5_over_ma20"] = c.rolling(5).mean() / c.rolling(20).mean() - 1
    X["ma20_over_ma50"] = c.rolling(20).mean() / c.rolling(50).mean() - 1

    # --- volatility ---
    for w in (5, 10, 20, 60):
        X[f"vol_{w}d"] = ret1.rolling(w).std()
    X["vol_ratio_5_20"] = X["vol_5d"] / X["vol_20d"]
    hl = (df["High"] - df["Low"]) / c
    X["hl_range"] = hl
    X["hl_range_ma10"] = hl.rolling(10).mean()

    # --- volume ---
    X["vol_chg"] = v.pct_change()
    X["vol_over_ma20"] = v / v.rolling(20).mean() - 1

    # --- oscillators ---
    X["rsi_14"] = rsi(c, 14)
    X["rsi_5"] = rsi(c, 5)
    lo20, hi20 = c.rolling(20).min(), c.rolling(20).max()
    X["stoch_20"] = (c - lo20) / (hi20 - lo20)
    m20, s20 = c.rolling(20).mean(), c.rolling(20).std()
    X["bb_pos"] = (c - m20) / (2 * s20)

    # --- distance from longer-run extremes ---
    X["pct_off_52w_high"] = c / c.rolling(252).max() - 1
    X["pct_off_52w_low"] = c / c.rolling(252).min() - 1

    # --- calendar ---
    X["dow"] = df.index.dayofweek
    X["month"] = df.index.month

    # --- cross-asset (BTC / VIX / SPY), per the regime-aware LightGBM finding ---
    #
    # LEAKAGE NOTE (confirmed empirically 2026-08-15): a 24/7 asset's daily bar
    # is NOT contemporaneous with a US equity's daily bar even on the same
    # calendar date. BTC-USD's date-D "Close" aggregates through end-of-UTC-day
    # (~21:00-23:00 UTC), i.e. 4-8h AFTER the 20:00 UTC NYSE close on date D --
    # so an unlagged btc_* feature at row D encodes part of the overnight window
    # that the h=1 label is trying to predict. Verified: BTC daily Close on
    # 2026-08-10 (63910.59) matches its 21:00 UTC hourly bar (63910.42).
    # SPY and VIX close at 20:00 UTC and ARE contemporaneous -- no lag needed.
    LAG_DAYS = {"btc": 1}          # asset -> extra bars of lag required
    if cross:
        for name, series in cross.items():
            # reindex onto this ticker's calendar; ffill ONLY (bfill would leak)
            s = series.reindex(df.index).ffill()
            lag = LAG_DAYS.get(name, 0)
            if lag:
                s = s.shift(lag)   # use only bars that strictly precede close(D)
            X[f"{name}_ret1"] = s.pct_change()
            X[f"{name}_ret5"] = s.pct_change(5)
            X[f"{name}_vol20"] = s.pct_change().rolling(20).std()
            X[f"{name}_px_over_ma20"] = s / s.rolling(20).mean() - 1

    return X


def make_label(df, horizon):
    """Direction of forward return close[t] -> close[t+h]. NaN for last h bars."""
    fwd = df["Close"].shift(-horizon) / df["Close"] - 1
    return (fwd > 0).astype(int).where(fwd.notna()), fwd


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def walk_forward(X, y, fwd_ret, horizon, n_splits=N_SPLITS):
    """Expanding-window walk-forward. Purges `horizon` bars between train and
    test so the last training labels cannot overlap the test window."""
    n = len(X)
    fold_size = n // (n_splits + 1)
    rows = []

    for k in range(n_splits):
        tr_end = fold_size * (k + 1)
        te_start = tr_end + horizon          # purge gap -- prevents label overlap
        te_end = min(tr_end + fold_size, n)
        if te_start >= te_end:
            continue

        Xtr, ytr = X.iloc[:tr_end], y.iloc[:tr_end]
        Xte, yte = X.iloc[te_start:te_end], y.iloc[te_start:te_end]
        rte = fwd_ret.iloc[te_start:te_end]

        if ytr.nunique() < 2 or yte.nunique() < 2:
            continue

        model = lgb.LGBMClassifier(
            n_estimators=400, learning_rate=0.03, num_leaves=15,
            max_depth=5, min_child_samples=40, subsample=0.8,
            subsample_freq=1, colsample_bytree=0.7,
            reg_alpha=0.1, reg_lambda=1.0,
            random_state=SEED, verbose=-1, n_jobs=4,
        )
        model.fit(Xtr, ytr)

        p = model.predict_proba(Xte)[:, 1]
        pred = (p > 0.5).astype(int)

        # baseline: always predict the majority class seen in TRAIN only
        maj = int(ytr.mean() > 0.5)
        base_acc = accuracy_score(yte, np.full(len(yte), maj))

        # naive long-only strategy return vs model-gated return (no costs)
        strat = rte[pred == 1]
        rows.append({
            "fold": k + 1,
            "train_n": len(Xtr), "test_n": len(Xte),
            "auc": roc_auc_score(yte, p),
            "acc": accuracy_score(yte, pred),
            "base_acc": base_acc,
            "up_rate_test": yte.mean(),
            "signal_rate": pred.mean(),
            "mean_ret_when_long": strat.mean() if len(strat) else np.nan,
            "mean_ret_all": rte.mean(),
            "model": model,
        })
    return rows


def run_ticker(ticker, cross):
    df = fetch(ticker)
    if len(df) < 800:
        print(f"  !! {ticker}: only {len(df)} rows, skipping")
        return []

    X_all = build_features(df, cross)
    out = []

    for h in HORIZONS:
        y, fwd = make_label(df, h)
        data = X_all.copy()
        data["_y"], data["_fwd"] = y, fwd
        data = data.dropna()                      # drops warmup + last h bars
        if len(data) < 500:
            continue

        X = data.drop(columns=["_y", "_fwd"])
        y_c = data["_y"].astype(int)
        fwd_c = data["_fwd"]

        folds = walk_forward(X, y_c, fwd_c, h)
        if not folds:
            continue

        aucs = [f["auc"] for f in folds]
        accs = [f["acc"] for f in folds]
        bases = [f["base_acc"] for f in folds]
        out.append({
            "ticker": ticker, "horizon": h, "n": len(X),
            "auc_mean": np.mean(aucs), "auc_std": np.std(aucs),
            "acc_mean": np.mean(accs), "base_mean": np.mean(bases),
            "edge": np.mean(accs) - np.mean(bases),
            "folds": folds,
        })
        print(f"  {ticker:6s} h={h:2d}d  AUC {np.mean(aucs):.4f} "
              f"(±{np.std(aucs):.3f})  acc {np.mean(accs):.4f} "
              f"vs base {np.mean(bases):.4f}  edge {np.mean(accs)-np.mean(bases):+.4f}")
    return out


def main():
    tickers = sys.argv[1:] or ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "SPY"]

    print("Fetching cross-asset series (SPY / VIX / BTC)...")
    cross = {}
    for name, sym in [("spy", "SPY"), ("vix", "^VIX"), ("btc", "BTC-USD")]:
        try:
            s = fetch(sym)["Close"]
            cross[name] = s
            print(f"  {name}: {len(s)} rows")
        except Exception as e:
            print(f"  {name}: FAILED ({e})")

    print(f"\nWalk-forward: {N_SPLITS} expanding folds, purge gap = horizon")
    print(f"Period {START} -> {END}\n")

    results = []
    for t in tickers:
        try:
            results.extend(run_ticker(t, cross))
        except Exception as e:
            print(f"  !! {t} failed: {type(e).__name__}: {e}")

    if not results:
        print("No results.")
        return

    res = pd.DataFrame([{k: v for k, v in r.items() if k != "folds"}
                        for r in results])
    res.to_csv("/opt/saiful/llm_research/quant_finance/tmp/results.csv", index=False)

    print("\n" + "=" * 74)
    print("BY HORIZON (averaged across tickers)")
    print("=" * 74)
    summ = res.groupby("horizon").agg(
        auc_mean=("auc_mean", "mean"),
        auc_std=("auc_mean", "std"),
        acc_mean=("acc_mean", "mean"),
        base_mean=("base_mean", "mean"),
        edge=("edge", "mean"),
        n_tickers=("ticker", "count"),
    ).round(4)
    print(summ.to_string())

    print("\n" + "=" * 74)
    print("PER TICKER x HORIZON (AUC)")
    print("=" * 74)
    print(res.pivot(index="ticker", columns="horizon",
                    values="auc_mean").round(4).to_string())

    best = res.loc[res["auc_mean"].idxmax()]
    print(f"\nBest single cell: {best['ticker']} @ {int(best['horizon'])}d "
          f"-> AUC {best['auc_mean']:.4f}")

    # feature importance from the last fold of the best horizon
    bh = summ["auc_mean"].idxmax()
    print(f"\nTop features (horizon={bh}d, last fold, gain):")
    imps = []
    for r in results:
        if r["horizon"] == bh:
            m = r["folds"][-1]["model"]
            imps.append(pd.Series(m.booster_.feature_importance("gain"),
                                  index=m.feature_name_))
    if imps:
        agg = pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)
        for name, val in agg.head(15).items():
            print(f"    {name:24s} {val:12.1f}")


if __name__ == "__main__":
    main()
