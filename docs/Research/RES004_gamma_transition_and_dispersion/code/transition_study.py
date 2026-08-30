#!/usr/bin/env python3
"""RES004 — the gamma-flip transition, and dispersion rotation.

Tests the two Rader Trader claims that RES003's static tercile classifier could not see.
Method fixed in PREREGISTRATION.md, committed before this file ran.

  H1  first close into "negative gamma" after K calm closes predicts downside,
      measured against stressed days that are NOT flips (the level is controlled out)
  H2  dispersion is high vs index vol in calm; correlations dominate in stress

Research code. Imports nothing from `backend/app/`; writes only inside this folder.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]

DEF_START, DEF_END = "2005-01-03", "2018-12-31"
HOLD_START, HOLD_END = "2019-01-01", "2026-08-28"
LOOKBACK, DISP_WIN = 504, 21
KS, HORIZONS = (5, 10, 20), (1, 3, 5)
N_BOOT, SEED = 10_000, 20260830


def load() -> pd.DataFrame:
    cache = os.path.join(OUT, "panel.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    frames = {}
    for t in ["SPY"] + SECTORS:
        d = yf.download(t, start=DEF_START, end="2026-08-29",
                        progress=False, auto_adjust=True)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        frames[t] = d["Close"]
    vix = yf.download("^VIX", start=DEF_START, end="2026-08-29",
                      progress=False, auto_adjust=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    frames["vix"] = vix["Close"]
    df = pd.DataFrame(frames).dropna()
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(cache)
    return df


def features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["vix_pct"] = d["vix"].rolling(LOOKBACK).rank(pct=True).shift(1) * 100
    d["spy_ret"] = d["SPY"].pct_change()
    d["spy_vol"] = d["spy_ret"].rolling(DISP_WIN).std() * np.sqrt(252)

    sec = d[SECTORS].pct_change()
    d["dispersion"] = sec.std(axis=1).rolling(DISP_WIN).mean() * np.sqrt(252)
    d["disp_ratio"] = d["dispersion"] / d["spy_vol"]

    corrs = []
    for i in range(len(sec)):
        if i < DISP_WIN:
            corrs.append(np.nan)
            continue
        w = sec.iloc[i - DISP_WIN + 1: i + 1]
        c = w.corr().to_numpy()
        corrs.append(float(c[np.triu_indices_from(c, k=1)].mean()))
    d["avg_corr"] = corrs

    # "negative gamma" analogue: VIX percentile above its median.
    above = (d["vix_pct"] > 50).astype(float)
    d["above"] = above
    run_below = above.copy() * 0
    n = 0
    vals = []
    for a in above.to_numpy():
        vals.append(n)
        n = 0 if a == 1 else n + 1
    d["calm_run"] = vals          # consecutive closes below the median, as of yesterday

    for h in HORIZONS:
        d[f"fret_{h}"] = d["SPY"].shift(-h) / d["SPY"] - 1.0
    return d


def sb_idx(n, block, rng):
    p, idx = 1.0 / max(block, 1.0), np.empty(n, dtype=np.int64)
    i = rng.integers(0, n)
    for k in range(n):
        idx[k] = i
        i = rng.integers(0, n) if rng.random() < p else (i + 1) % n
    return idx


def boot_ci(fn, arrays, block, rng, n_boot=N_BOOT):
    n = len(arrays[0])
    s = np.empty(n_boot)
    for b in range(n_boot):
        j = sb_idx(n, block, rng)
        s[b] = fn(*[a[j] for a in arrays])
    s = s[np.isfinite(s)]
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def run_h1(d, label, rng):
    res = {}
    for K in KS:
        for h in HORIZONS:
            sub = d.dropna(subset=["vix_pct", f"fret_{h}"]).copy()
            stressed = sub["above"] == 1
            # flip = first close above the median after >= K consecutive closes below
            flip = stressed & (sub["calm_run"] >= K)
            ctrl = stressed & ~flip
            if flip.sum() < 10:
                continue
            f = sub.loc[flip, f"fret_{h}"].to_numpy()
            c = sub.loc[ctrl, f"fret_{h}"].to_numpy()
            mark = np.concatenate([np.ones(len(f)), np.zeros(len(c))])
            vals = np.concatenate([f, c])

            def diff(m, v):
                a, b = v[m == 1], v[m == 0]
                return a.mean() - b.mean() if len(a) and len(b) else np.nan

            lo, hi = boot_ci(diff, [mark, vals], 2 * h, rng)
            res[f"K{K}_h{h}"] = {
                "n_flip": int(len(f)), "n_ctrl": int(len(c)),
                "mean_flip": float(f.mean()), "mean_ctrl": float(c.mean()),
                "diff": float(f.mean() - c.mean()), "ci": [lo, hi],
                "excludes_zero": bool(lo > 0 or hi < 0),
            }
            r = res[f"K{K}_h{h}"]
            flag = "  <-- excludes 0" if r["excludes_zero"] else ""
            print(f"  [{label} K={K:2d} h={h}] n={r['n_flip']:4d} "
                  f"flip={r['mean_flip']*100:+.3f}% ctrl={r['mean_ctrl']*100:+.3f}% "
                  f"diff={r['diff']*100:+.3f}% CI={lo*100:+.3f}..{hi*100:+.3f}%{flag}")
    return res


def run_h2(d, label, rng):
    sub = d.dropna(subset=["vix_pct", "disp_ratio", "avg_corr"]).copy()
    reg = pd.cut(sub["vix_pct"], [-0.01, 33.3, 66.7, 100.01],
                 labels=["calm", "normal", "stressed"])
    calm = (reg == "calm").to_numpy().astype(float)
    stress = (reg == "stressed").to_numpy().astype(float)
    dr = sub["disp_ratio"].to_numpy()
    ac = sub["avg_corr"].to_numpy()

    def ratio(c, s, x, y):
        a, b = x[c.astype(bool)], x[s.astype(bool)]
        return a.mean() / b.mean() if len(a) and len(b) else np.nan

    def corr_diff(c, s, x, y):
        a, b = y[s.astype(bool)], y[c.astype(bool)]
        return a.mean() - b.mean() if len(a) and len(b) else np.nan

    arrays = [calm, stress, dr, ac]
    out = {
        "disp_ratio_calm": float(dr[calm.astype(bool)].mean()),
        "disp_ratio_stressed": float(dr[stress.astype(bool)].mean()),
        "disp_calm_over_stressed": float(dr[calm.astype(bool)].mean()
                                         / dr[stress.astype(bool)].mean()),
        "disp_ci": boot_ci(ratio, arrays, 42, rng),
        "corr_calm": float(ac[calm.astype(bool)].mean()),
        "corr_stressed": float(ac[stress.astype(bool)].mean()),
        "corr_stressed_minus_calm": float(ac[stress.astype(bool)].mean()
                                          - ac[calm.astype(bool)].mean()),
        "corr_ci": boot_ci(corr_diff, arrays, 42, rng),
    }
    print(f"  [{label}] dispersion/indexvol calm={out['disp_ratio_calm']:.3f} "
          f"stressed={out['disp_ratio_stressed']:.3f} "
          f"ratio={out['disp_calm_over_stressed']:.3f} "
          f"CI={out['disp_ci'][0]:.3f}..{out['disp_ci'][1]:.3f}")
    print(f"  [{label}] avg pairwise corr calm={out['corr_calm']:.3f} "
          f"stressed={out['corr_stressed']:.3f} "
          f"diff={out['corr_stressed_minus_calm']:+.3f} "
          f"CI={out['corr_ci'][0]:+.3f}..{out['corr_ci'][1]:+.3f}")
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    d = features(load())
    dd, dh = d.loc[DEF_START:DEF_END], d.loc[HOLD_START:HOLD_END]
    print(f"rows: total={len(d)} definition={len(dd)} holdout={len(dh)}")

    print("\n--- H1  flip vs matched stressed control ---")
    print(" DEFINITION 2005-2018")
    h1d = run_h1(dd, "def", rng)
    print(" HOLDOUT 2019-2026")
    h1h = run_h1(dh, "hold", rng)

    print("\n--- H2  dispersion rotation ---")
    h2d = run_h2(dd, "def", rng)
    h2h = run_h2(dh, "hold", rng)

    json.dump({"definition": {"H1": h1d, "H2": h2d},
               "holdout": {"H1": h1h, "H2": h2h},
               "meta": {"seed": SEED, "n_boot": N_BOOT, "rows": len(d)}},
              open(os.path.join(OUT, "results.json"), "w"), indent=2, default=str)
    print(f"\nwrote {os.path.join(OUT, 'results.json')}")


if __name__ == "__main__":
    sys.exit(main())
