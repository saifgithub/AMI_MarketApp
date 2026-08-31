#!/usr/bin/env python3
"""RES003 — does volatility regime modulate risk but not direction?

Runs the four tests fixed in PREREGISTRATION.md (committed before this file ran):

  A  regime -> forward realised volatility        (expected to pass; calibration check)
  B  regime -> forward direction                  (expected to null; inverted kill)
  C  vol-scaled sizing vs a shuffled-size placebo (the actual claim)
  E  is a +100% contest win evidence of skill?    (selection-bias bound)

Research code. Imports nothing from `backend/app/` and writes nothing outside this folder.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")

DEF_START, DEF_END = "2005-01-03", "2018-12-31"   # definition window
HOLD_START, HOLD_END = "2019-01-01", "2026-08-28"  # holdout
LOOKBACK = 504          # 2y percentile window
GK_WINDOW = 20
HORIZONS = (5, 10, 21)
N_BOOT = 10_000
N_TRADES = 10_000
SIZE_CLIP = (0.5, 1.5)
SEED = 20260830


def load() -> pd.DataFrame:
    cache = os.path.join(OUT, "prices.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    spy = yf.download("SPY", start=DEF_START, end="2026-08-29",
                      progress=False, auto_adjust=True)
    vix = yf.download("^VIX", start=DEF_START, end="2026-08-29",
                      progress=False, auto_adjust=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    df = pd.DataFrame({
        "open": spy["Open"], "high": spy["High"],
        "low": spy["Low"], "close": spy["Close"],
        "vix": vix["Close"],
    }).dropna()
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(cache)
    return df


def features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    # Garman-Klass: uses the whole bar, far more efficient than close-to-close.
    hl = np.log(d["high"] / d["low"]) ** 2
    co = np.log(d["close"] / d["open"]) ** 2
    gk_var = 0.5 * hl - (2 * np.log(2) - 1) * co
    d["gk"] = np.sqrt(gk_var.rolling(GK_WINDOW).mean().clip(lower=0) * 252)

    # Percentile rank within the trailing 504d, computed on t and then lagged one
    # day, so a row's regime uses information through the previous close only.
    d["vix_pct"] = d["vix"].rolling(LOOKBACK).rank(pct=True).shift(1) * 100
    d["gk_pct"] = d["gk"].rolling(LOOKBACK).rank(pct=True).shift(1) * 100
    d["gk_lag"] = d["gk"].shift(1)

    d["logret"] = np.log(d["close"]).diff()
    for h in HORIZONS:
        fwd_var = d["logret"].shift(-1).rolling(h).var()
        d[f"fvol_{h}"] = np.sqrt(fwd_var.shift(-(h - 1)) * 252)
        d[f"fret_{h}"] = np.log(d["close"].shift(-h) / d["close"])
        d[f"fsimple_{h}"] = d["close"].shift(-h) / d["close"] - 1.0
    return d


def regime(pct: pd.Series) -> pd.Series:
    return pd.cut(pct, [-0.01, 33.3, 66.7, 100.01],
                  labels=["calm", "normal", "stressed"])


def stationary_bootstrap_idx(n: int, block: float, rng) -> np.ndarray:
    """Politis-Romano: geometric block lengths, wraps around."""
    p = 1.0 / max(block, 1.0)
    idx = np.empty(n, dtype=np.int64)
    i = rng.integers(0, n)
    for k in range(n):
        idx[k] = i
        if rng.random() < p:
            i = rng.integers(0, n)
        else:
            i = (i + 1) % n
    return idx


def boot_ci(fn, arrays, block, rng, n_boot=N_BOOT, lo=2.5, hi=97.5):
    n = len(arrays[0])
    stats = np.empty(n_boot)
    for b in range(n_boot):
        idx = stationary_bootstrap_idx(n, block, rng)
        stats[b] = fn(*[a[idx] for a in arrays])
    finite = stats[np.isfinite(stats)]
    return float(np.percentile(finite, lo)), float(np.percentile(finite, hi))


def run_ab(d: pd.DataFrame, label: str, rng) -> dict:
    res = {}
    for h in HORIZONS:
        sub = d.dropna(subset=["vix_pct", f"fvol_{h}", f"fret_{h}"]).copy()
        sub["reg"] = regime(sub["vix_pct"])
        calm = (sub["reg"] == "calm").to_numpy()
        stressed = (sub["reg"] == "stressed").to_numpy()
        fvol = sub[f"fvol_{h}"].to_numpy()
        fret = sub[f"fret_{h}"].to_numpy()
        block = 2 * h

        def vol_ratio(c, s, v, r):
            a, b = v[s.astype(bool)], v[c.astype(bool)]
            return np.mean(a) / np.mean(b) if len(a) and len(b) else np.nan

        def ret_diff(c, s, v, r):
            a, b = r[s.astype(bool)], r[c.astype(bool)]
            return np.mean(a) - np.mean(b) if len(a) and len(b) else np.nan

        arrays = [calm.astype(float), stressed.astype(float), fvol, fret]
        res[h] = {
            "n": int(len(sub)),
            "n_calm": int(calm.sum()),
            "n_stressed": int(stressed.sum()),
            "vol_calm": float(fvol[calm].mean()),
            "vol_stressed": float(fvol[stressed].mean()),
            "A_vol_ratio": float(fvol[stressed].mean() / fvol[calm].mean()),
            "A_ci": boot_ci(vol_ratio, arrays, block, rng),
            "ret_calm": float(fret[calm].mean()),
            "ret_stressed": float(fret[stressed].mean()),
            "B_ret_diff": float(fret[stressed].mean() - fret[calm].mean()),
            "B_ci": boot_ci(ret_diff, arrays, block, rng),
        }
        print(f"  [{label} h={h:2d}] A ratio={res[h]['A_vol_ratio']:.3f} "
              f"CI={res[h]['A_ci'][0]:.3f}..{res[h]['A_ci'][1]:.3f} | "
              f"B diff={res[h]['B_ret_diff']*100:+.3f}% "
              f"CI={res[h]['B_ci'][0]*100:+.3f}..{res[h]['B_ci'][1]*100:+.3f}%")
    return res


def run_c(d_def: pd.DataFrame, d: pd.DataFrame, label: str, rng) -> dict:
    target_vol = float(d_def["gk_lag"].median())
    res = {"target_vol": target_vol}
    for h in HORIZONS:
        sub = d.dropna(subset=["gk_lag", f"fsimple_{h}"])
        pool = np.arange(len(sub))
        pick = rng.choice(pool, size=min(N_TRADES, len(pool)), replace=True)
        pick.sort()                     # keep date order for the block bootstrap
        fwd = sub[f"fsimple_{h}"].to_numpy()[pick]
        fvol = sub["gk_lag"].to_numpy()[pick]

        size2 = np.clip(target_vol / fvol, *SIZE_CLIP)
        size3 = rng.permutation(size2)          # placebo: same sizes, no alignment

        pnl1, pnl2, pnl3 = fwd * 1.0, fwd * size2, fwd * size3
        block = 2 * h

        def var_ratio(a, b):
            return np.var(a) / np.var(b)

        res[h] = {
            "var_const": float(np.var(pnl1)),
            "var_scaled": float(np.var(pnl2)),
            "var_shuffled": float(np.var(pnl3)),
            "C_var_ratio_scaled_vs_shuffled": float(np.var(pnl2) / np.var(pnl3)),
            "C_ci": boot_ci(var_ratio, [pnl2, pnl3], block, rng),
            "var_ratio_scaled_vs_const": float(np.var(pnl2) / np.var(pnl1)),
            "p95_loss_const": float(np.percentile(pnl1, 5)),
            "p95_loss_scaled": float(np.percentile(pnl2, 5)),
            "p95_loss_shuffled": float(np.percentile(pnl3, 5)),
            "kurt_const": float(pd.Series(pnl1).kurt()),
            "kurt_scaled": float(pd.Series(pnl2).kurt()),
            "kurt_shuffled": float(pd.Series(pnl3).kurt()),
            "mean_const": float(pnl1.mean()),
            "mean_scaled": float(pnl2.mean()),
            "mean_shuffled": float(pnl3.mean()),
            "mean_scaled_ci": boot_ci(lambda a, b: a.mean(), [pnl2, pnl3], block, rng),
        }
        r = res[h]
        print(f"  [{label} h={h:2d}] C var(scaled)/var(shuffled)="
              f"{r['C_var_ratio_scaled_vs_shuffled']:.3f} "
              f"CI={r['C_ci'][0]:.3f}..{r['C_ci'][1]:.3f} | "
              f"vs const={r['var_ratio_scaled_vs_const']:.3f}")
    return res


def run_e(spy_monthly_vol: float, rng) -> dict:
    """What monthly vol makes a +100% winner the EXPECTED max among N zero-skill traders?"""
    out = {"spy_monthly_vol": spy_monthly_vol, "by_n": {}}
    for N in (50, 100, 300, 500):
        lo, hi = 0.01, 3.0
        for _ in range(60):                      # bisect on v
            v = (lo + hi) / 2
            x = rng.normal(-0.5 * v * v, v, size=(4000, N))
            exp_max = float(np.mean(np.exp(x).max(axis=1) - 1.0))
            if exp_max < 1.0:
                lo = v
            else:
                hi = v
        out["by_n"][N] = {
            "required_monthly_vol": round(v, 4),
            "leverage_vs_spy": round(v / spy_monthly_vol, 2),
        }
        print(f"  [E] N={N:3d}  needs monthly vol {v*100:5.1f}%  "
              f"= {v/spy_monthly_vol:5.2f}x SPY's own {spy_monthly_vol*100:.1f}%")
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    d = features(load())
    d_def = d.loc[DEF_START:DEF_END]
    d_hold = d.loc[HOLD_START:HOLD_END]
    print(f"rows: total={len(d)} definition={len(d_def)} holdout={len(d_hold)}")

    print("\n--- DEFINITION WINDOW 2005-2018 ---")
    ab_def = run_ab(d_def, "def", rng)
    c_def = run_c(d_def, d_def, "def", rng)

    print("\n--- HOLDOUT 2019-2026 (one shot) ---")
    ab_hold = run_ab(d_hold, "hold", rng)
    c_hold = run_c(d_def, d_hold, "hold", rng)

    print("\n--- E: is a +100% month evidence of skill? ---")
    monthly = d["logret"].std() * np.sqrt(21)
    e = run_e(float(monthly), rng)

    results = {
        "meta": {
            "rows": len(d), "seed": SEED, "n_boot": N_BOOT,
            "n_trades": N_TRADES, "size_clip": SIZE_CLIP,
            "definition": [DEF_START, DEF_END], "holdout": [HOLD_START, HOLD_END],
        },
        "definition": {"AB": ab_def, "C": c_def},
        "holdout": {"AB": ab_hold, "C": c_hold},
        "E": e,
    }
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nwrote {os.path.join(OUT, 'results.json')}")


if __name__ == "__main__":
    sys.exit(main())
