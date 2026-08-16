#!/usr/bin/env python3
"""
Cross-sectional ranking test -- the fix for "AUC > 0.5 but edge < 0".

The single-ticker experiments failed to beat an always-up baseline because
stocks drift upward: predicting absolute direction means fighting a ~60/40
base rate. Here the label is RELATIVE instead:

    does ticker i beat the CROSS-SECTIONAL MEDIAN return of the universe
    over the next H days?

By construction that label is ~50/50, so the majority-class baseline is 0.50
and any AUC above it is real, usable edge. It also strips out market beta:
we no longer need to predict the market, only relative ordering within it --
which is exactly what the measured AUC ~0.55 ranking ability represents.

Evaluation goes beyond AUC to the thing that actually matters:
    long-short decile spread = mean fwd return of top-ranked names
                             - mean fwd return of bottom-ranked names
This is reported gross of costs (flagged in the output, not hidden).

Walk-forward splits are BY DATE across the whole panel, so no ticker's future
can inform another ticker's present.
"""
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/opt/saiful/llm_research/quant_finance/scripts")
from lgbm_baseline import fetch, build_features   # audited machinery

warnings.filterwarnings("ignore")

HORIZON = 20
N_SPLITS = 5
SEED = 42

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO",
    "JPM", "BAC", "WFC", "GS", "V", "MA",
    "JNJ", "UNH", "PFE", "ABBV", "MRK",
    "XOM", "CVX", "COP",
    "WMT", "COST", "KO", "PEP", "PG", "MCD",
    "CAT", "BA", "HON", "GE",
]


def build_panel(tickers, cross):
    """Long panel: one row per (date, ticker) with features + fwd return."""
    frames = []
    ok = 0
    for t in tickers:
        try:
            df = fetch(t)
        except Exception:
            continue
        if len(df) < 800:
            continue
        X = build_features(df, cross)
        X["ticker"] = t
        # forward return over HORIZON days (label built cross-sectionally later)
        X["_fwd"] = df["Close"].shift(-HORIZON) / df["Close"] - 1
        frames.append(X)
        ok += 1
    print(f"  panel built from {ok}/{len(tickers)} tickers")
    panel = pd.concat(frames).rename_axis("date").reset_index()
    return panel


def add_cross_sectional_label(panel):
    """Label = beats the cross-sectional MEDIAN forward return that day.

    Median is computed per-date across tickers -- this uses only same-date
    information, and the resulting label is ~50/50 by construction.
    Dates with fewer than 10 tickers are dropped (unstable median).
    """
    counts = panel.groupby("date")["_fwd"].transform("count")
    panel = panel[counts >= 10].copy()
    med = panel.groupby("date")["_fwd"].transform("median")
    panel["_y"] = (panel["_fwd"] > med).astype(int)
    return panel


def main():
    print("Fetching cross-asset series...")
    cross = {}
    for name, sym in [("spy", "SPY"), ("vix", "^VIX"), ("btc", "BTC-USD")]:
        try:
            cross[name] = fetch(sym)["Close"]
        except Exception:
            print(f"  {name} failed")

    print(f"Building panel over {len(UNIVERSE)} tickers...")
    panel = build_panel(UNIVERSE, cross)
    panel = panel.dropna(subset=["_fwd"])
    panel = add_cross_sectional_label(panel)

    feat_cols = [c for c in panel.columns
                 if c not in ("date", "ticker", "_fwd", "_y")]
    panel = panel.dropna(subset=feat_cols, how="all").sort_values("date")

    dates = np.array(sorted(panel["date"].unique()))
    print(f"  {len(panel):,} rows, {len(dates):,} dates, "
          f"{panel['ticker'].nunique()} tickers")
    print(f"  label balance: {panel['_y'].mean():.4f} "
          f"(0.50 = beta stripped out, as intended)")

    # ---- walk-forward BY DATE across the whole panel ----
    fold = len(dates) // (N_SPLITS + 1)
    rows = []
    for k in range(N_SPLITS):
        tr_end_i = fold * (k + 1)
        te_start_i = tr_end_i + HORIZON          # purge gap, in dates
        te_end_i = min(tr_end_i + fold, len(dates))
        if te_start_i >= te_end_i:
            continue
        tr_dates = set(dates[:tr_end_i])
        te_dates = set(dates[te_start_i:te_end_i])

        tr = panel[panel["date"].isin(tr_dates)]
        te = panel[panel["date"].isin(te_dates)]
        if len(tr) < 500 or len(te) < 200:
            continue

        m = lgb.LGBMClassifier(
            n_estimators=500, learning_rate=0.03, num_leaves=31, max_depth=6,
            min_child_samples=50, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
            random_state=SEED, verbose=-1, n_jobs=4)
        m.fit(tr[feat_cols], tr["_y"])

        p = m.predict_proba(te[feat_cols])[:, 1]
        te = te.assign(_p=p)

        auc = roc_auc_score(te["_y"], p)

        # --- long/short decile spread, computed per date then averaged ---
        spreads, tops, bots = [], [], []
        for d, g in te.groupby("date"):
            if len(g) < 10:
                continue
            g = g.sort_values("_p")
            n_side = max(1, len(g) // 5)          # quintiles
            bot = g.head(n_side)["_fwd"].mean()
            top = g.tail(n_side)["_fwd"].mean()
            spreads.append(top - bot)
            tops.append(top)
            bots.append(bot)

        rows.append({
            "fold": k + 1, "train_rows": len(tr), "test_rows": len(te),
            "auc": auc,
            "spread": np.mean(spreads) if spreads else np.nan,
            "top_q_ret": np.mean(tops) if tops else np.nan,
            "bot_q_ret": np.mean(bots) if bots else np.nan,
            "univ_ret": te["_fwd"].mean(),
            "n_dates": len(spreads),
            "model": m,
        })
        print(f"  fold {k+1}: AUC {auc:.4f}  spread {np.mean(spreads)*100:+.2f}%  "
              f"(top {np.mean(tops)*100:+.2f}% vs bot {np.mean(bots)*100:+.2f}%, "
              f"universe {te['_fwd'].mean()*100:+.2f}%)")

    if not rows:
        print("No folds produced.")
        return

    res = pd.DataFrame([{k: v for k, v in r.items() if k != "model"}
                        for r in rows])
    res.to_csv("/opt/saiful/llm_research/quant_finance/tmp/cross_sectional.csv",
               index=False)

    print("\n" + "=" * 74)
    print(f"CROSS-SECTIONAL RANKING -- {HORIZON}-day horizon")
    print("=" * 74)
    print(res.drop(columns=["train_rows", "test_rows"]).round(4).to_string(index=False))

    auc_m = res["auc"].mean()
    sp_m = res["spread"].mean()
    t_auc, p_auc = stats.ttest_1samp(res["auc"], 0.5)
    t_sp, p_sp = stats.ttest_1samp(res["spread"].dropna(), 0.0)

    print(f"\nMean AUC            : {auc_m:.4f}  (baseline 0.500 BY CONSTRUCTION)")
    print(f"  t vs 0.50         : t={t_auc:.2f}  p={p_auc:.4f}")
    print(f"Mean Q5-Q1 spread   : {sp_m*100:+.2f}% per {HORIZON} trading days")
    print(f"  t vs 0.00         : t={t_sp:.2f}  p={p_sp:.4f}")
    if not np.isnan(sp_m):
        print(f"  annualised (~12.6 periods/yr, GROSS of costs): {sp_m*12.6*100:+.1f}%")
    print(f"Universe mean ret   : {res['univ_ret'].mean()*100:+.2f}% per period")

    print("\nEdge vs the single-ticker setup:")
    print("  single-ticker: AUC 0.5528 but edge -0.045 vs always-up baseline")
    print(f"  cross-sectional: AUC {auc_m:.4f} vs a TRUE 0.500 baseline")
    print("  -> the 0.50 baseline here is real, not an artifact of upward drift")

    print("\nCOSTS NOT INCLUDED: spread, commission, borrow on the short leg,")
    print("and ~2x turnover per period. Subtract realistically before believing.")

    imps = [pd.Series(r["model"].booster_.feature_importance("gain"),
                      index=r["model"].feature_name_) for r in rows]
    agg = pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)
    print("\nTop features (mean gain across folds):")
    for name, val in agg.head(12).items():
        print(f"    {name:24s} {val:12.1f}")


if __name__ == "__main__":
    main()
