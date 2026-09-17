"""
EXPLORATORY -- not pre-registered; written and run after the pre-registered
results were seen.

Follow-up diagnostic on C05's pre-registered net-expectancy-in-R metric,
which the coordinator flagged as possibly ill-conditioned: in
V1_strict_60m the placebo's median net expectancy is -0.587R against a
gross median of only -0.064R, implying an average placebo cost of ~0.52R
per trade versus the recipe's ~0.094R -- a gap that looks like it comes
from the R-denominator (a random entry occasionally draws a tiny 10-bar
swing-stop distance, so `cost_bps / stop_distance_pct` blows up), not from
entry timing. This script re-runs the same 12 cells, same seed (20260917),
same 500-replication placebo, same resolver and cost rules as
`run_c05.py`, and reports the metrics needed to see whether anything
survives once the R-denominator effect is set aside:

  1. gross expectancy in R (no costs)
  2. gross win rate (win = gross return > 0)
  3. net and gross expectancy in PERCENT of entry price (no R-normalisation
     at all -- costs still applied, just not divided by a stop distance)
  4. stop distance as % of entry price: median and 10th percentile,
     recipe vs. (pooled) placebo
  5. average cost in R: recipe vs. placebo median
  6. a second, "distance-matched" placebo arm: identical random-entry
     draws, but a candidate signal is rejected and redrawn if its own stop
     distance (as % of entry) would fall below the RECIPE's own 10th-
     percentile stop distance in that cell/instrument -- i.e. "what does
     random timing look like once the tiny-stop-distance draws that blow
     up the R-denominator are excluded the same way they are naturally
     rare for the recipe." Reports the recipe's percentile against this
     arm for net expectancy in R, net expectancy in %, and win rate.
  7. for the 4 primary (60m) and 4 daily cells only: recipe net/gross %
     expectancy split by side (long/short) and by instrument, with trade
     counts, to check whether any effect concentrates in one instrument or
     one side.

This reuses `run_c05.py`'s bar loading, signal computation, cell/instrument
universe, costs, targets and seed unchanged -- nothing here recomputes the
recipe's signals differently, only reports additional statistics on the
SAME trades and an extended placebo. It does not import, call, or modify
`placebo_swing.py` (the pre-registered placebo module) or touch
`out/results.json` / `out/summary.txt` / `out/win_rate_vs_claim.png`.

Time budget: the distance-matched arm (item 6) costs roughly as much again
as the unfloored placebo per cell/instrument because of its extra retry
loop. If total wall time is projected to exceed ~25 minutes with the
distance-matched arm run on all 12 cells, it is dropped for the 5-minute
cells only (item 6 is diagnostic, not pre-registered, and the
pre-registration itself treats 5-minute results as weak on their own) --
`out/posthoc_diagnostic.txt` states plainly whether this was done.

Entry point: `python posthoc_diagnostic.py` from this file's directory.
Writes `out/posthoc_diagnostic.json` and `out/posthoc_diagnostic.txt`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent.parent
OUT_DIR = CODE_DIR.parent / "out"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE_DIR))

import run_c05 as c05  # noqa: E402
from posthoc_placebo import run_placebo_replications_ext  # noqa: E402
from swing_stop_resolver import run_swing_r_brackets  # noqa: E402

HEADER = "EXPLORATORY -- not pre-registered; written and run after the pre-registered results were seen."

# Drop the distance-matched arm (item 6) for 5-minute cells only if the
# projected total time would exceed this -- decided once, up front, from a
# per-instrument timing probe, not adjusted mid-run.
TIME_BUDGET_S = 25 * 60


def _stop_dist_pct(trades: pd.DataFrame) -> np.ndarray:
    taken = trades[~trades["skipped"]]
    return ((taken["entry_price"] - taken["stop_price"]).abs() / taken["entry_price"]).to_numpy()


def _pct(arr: np.ndarray, q: float) -> float:
    arr = np.asarray(arr, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.percentile(arr, q)) if len(arr) > 0 else float("nan")


def _probe_distance_matched_cost(all_bars) -> tuple[float, float]:
    """Time one unfloored and one distance-matched placebo call on the
    largest series (BTC-USD 5m) at a realistic trade count, to project the
    total run time and decide up front whether item 6 must be dropped for
    5-minute cells to stay inside the time budget. Returns
    (seconds_per_trade_unfloored, seconds_per_trade_distance_matched),
    both measured at the SAME n_trades so the ratio between them is a fair
    estimate of the distance-matched arm's extra retry-loop cost."""
    bars = all_bars["BTC-USD"]["5m"]
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    n_trades_probe = 280

    t0 = time.time()
    run_placebo_replications_ext(
        open_, high, low, close, n_trades=n_trades_probe, n_long=140, target_r=1.5, cost_rate=0.001,
        max_bars=c05.MAX_BARS, lookback=c05.LOOKBACK, n_reps=c05.N_PLACEBO_REPS, seed=1,
        min_stop_dist_pct=None,
    )
    unfloored_s = time.time() - t0

    t0 = time.time()
    run_placebo_replications_ext(
        open_, high, low, close, n_trades=n_trades_probe, n_long=140, target_r=1.5, cost_rate=0.001,
        max_bars=c05.MAX_BARS, lookback=c05.LOOKBACK, n_reps=c05.N_PLACEBO_REPS, seed=1,
        min_stop_dist_pct=0.002,
    )
    matched_s = time.time() - t0

    return unfloored_s / n_trades_probe, matched_s / n_trades_probe


def run_cell_diagnostic(variant: str, reading: str, timeframe: str, all_bars, run_distance_matched: bool) -> dict:
    target_r = c05.TARGET_R[variant]
    per_instrument = {}

    pooled_recipe_net_r = []
    pooled_recipe_gross_r = []
    pooled_recipe_net_pct = []
    pooled_recipe_gross_pct = []
    pooled_recipe_cost_r = []
    pooled_recipe_stop_dist = []

    unfloored_win = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_n = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_sum_net_r = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_sum_gross_r = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_sum_net_pct = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_sum_gross_pct = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_sum_cost_r = np.zeros(c05.N_PLACEBO_REPS)
    unfloored_stop_dist_all: list[np.ndarray] = []

    matched_win = np.zeros(c05.N_PLACEBO_REPS)
    matched_n = np.zeros(c05.N_PLACEBO_REPS)
    matched_sum_net_r = np.zeros(c05.N_PLACEBO_REPS)
    matched_sum_net_pct = np.zeros(c05.N_PLACEBO_REPS)
    matched_floor_exhausted_total = 0

    by_side_instrument = {}

    for ticker in c05.TICKERS:
        bars = all_bars[ticker][timeframe]
        cost_bps = c05.COST_BPS[c05.ASSET_CLASS[ticker]]
        cost_rate = cost_bps / 10_000.0

        signals, _ = c05.compute_signals(bars, variant, reading)
        result = run_swing_r_brackets(
            bars, signals, target_r=target_r, cost_bps=cost_bps, max_bars=c05.MAX_BARS, lookback=c05.LOOKBACK
        )
        taken = result.trades[~result.trades["skipped"]]
        n_taken = len(taken)
        stop_dist = _stop_dist_pct(result.trades)

        pooled_recipe_net_r.append(taken["net_r"].to_numpy())
        pooled_recipe_gross_r.append(taken["gross_r"].to_numpy())
        pooled_recipe_net_pct.append(taken["net_return"].to_numpy())
        pooled_recipe_gross_pct.append(taken["gross_return"].to_numpy())
        pooled_recipe_cost_r.append((taken["gross_r"] - taken["net_r"]).to_numpy())
        pooled_recipe_stop_dist.append(stop_dist)

        by_side_instrument[ticker] = {
            "long": _side_stats(taken[taken["side"] == "long"]),
            "short": _side_stats(taken[taken["side"] == "short"]),
        }

        if n_taken == 0:
            per_instrument[ticker] = {"n_taken": 0}
            continue

        n_long = int((taken["side"] == "long").sum())
        seed = c05.SEED + c05.stable_subseed(variant, reading, timeframe, ticker, "posthoc")

        open_ = bars["open"].to_numpy(dtype=float)
        high = bars["high"].to_numpy(dtype=float)
        low = bars["low"].to_numpy(dtype=float)
        close = bars["close"].to_numpy(dtype=float)

        unfl = run_placebo_replications_ext(
            open_, high, low, close, n_trades=n_taken, n_long=n_long, target_r=target_r,
            cost_rate=cost_rate, max_bars=c05.MAX_BARS, lookback=c05.LOOKBACK,
            n_reps=c05.N_PLACEBO_REPS, seed=seed, min_stop_dist_pct=None,
        )
        unfloored_win += unfl["win_count"]
        unfloored_n += unfl["n_realised"]
        unfloored_sum_net_r += unfl["sum_net_r"]
        unfloored_sum_gross_r += unfl["sum_gross_r"]
        unfloored_sum_net_pct += unfl["sum_net_pct"]
        unfloored_sum_gross_pct += unfl["sum_gross_pct"]
        unfloored_sum_cost_r += unfl["sum_cost_r"]
        unfloored_stop_dist_all.append(unfl["stop_dist_pcts"])

        n_placebo_realised = int(unfl["n_realised"].sum())

        per_instrument[ticker] = {
            "n_taken": n_taken,
            "recipe_stop_dist_pct_p10": _pct(stop_dist, 10),
            "recipe_stop_dist_pct_p50": _pct(stop_dist, 50),
            "placebo_stop_dist_pct_p10": _pct(unfl["stop_dist_pcts"], 10),
            "placebo_stop_dist_pct_p50": _pct(unfl["stop_dist_pcts"], 50),
        }

        if run_distance_matched:
            floor = _pct(stop_dist, 10)
            matched = run_placebo_replications_ext(
                open_, high, low, close, n_trades=n_taken, n_long=n_long, target_r=target_r,
                cost_rate=cost_rate, max_bars=c05.MAX_BARS, lookback=c05.LOOKBACK,
                n_reps=c05.N_PLACEBO_REPS, seed=seed + 1, min_stop_dist_pct=floor,
            )
            matched_win += matched["win_count"]
            matched_n += matched["n_realised"]
            matched_sum_net_r += matched["sum_net_r"]
            matched_sum_net_pct += matched["sum_net_pct"]
            matched_floor_exhausted_total += matched["n_floor_exhausted"]
            per_instrument[ticker]["distance_matched_floor_used"] = floor
            per_instrument[ticker]["distance_matched_n_floor_exhausted"] = matched["n_floor_exhausted"]

    recipe_net_r = np.concatenate(pooled_recipe_net_r) if pooled_recipe_net_r else np.array([])
    recipe_gross_r = np.concatenate(pooled_recipe_gross_r) if pooled_recipe_gross_r else np.array([])
    recipe_net_pct = np.concatenate(pooled_recipe_net_pct) if pooled_recipe_net_pct else np.array([])
    recipe_gross_pct = np.concatenate(pooled_recipe_gross_pct) if pooled_recipe_gross_pct else np.array([])
    recipe_cost_r = np.concatenate(pooled_recipe_cost_r) if pooled_recipe_cost_r else np.array([])
    recipe_stop_dist = np.concatenate(pooled_recipe_stop_dist) if pooled_recipe_stop_dist else np.array([])
    unfloored_stop_dist = (
        np.concatenate(unfloored_stop_dist_all) if unfloored_stop_dist_all else np.array([])
    )

    n = len(recipe_net_r)
    recipe_gross_win_rate = float((recipe_gross_r > 0).mean()) if n > 0 else float("nan")
    recipe_net_win_rate = float((recipe_net_r > 0).mean()) if n > 0 else float("nan")

    valid = unfloored_n > 0
    placebo_gross_r_per_rep = np.divide(unfloored_sum_gross_r, unfloored_n, out=np.full_like(unfloored_sum_gross_r, np.nan), where=valid)
    placebo_net_r_per_rep = np.divide(unfloored_sum_net_r, unfloored_n, out=np.full_like(unfloored_sum_net_r, np.nan), where=valid)
    placebo_gross_pct_per_rep = np.divide(unfloored_sum_gross_pct, unfloored_n, out=np.full_like(unfloored_sum_gross_pct, np.nan), where=valid)
    placebo_net_pct_per_rep = np.divide(unfloored_sum_net_pct, unfloored_n, out=np.full_like(unfloored_sum_net_pct, np.nan), where=valid)
    placebo_win_rate_per_rep = np.divide(unfloored_win, unfloored_n, out=np.full_like(unfloored_win, np.nan), where=valid)
    placebo_cost_r_per_rep = np.divide(unfloored_sum_cost_r, unfloored_n, out=np.full_like(unfloored_sum_cost_r, np.nan), where=valid)

    def pctile_of_actual(actual, dist):
        d = dist[~np.isnan(dist)]
        return float(np.mean(d <= actual)) if len(d) > 0 and not np.isnan(actual) else float("nan")

    result_dict = {
        "n_trades": n,
        "gross_expectancy_r": {
            "recipe": float(np.mean(recipe_gross_r)) if n else float("nan"),
            "placebo_p5": _pct(placebo_gross_r_per_rep, 5),
            "placebo_p50": _pct(placebo_gross_r_per_rep, 50),
            "placebo_p95": _pct(placebo_gross_r_per_rep, 95),
            "recipe_percentile_in_placebo": pctile_of_actual(
                float(np.mean(recipe_gross_r)) if n else float("nan"), placebo_gross_r_per_rep
            ),
        },
        "gross_win_rate": {
            "recipe": recipe_gross_win_rate,
            "placebo_p5": _pct(placebo_win_rate_per_rep, 5),
            "placebo_p50": _pct(placebo_win_rate_per_rep, 50),
            "placebo_p95": _pct(placebo_win_rate_per_rep, 95),
        },
        "net_win_rate": {
            "recipe": recipe_net_win_rate,
        },
        "net_expectancy_pct": {
            "recipe": float(np.mean(recipe_net_pct)) if n else float("nan"),
            "placebo_p5": _pct(placebo_net_pct_per_rep, 5),
            "placebo_p50": _pct(placebo_net_pct_per_rep, 50),
            "placebo_p95": _pct(placebo_net_pct_per_rep, 95),
            "recipe_percentile_in_placebo": pctile_of_actual(
                float(np.mean(recipe_net_pct)) if n else float("nan"), placebo_net_pct_per_rep
            ),
        },
        "gross_expectancy_pct": {
            "recipe": float(np.mean(recipe_gross_pct)) if n else float("nan"),
            "placebo_p5": _pct(placebo_gross_pct_per_rep, 5),
            "placebo_p50": _pct(placebo_gross_pct_per_rep, 50),
            "placebo_p95": _pct(placebo_gross_pct_per_rep, 95),
        },
        "stop_dist_pct": {
            "recipe_p10": _pct(recipe_stop_dist, 10),
            "recipe_p50": _pct(recipe_stop_dist, 50),
            "placebo_p10": _pct(unfloored_stop_dist, 10),
            "placebo_p50": _pct(unfloored_stop_dist, 50),
        },
        "avg_cost_r": {
            "recipe": float(np.mean(recipe_cost_r)) if n else float("nan"),
            "placebo_p50": _pct(placebo_cost_r_per_rep, 50),
        },
        "per_instrument": per_instrument,
        "by_side_instrument": by_side_instrument,
    }

    if run_distance_matched:
        mvalid = matched_n > 0
        matched_net_r_per_rep = np.divide(matched_sum_net_r, matched_n, out=np.full_like(matched_sum_net_r, np.nan), where=mvalid)
        matched_net_pct_per_rep = np.divide(matched_sum_net_pct, matched_n, out=np.full_like(matched_sum_net_pct, np.nan), where=mvalid)
        matched_win_rate_per_rep = np.divide(matched_win, matched_n, out=np.full_like(matched_win, np.nan), where=mvalid)

        actual_net_r = float(np.mean(recipe_net_r)) if n else float("nan")
        actual_net_pct = float(np.mean(recipe_net_pct)) if n else float("nan")
        actual_win_rate = recipe_net_win_rate

        result_dict["distance_matched_placebo"] = {
            "run": True,
            "n_floor_exhausted_total": int(matched_floor_exhausted_total),
            "net_expectancy_r": {
                "placebo_p5": _pct(matched_net_r_per_rep, 5),
                "placebo_p50": _pct(matched_net_r_per_rep, 50),
                "placebo_p95": _pct(matched_net_r_per_rep, 95),
                "recipe_percentile_in_placebo": pctile_of_actual(actual_net_r, matched_net_r_per_rep),
            },
            "net_expectancy_pct": {
                "placebo_p5": _pct(matched_net_pct_per_rep, 5),
                "placebo_p50": _pct(matched_net_pct_per_rep, 50),
                "placebo_p95": _pct(matched_net_pct_per_rep, 95),
                "recipe_percentile_in_placebo": pctile_of_actual(actual_net_pct, matched_net_pct_per_rep),
            },
            "win_rate": {
                "placebo_p5": _pct(matched_win_rate_per_rep, 5),
                "placebo_p50": _pct(matched_win_rate_per_rep, 50),
                "placebo_p95": _pct(matched_win_rate_per_rep, 95),
                "recipe_percentile_in_placebo": pctile_of_actual(actual_win_rate, matched_win_rate_per_rep),
            },
        }
    else:
        result_dict["distance_matched_placebo"] = {"run": False, "reason": "dropped for 5-minute cells to stay within the ~25 minute time budget"}

    return result_dict


def _side_stats(trades: pd.DataFrame) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "net_pct": float("nan"), "gross_pct": float("nan")}
    return {
        "n": n,
        "net_pct": float(trades["net_return"].mean()),
        "gross_pct": float(trades["gross_return"].mean()),
    }


def _known_trade_totals_by_timeframe() -> dict[str, int]:
    """Sum of n_taken across all cells x instruments, by timeframe, read
    from the pre-registered out/results.json (same signals/trade counts as
    this script produces, since nothing about signal generation changed) --
    used only to project total placebo wall time up front, not as a
    reported number of this diagnostic."""
    results_path = OUT_DIR / "results.json"
    with open(results_path) as f:
        pre = json.load(f)
    totals = {"60m": 0, "5m": 0, "daily": 0}
    for cell_key, c in pre["cells"].items():
        tf = cell_key.split("_")[-1]
        for _ticker, v in c["per_instrument"].items():
            totals[tf] += v["n_taken"]
    return totals


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(HEADER)

    print("Loading bars (reusing run_c05.load_all_bars) ...")
    all_bars = c05.load_all_bars()

    s_per_trade_unfloored, s_per_trade_matched = _probe_distance_matched_cost(all_bars)
    trade_totals = _known_trade_totals_by_timeframe()
    total_trades = sum(trade_totals.values())

    projected_unfloored_s = total_trades * s_per_trade_unfloored
    projected_matched_all_s = total_trades * s_per_trade_matched
    projected_total_all_s = projected_unfloored_s + projected_matched_all_s

    drop_distance_matched_for_5m = projected_total_all_s > TIME_BUDGET_S
    if drop_distance_matched_for_5m:
        projected_matched_s = (total_trades - trade_totals["5m"]) * s_per_trade_matched
    else:
        projected_matched_s = projected_matched_all_s
    projected_total_s = projected_unfloored_s + projected_matched_s

    print(
        f"Probe rates: unfloored={s_per_trade_unfloored*1000:.2f}ms/trade, "
        f"distance-matched={s_per_trade_matched*1000:.2f}ms/trade (BTC-USD 5m). "
        f"Known trade totals by timeframe (from the pre-registered run): {trade_totals}. "
        f"Projected total with BOTH arms on all 12 cells: {projected_total_all_s:.0f}s vs budget {TIME_BUDGET_S}s. "
        f"Dropping distance-matched arm for 5m cells: {drop_distance_matched_for_5m} "
        f"(revised projection: {projected_total_s:.0f}s)."
    )

    results = {}
    for variant, reading, timeframe in c05.CELLS:
        cell_key = f"{variant}_{reading}_{timeframe}"
        run_dm = not (drop_distance_matched_for_5m and timeframe == "5m")
        print(f"=== {cell_key} (distance_matched={run_dm}) ===")
        results[cell_key] = run_cell_diagnostic(variant, reading, timeframe, all_bars, run_dm)

    wall_time = time.time() - t0

    out = {
        "note": HEADER,
        "meta": {
            "seed": c05.SEED,
            "n_placebo_reps": c05.N_PLACEBO_REPS,
            "distance_matched_dropped_for_5m": drop_distance_matched_for_5m,
            "wall_time_s": wall_time,
        },
        "cells": results,
    }
    with open(OUT_DIR / "posthoc_diagnostic.json", "w") as f:
        json.dump(out, f, indent=2, default=float)

    write_txt(out, wall_time, drop_distance_matched_for_5m)
    print(f"Done in {wall_time:.1f}s")


def write_txt(out: dict, wall_time: float, dropped_5m: bool) -> None:
    lines = [HEADER, ""]
    lines.append("C05 post-hoc diagnostic: gross/percent views and a distance-matched placebo arm")
    lines.append("=" * 100)
    lines.append(f"Seed: {out['meta']['seed']}  Placebo reps/cell: {out['meta']['n_placebo_reps']}")
    lines.append(f"Distance-matched arm dropped for 5-minute cells: {dropped_5m}")
    lines.append(f"Wall time: {wall_time:.1f}s")
    lines.append("")

    for cell_key, c in out["cells"].items():
        lines.append(f"--- {cell_key} (n={c['n_trades']}) ---")
        ge = c["gross_expectancy_r"]
        lines.append(
            f"  gross_exp_R: recipe={ge['recipe']:.4f}  placebo[p5,p50,p95]="
            f"[{ge['placebo_p5']:.4f},{ge['placebo_p50']:.4f},{ge['placebo_p95']:.4f}]  "
            f"recipe_percentile={ge['recipe_percentile_in_placebo']:.3f}"
        )
        gw = c["gross_win_rate"]
        lines.append(
            f"  gross_win_rate: recipe={gw['recipe']:.4f}  placebo[p5,p50,p95]="
            f"[{gw['placebo_p5']:.4f},{gw['placebo_p50']:.4f},{gw['placebo_p95']:.4f}]"
        )
        lines.append(f"  net_win_rate (recipe, net R>0): {c['net_win_rate']['recipe']:.4f}")
        ne = c["net_expectancy_pct"]
        lines.append(
            f"  net_exp_pct: recipe={ne['recipe']:.6f}  placebo[p5,p50,p95]="
            f"[{ne['placebo_p5']:.6f},{ne['placebo_p50']:.6f},{ne['placebo_p95']:.6f}]  "
            f"recipe_percentile={ne['recipe_percentile_in_placebo']:.3f}"
        )
        gep = c["gross_expectancy_pct"]
        lines.append(
            f"  gross_exp_pct: recipe={gep['recipe']:.6f}  placebo[p5,p50,p95]="
            f"[{gep['placebo_p5']:.6f},{gep['placebo_p50']:.6f},{gep['placebo_p95']:.6f}]"
        )
        sd = c["stop_dist_pct"]
        lines.append(
            f"  stop_dist_pct: recipe[p10,p50]=[{sd['recipe_p10']:.6f},{sd['recipe_p50']:.6f}]  "
            f"placebo[p10,p50]=[{sd['placebo_p10']:.6f},{sd['placebo_p50']:.6f}]"
        )
        ac = c["avg_cost_r"]
        lines.append(f"  avg_cost_R: recipe={ac['recipe']:.4f}  placebo_p50={ac['placebo_p50']:.4f}")

        dm = c["distance_matched_placebo"]
        if dm.get("run"):
            ner = dm["net_expectancy_r"]
            nep = dm["net_expectancy_pct"]
            wr = dm["win_rate"]
            lines.append(
                f"  distance_matched: net_exp_R placebo[p5,p50,p95]="
                f"[{ner['placebo_p5']:.4f},{ner['placebo_p50']:.4f},{ner['placebo_p95']:.4f}] "
                f"recipe_percentile={ner['recipe_percentile_in_placebo']:.3f}"
            )
            lines.append(
                f"                   net_exp_pct placebo[p5,p50,p95]="
                f"[{nep['placebo_p5']:.6f},{nep['placebo_p50']:.6f},{nep['placebo_p95']:.6f}] "
                f"recipe_percentile={nep['recipe_percentile_in_placebo']:.3f}"
            )
            lines.append(
                f"                   win_rate placebo[p5,p50,p95]="
                f"[{wr['placebo_p5']:.4f},{wr['placebo_p50']:.4f},{wr['placebo_p95']:.4f}] "
                f"recipe_percentile={wr['recipe_percentile_in_placebo']:.3f}  "
                f"n_floor_exhausted_total={dm['n_floor_exhausted_total']}"
            )
        else:
            lines.append(f"  distance_matched: NOT RUN ({dm.get('reason')})")

        if cell_key.endswith("_60m") or cell_key.endswith("_daily"):
            lines.append("  by side / instrument (net_pct, gross_pct, n):")
            for ticker, sides in c["by_side_instrument"].items():
                lg = sides["long"]
                sh = sides["short"]
                lines.append(
                    f"    {ticker:8s} long: n={lg['n']:4d} net_pct={lg['net_pct']:.6f} gross_pct={lg['gross_pct']:.6f}  "
                    f"short: n={sh['n']:4d} net_pct={sh['net_pct']:.6f} gross_pct={sh['gross_pct']:.6f}"
                )
        lines.append("")

    (OUT_DIR / "posthoc_diagnostic.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
