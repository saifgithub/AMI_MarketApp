#!/usr/bin/env python3
"""
Model shootout at the 20-day horizon (the only horizon with a robust signal).

The point is NOT "more models = better". The point is the CONTROLS:

  * LogisticRegression / Ridge  -- if a linear model matches LightGBM, the
    signal is trivially linear and tree sophistication buys nothing.
  * DummyClassifier            -- the always-majority floor.
  * Shuffled-label LightGBM    -- destroys the signal; MUST land at ~0.50.
    If it doesn't, the harness leaks and every other number is void.

Then the actual candidates: LightGBM, XGBoost, CatBoost, RandomForest,
ExtraTrees, plus soft-vote and stacked ensembles.

Reuses the audited feature/label/split machinery from lgbm_baseline.py.
"""
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, accuracy_score

sys.path.insert(0, "/opt/saiful/llm_research/quant_finance/scripts")
from lgbm_baseline import fetch, build_features, make_label  # audited

warnings.filterwarnings("ignore")

HORIZON = 20
N_SPLITS = 5
SEED = 42
TICKERS = ["MSFT", "GOOGL", "AMZN", "META", "TSLA", "WMT", "JNJ", "KO"]


def models():
    """Fresh instances each fold."""
    return {
        "Dummy(majority)": DummyClassifier(strategy="prior"),
        "Logistic(linear)": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(max_iter=2000, C=0.1, random_state=SEED)),
        "LightGBM": lgb.LGBMClassifier(
            n_estimators=400, learning_rate=0.03, num_leaves=15, max_depth=5,
            min_child_samples=40, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
            random_state=SEED, verbose=-1, n_jobs=4),
        "XGBoost": xgb.XGBClassifier(
            n_estimators=400, learning_rate=0.03, max_depth=5,
            min_child_weight=10, subsample=0.8, colsample_bytree=0.7,
            reg_alpha=0.1, reg_lambda=1.0, random_state=SEED,
            n_jobs=4, eval_metric="logloss", verbosity=0),
        "CatBoost": CatBoostClassifier(
            iterations=400, learning_rate=0.03, depth=5, l2_leaf_reg=3.0,
            random_seed=SEED, verbose=0, thread_count=4),
        "RandomForest": RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=20,
            random_state=SEED, n_jobs=4),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=20,
            random_state=SEED, n_jobs=4),
    }


def run_fold(Xtr, ytr, Xte, yte):
    """Returns {model_name: (auc, acc)} plus ensembles built from the same probs."""
    probs, out = {}, {}
    for name, m in models().items():
        Xtr_, Xte_ = Xtr, Xte
        if name in ("RandomForest", "ExtraTrees", "Dummy(majority)"):
            med = Xtr.median()
            Xtr_, Xte_ = Xtr.fillna(med), Xte.fillna(med)
        try:
            m.fit(Xtr_, ytr)
            p = m.predict_proba(Xte_)[:, 1]
        except Exception as e:
            out[name] = (np.nan, np.nan)
            continue
        probs[name] = p
        out[name] = (roc_auc_score(yte, p) if yte.nunique() > 1 else np.nan,
                     accuracy_score(yte, (p > 0.5).astype(int)))

    # --- ensembles over the GBM family (exclude dummy/linear) ---
    gbms = [probs[k] for k in ("LightGBM", "XGBoost", "CatBoost") if k in probs]
    if len(gbms) == 3:
        avg = np.mean(gbms, axis=0)
        out["Ens: 3xGBM avg"] = (roc_auc_score(yte, avg),
                                 accuracy_score(yte, (avg > 0.5).astype(int)))
    allm = [probs[k] for k in
            ("LightGBM", "XGBoost", "CatBoost", "RandomForest", "ExtraTrees")
            if k in probs]
    if len(allm) == 5:
        avg = np.mean(allm, axis=0)
        out["Ens: 5xTree avg"] = (roc_auc_score(yte, avg),
                                  accuracy_score(yte, (avg > 0.5).astype(int)))
    if len(gbms) == 3 and "Logistic(linear)" in probs:
        avg = np.mean(gbms + [probs["Logistic(linear)"]], axis=0)
        out["Ens: GBM+linear"] = (roc_auc_score(yte, avg),
                                  accuracy_score(yte, (avg > 0.5).astype(int)))

    # --- NEGATIVE CONTROL: shuffled labels must collapse to ~0.50 ---
    rng = np.random.default_rng(SEED)
    ysh = pd.Series(rng.permutation(ytr.values), index=ytr.index)
    msh = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15,
                             max_depth=5, min_child_samples=40, subsample=0.8,
                             subsample_freq=1, colsample_bytree=0.7,
                             random_state=SEED, verbose=-1, n_jobs=4)
    msh.fit(Xtr, ysh)
    psh = msh.predict_proba(Xte)[:, 1]
    out["CONTROL: shuffled y"] = (roc_auc_score(yte, psh),
                                  accuracy_score(yte, (psh > 0.5).astype(int)))
    return out


def main():
    print("Fetching cross-asset series...")
    cross = {}
    for name, sym in [("spy", "SPY"), ("vix", "^VIX"), ("btc", "BTC-USD")]:
        try:
            cross[name] = fetch(sym)["Close"]
        except Exception as e:
            print(f"  {name} failed: {e}")

    rows = []
    for t in TICKERS:
        try:
            df = fetch(t)
        except Exception as e:
            print(f"  !! {t} fetch failed")
            continue
        if len(df) < 800:
            continue
        X_all = build_features(df, cross)
        y, fwd = make_label(df, HORIZON)
        d = X_all.copy()
        d["_y"] = y
        d = d.dropna()
        X, yy = d.drop(columns=["_y"]), d["_y"].astype(int)

        n = len(X)
        fold = n // (N_SPLITS + 1)
        for k in range(N_SPLITS):
            tr_end = fold * (k + 1)
            te_start = tr_end + HORIZON            # purge gap
            te_end = min(tr_end + fold, n)
            if te_start >= te_end:
                continue
            Xtr, ytr = X.iloc[:tr_end], yy.iloc[:tr_end]
            Xte, yte = X.iloc[te_start:te_end], yy.iloc[te_start:te_end]
            if ytr.nunique() < 2 or yte.nunique() < 2:
                continue
            for name, (auc, acc) in run_fold(Xtr, ytr, Xte, yte).items():
                rows.append({"ticker": t, "fold": k, "model": name,
                             "auc": auc, "acc": acc})
        print(f"  {t} done")

    res = pd.DataFrame(rows)
    res.to_csv("/opt/saiful/llm_research/quant_finance/tmp/shootout.csv",
               index=False)

    print("\n" + "=" * 78)
    print(f"MODEL SHOOTOUT -- {HORIZON}-day horizon, {len(TICKERS)} tickers, "
          f"{N_SPLITS} walk-forward folds")
    print("=" * 78)

    summ = res.groupby("model").agg(
        auc=("auc", "mean"), auc_sd=("auc", "std"),
        acc=("acc", "mean"), n=("auc", "count")).sort_values("auc",
                                                             ascending=False)

    # paired t-test of each model vs LightGBM on matched ticker/fold cells
    lgbm = res[res.model == "LightGBM"].set_index(["ticker", "fold"])["auc"]
    pvals = {}
    for m in summ.index:
        if m == "LightGBM":
            pvals[m] = np.nan
            continue
        o = res[res.model == m].set_index(["ticker", "fold"])["auc"]
        j = pd.concat([lgbm, o], axis=1, join="inner").dropna()
        if len(j) > 3:
            pvals[m] = stats.ttest_rel(j.iloc[:, 1], j.iloc[:, 0]).pvalue
        else:
            pvals[m] = np.nan
    summ["p_vs_LGBM"] = pd.Series(pvals)

    print(summ.round(4).to_string())

    print("\nInterpretation guide:")
    print("  * CONTROL: shuffled y  -- MUST be ~0.50. If not, the harness leaks.")
    print("  * Logistic(linear)     -- if ~= LightGBM, signal is linear;")
    print("                            tree/ensemble sophistication is wasted.")
    print("  * p_vs_LGBM            -- paired t-test vs LightGBM across cells.")
    print("                            p > 0.05 => not distinguishable.")


if __name__ == "__main__":
    main()
