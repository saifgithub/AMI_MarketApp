#!/usr/bin/env python3
"""RES006 — effort-without-result, and whether filtering bad trades beats trading less.

Method fixed in PREREGISTRATION.md, committed before this file ran.

  H1  down days with heavy volume and no price progression, vs other down days
  H2  a volume-participation filter vs a random skip of matched frequency
  H3  stop-after-k-losses vs a random skip of matched frequency  (predicted null)

NOT a test of order flow — daily bars, three orders of magnitude coarser. See the
pre-registration. Research code; imports nothing from `backend/app/`.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
DEF_START, DEF_END = "2005-01-03", "2018-12-31"
HOLD_START, HOLD_END = "2019-01-01", "2026-08-28"
MEDWIN, HORIZONS, N_BOOT, SEED = 60, (1, 3, 5), 10_000, 20260831


def load() -> pd.DataFrame:
    cache = os.path.join(OUT, "spy_ohlcv.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    d = yf.download("SPY", start=DEF_START, end="2026-08-29",
                    progress=False, auto_adjust=True)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    d.columns = ["open", "high", "low", "close", "volume"]
    os.makedirs(OUT, exist_ok=True)
    d.to_csv(cache)
    return d


def features(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["ret"] = d["close"].pct_change()
    # Trailing medians only -> every feature is causal at t.
    d["effort"] = d["volume"] / d["volume"].rolling(MEDWIN).median()
    d["result"] = d["ret"].abs() / d["ret"].abs().rolling(MEDWIN).median()
    d["absorption"] = d["effort"] / d["result"].replace(0, np.nan)
    d["vol_floor_ok"] = d["volume"] >= d["volume"].rolling(MEDWIN).median()
    for h in HORIZONS:
        d[f"fret_{h}"] = d["close"].shift(-h) / d["close"] - 1.0
    return d


def sb_idx(n, block, rng):
    p, idx = 1.0 / max(block, 1.0), np.empty(n, dtype=np.int64)
    i = rng.integers(0, n)
    for k in range(n):
        idx[k] = i
        i = rng.integers(0, n) if rng.random() < p else (i + 1) % n
    return idx


def boot_ci(fn, arrays, block, rng):
    n = len(arrays[0])
    s = np.empty(N_BOOT)
    for b in range(N_BOOT):
        j = sb_idx(n, block, rng)
        s[b] = fn(*[a[j] for a in arrays])
    s = s[np.isfinite(s)]
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def run_h1(d, label, rng):
    res = {}
    for h in HORIZONS:
        sub = d.dropna(subset=["absorption", f"fret_{h}"]).copy()
        down = sub["ret"] < 0
        thr = sub.loc[down, "absorption"].quantile(2 / 3)
        absorb = down & (sub["absorption"] >= thr)
        ctrl = down & ~absorb
        a = sub.loc[absorb, f"fret_{h}"].to_numpy()
        c = sub.loc[ctrl, f"fret_{h}"].to_numpy()
        mark = np.concatenate([np.ones(len(a)), np.zeros(len(c))])
        vals = np.concatenate([a, c])

        def diff(m, v):
            x, y = v[m == 1], v[m == 0]
            return x.mean() - y.mean() if len(x) and len(y) else np.nan

        lo, hi = boot_ci(diff, [mark, vals], 2 * h, rng)
        res[h] = {"n_absorb": int(len(a)), "n_ctrl": int(len(c)),
                  "mean_absorb": float(a.mean()), "mean_ctrl": float(c.mean()),
                  "diff": float(a.mean() - c.mean()), "ci": [lo, hi],
                  "excludes_zero": bool(lo > 0 or hi < 0)}
        r = res[h]
        flag = "  <-- excludes 0" if r["excludes_zero"] else ""
        print(f"  [{label} h={h}] n={r['n_absorb']:4d} absorb={r['mean_absorb']*100:+.3f}% "
              f"ctrl={r['mean_ctrl']*100:+.3f}% diff={r['diff']*100:+.3f}% "
              f"CI={lo*100:+.3f}..{hi*100:+.3f}%{flag}")
    return res


def run_filters(d, label, rng):
    """H2 and H3 on non-overlapping sequential trades."""
    res = {}
    for h in HORIZONS:
        sub = d.dropna(subset=[f"fret_{h}", "vol_floor_ok"]).iloc[::h].copy()
        pnl = sub[f"fret_{h}"].to_numpy()
        floor_ok = sub["vol_floor_ok"].to_numpy().astype(bool)
        n = len(pnl)

        # H3: skip the trade after k consecutive losers (causal - uses only past outcomes)
        h3 = {}
        for k in (2, 3):
            keep = np.ones(n, dtype=bool)
            streak = 0
            for i in range(n):
                if streak >= k:
                    keep[i] = False
                # streak updates on the realised trade whether or not we took it
                streak = streak + 1 if pnl[i] < 0 else 0
            n_skip = int((~keep).sum())
            placebo = np.ones(n, dtype=bool)
            placebo[rng.choice(n, size=n_skip, replace=False)] = False

            def d_mean(a, b, p):
                x, y = p[a.astype(bool)], p[b.astype(bool)]
                return x.mean() - y.mean() if len(x) and len(y) else np.nan

            lo, hi = boot_ci(d_mean, [keep.astype(float), placebo.astype(float), pnl],
                             2, rng)
            h3[k] = {"n_trades": n, "n_skipped": n_skip,
                     "mean_all": float(pnl.mean()),
                     "mean_rule": float(pnl[keep].mean()),
                     "mean_placebo": float(pnl[placebo].mean()),
                     "rule_minus_placebo": float(pnl[keep].mean() - pnl[placebo].mean()),
                     "ci": [lo, hi],
                     "excludes_zero": bool(lo > 0 or hi < 0)}
            r = h3[k]
            flag = "  <-- excludes 0" if r["excludes_zero"] else ""
            print(f"  [{label} h={h} H3 k={k}] skipped {n_skip}/{n}  "
                  f"rule={r['mean_rule']*100:+.3f}% placebo={r['mean_placebo']*100:+.3f}% "
                  f"diff={r['rule_minus_placebo']*100:+.3f}% "
                  f"CI={lo*100:+.3f}..{hi*100:+.3f}%{flag}")

        # H2: volume participation floor vs matched random skip
        n_skip = int((~floor_ok).sum())
        placebo = np.ones(n, dtype=bool)
        if 0 < n_skip < n:
            placebo[rng.choice(n, size=n_skip, replace=False)] = False

        def d_mean2(a, b, p):
            x, y = p[a.astype(bool)], p[b.astype(bool)]
            return x.mean() - y.mean() if len(x) and len(y) else np.nan

        lo, hi = boot_ci(d_mean2, [floor_ok.astype(float), placebo.astype(float), pnl], 2, rng)
        h2 = {"n_trades": n, "n_skipped": n_skip,
              "mean_all": float(pnl.mean()),
              "mean_rule": float(pnl[floor_ok].mean()),
              "mean_placebo": float(pnl[placebo].mean()),
              "rule_minus_placebo": float(pnl[floor_ok].mean() - pnl[placebo].mean()),
              "ci": [lo, hi], "excludes_zero": bool(lo > 0 or hi < 0)}
        flag = "  <-- excludes 0" if h2["excludes_zero"] else ""
        print(f"  [{label} h={h} H2 vol] skipped {n_skip}/{n}  "
              f"rule={h2['mean_rule']*100:+.3f}% placebo={h2['mean_placebo']*100:+.3f}% "
              f"diff={h2['rule_minus_placebo']*100:+.3f}% "
              f"CI={lo*100:+.3f}..{hi*100:+.3f}%{flag}")
        res[h] = {"H2": h2, "H3": h3}
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    d = features(load())
    dd, dh = d.loc[DEF_START:DEF_END], d.loc[HOLD_START:HOLD_END]
    print(f"rows: total={len(d)} definition={len(dd)} holdout={len(dh)}")

    print("\n--- H1  down-absorption vs other down days ---")
    print(" DEFINITION"); h1d = run_h1(dd, "def", rng)
    print(" HOLDOUT");    h1h = run_h1(dh, "hold", rng)

    print("\n--- H2/H3  filters vs matched random skips ---")
    print(" DEFINITION"); fd = run_filters(dd, "def", rng)
    print(" HOLDOUT");    fh = run_filters(dh, "hold", rng)

    json.dump({"definition": {"H1": h1d, "filters": fd},
               "holdout": {"H1": h1h, "filters": fh},
               "meta": {"seed": SEED, "n_boot": N_BOOT, "rows": len(d)}},
              open(os.path.join(OUT, "results.json"), "w"), indent=2, default=str)
    print(f"\nwrote {os.path.join(OUT, 'results.json')}")


if __name__ == "__main__":
    sys.exit(main())
