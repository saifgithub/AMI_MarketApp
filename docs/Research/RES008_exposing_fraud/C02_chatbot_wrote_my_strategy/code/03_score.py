"""C02 step 3 — score every strategy that passed the look-ahead gate.

For each passing strategy, positions are computed ONCE on the full available history per ticker
(the strategy already passed the truncation test, so a position at bar t computed on the full
series is provably identical to one computed on bars[:t] -- slicing after the fact is equivalent
and far cheaper than re-running signal() per window). Universe: p09 (BTC prompt) runs on U-CRYPTO
at 10 bps; every other strategy runs on U-EQ at 5 bps, all next_open. DEFINE/HOLDOUT windows and
S1/S2 definitions are exactly PREREGISTRATION.md's. The as-shown arm (H3) reruns the single best
DEFINE-window ticker gross, same_close, zero cost -- the "screenshot" arm.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.data import load_daily  # noqa: E402
from common.backtest import run_positions  # noqa: E402
from common.placebo import matched_random_entries, percentile_of  # noqa: E402
from common.bootstrap import paired_diff_ci  # noqa: E402

C02 = Path(__file__).resolve().parents[1]
STRATEGIES = C02 / "out" / "strategies"
GATE_RESULTS = C02 / "out" / "gate_results.json"
DEVIATIONS = C02 / "out" / "DEVIATIONS.md"

U_EQ = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM",
        "PG", "KO", "WMT", "DIS", "INTC", "CSCO", "BA", "GE", "PFE", "T", "SPY", "QQQ"]
U_CRYPTO = ["BTC-USD", "ETH-USD"]

DEFINE_START, DEFINE_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2018-12-31")
HOLDOUT_START, HOLDOUT_END = pd.Timestamp("2019-01-01"), pd.Timestamp("2026-08-31")
DATA_END = "2026-08-31"

N_REPS = 500
PLACEBO_SEED = 20260917
SLOW_THRESHOLD_SECONDS = 20 * 60


def load_signal_fn(py_path: Path):
    namespace = {}
    exec(compile(py_path.read_text(), str(py_path), "exec"), namespace)  # noqa: S102 -- already gated in step 2
    return namespace["signal"]


def deterministic_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return PLACEBO_SEED + int(digest[:8], 16) % 10_000


def slice_window(bars: pd.DataFrame, positions: pd.Series, start: pd.Timestamp, end: pd.Timestamp):
    mask = (bars.index >= start) & (bars.index <= end)
    return bars.loc[mask].copy(), positions.loc[mask].copy()


def score_cell(bars: pd.DataFrame, positions: pd.Series, cost_bps: float, seed: int) -> dict | None:
    if len(bars) < 2:
        return None
    result = run_positions(bars, positions, cost_bps=cost_bps, execution="next_open")
    summary = result.summary()

    bh_positions = pd.Series(1.0, index=bars.index)
    bh_result = run_positions(bars, bh_positions, cost_bps=cost_bps, execution="next_open")
    bh_summary = bh_result.summary()

    cell = {
        "net_total_return": summary["total_return"],
        "gross_total_return": float((1.0 + result.gross_daily_returns).prod() - 1.0),
        "buy_hold_net_total_return": bh_summary["total_return"],
        "n_trades": summary["n_trades"],
        "win_rate": summary["win_rate"],
        "exposure": summary["exposure"],
        "max_drawdown": summary["max_drawdown"],
        "beats_buy_hold_net": summary["total_return"] > bh_summary["total_return"],
        "daily_returns": result.daily_returns.to_numpy().tolist(),
        "buy_hold_daily_returns": bh_result.daily_returns.to_numpy().tolist(),
    }

    if summary["n_trades"] == 0:
        cell["s2_percentile"] = None
        cell["zero_trade"] = True
        return cell

    cell["zero_trade"] = False
    placebo = matched_random_entries(
        bars, result.trades, n_reps=N_REPS, cost_bps=cost_bps, seed=seed, execution="next_open"
    )
    cell["s2_percentile"] = percentile_of(summary["total_return"], placebo["total_returns"]) * 100.0
    return cell


def score_as_shown(bars_by_ticker: dict, positions_by_ticker: dict, cost_bps: float) -> dict:
    best_ticker, best_gross = None, -np.inf
    per_ticker_gross = {}
    for ticker, bars in bars_by_ticker.items():
        pos = positions_by_ticker[ticker]
        define_bars, define_pos = slice_window(bars, pos, DEFINE_START, DEFINE_END)
        if len(define_bars) < 2:
            continue
        result = run_positions(define_bars, define_pos, cost_bps=0.0, execution="same_close")
        gross_total = float((1.0 + result.gross_daily_returns).prod() - 1.0)
        bh = run_positions(define_bars, pd.Series(1.0, index=define_bars.index), cost_bps=0.0, execution="same_close")
        bh_total = float((1.0 + bh.gross_daily_returns).prod() - 1.0)
        per_ticker_gross[ticker] = {"gross_total_return": gross_total, "buy_hold_gross_total_return": bh_total,
                                     "beats_buy_hold": gross_total > bh_total}
        if gross_total > best_gross:
            best_gross = gross_total
            best_ticker = ticker

    if best_ticker is None:
        return {"best_ticker": None}

    return {
        "best_ticker": best_ticker,
        "best_ticker_gross_total_return": per_ticker_gross[best_ticker]["gross_total_return"],
        "best_ticker_buy_hold_gross_total_return": per_ticker_gross[best_ticker]["buy_hold_gross_total_return"],
        "looks_profitable": per_ticker_gross[best_ticker]["gross_total_return"] > 0.0,
        "beats_buy_hold_on_best_ticker": per_ticker_gross[best_ticker]["beats_buy_hold"],
        "n_tickers_beating_buy_hold_define_same_close_gross": sum(
            1 for v in per_ticker_gross.values() if v["beats_buy_hold"]
        ),
        "n_tickers_evaluated": len(per_ticker_gross),
    }


def pooled_stats(cells: dict) -> dict:
    non_zero = {t: c for t, c in cells.items() if not c["zero_trade"]}
    n_total = len(cells)
    n_beats = sum(1 for c in cells.values() if c["beats_buy_hold_net"])
    s1_fraction = n_beats / n_total if n_total else float("nan")

    all_net = np.concatenate([c["daily_returns"] for c in cells.values()]) if cells else np.array([])
    all_bh = np.concatenate([c["buy_hold_daily_returns"] for c in cells.values()]) if cells else np.array([])
    if len(all_net) > 0:
        diff_ci = paired_diff_ci(all_net, all_bh, stat=np.mean, seed=PLACEBO_SEED)
    else:
        diff_ci = {"estimate": float("nan"), "lower": float("nan"), "upper": float("nan")}

    if non_zero:
        mean_s2 = float(np.mean([c["s2_percentile"] for c in non_zero.values()]))
        frac_tickers_ge95 = sum(1 for c in non_zero.values() if c["s2_percentile"] >= 95.0) / len(non_zero)
    else:
        mean_s2 = float("nan")
        frac_tickers_ge95 = float("nan")

    return {
        "n_tickers": n_total,
        "n_tickers_zero_trade": n_total - len(non_zero),
        "n_tickers_beating_buy_hold_net": n_beats,
        "s1_fraction_beating_buy_hold": s1_fraction,
        "pooled_diff_vs_buy_hold_mean_daily_net": diff_ci,
        "s2_mean_placebo_percentile": mean_s2,
        "s2_fraction_tickers_ge_95th_percentile": frac_tickers_ge95,
        "n_trades_median": float(np.median([c["n_trades"] for c in cells.values()])) if cells else float("nan"),
        "exposure_median": float(np.median([c["exposure"] for c in cells.values()])) if cells else float("nan"),
    }


def main():
    t0 = time.time()
    gate = json.loads(GATE_RESULTS.read_text())
    passing = {
        name: e for name, e in gate["strategies"].items()
        if e["status"] in ("passed_first", "repaired")
    }
    print(f"{len(passing)} strategies passed the gate; scoring...", flush=True)

    print("loading U-EQ daily bars...", flush=True)
    eq_bars = load_daily(U_EQ, start="2000-01-01", end=DATA_END)
    print("loading U-CRYPTO daily bars...", flush=True)
    crypto_bars = load_daily(U_CRYPTO, start="2000-01-01", end=DATA_END)

    results = {"strategies": {}, "slow_strategies": []}
    deviations = []

    for name, entry in sorted(passing.items()):
        t_strat = time.time()
        py_path = C02 / entry["strategy_path"]
        signal_fn = load_signal_fn(py_path)

        is_crypto = name.startswith("p09_")
        universe = U_CRYPTO if is_crypto else U_EQ
        bars_pool = crypto_bars if is_crypto else eq_bars
        cost_bps = 10.0 if is_crypto else 5.0

        print(f"scoring {name} ({'U-CRYPTO' if is_crypto else 'U-EQ'}, {cost_bps}bps)...", flush=True)

        positions_by_ticker = {}
        for ticker in universe:
            bars = bars_pool[ticker]
            try:
                pos = signal_fn(bars.copy())
            except Exception as exc:
                deviations.append(f"- `{name}` on `{ticker}`: signal() raised {type(exc).__name__}: {exc} "
                                   f"on full history despite passing the gate on SPY; ticker excluded from this strategy's cells.")
                continue
            if not isinstance(pos, pd.Series):
                deviations.append(f"- `{name}` on `{ticker}`: signal() did not return a Series on this ticker's "
                                   f"history; ticker excluded from this strategy's cells.")
                continue
            pos = pos.reindex(bars.index).fillna(0.0)
            raw_vals = pos.to_numpy(dtype=float)
            out_of_range = raw_vals[~np.isin(np.round(raw_vals), [-1.0, 0.0, 1.0]) | (np.abs(raw_vals) > 1.0001)]
            if len(out_of_range) > 0:
                deviations.append(
                    f"- `{name}` on `{ticker}`: {len(out_of_range)} positions outside "
                    f"{{-1,0,1}} (e.g. {out_of_range[:3].tolist()}), despite passing the gate on SPY; "
                    f"clipped to [-1,1] and rounded to the nearest of {{-1,0,1}}."
                )
            pos = pos.clip(-1, 1).round().astype(float)
            positions_by_ticker[ticker] = pos

        define_cells, holdout_cells = {}, {}
        for ticker, pos in positions_by_ticker.items():
            bars = bars_pool[ticker]
            define_bars, define_pos = slice_window(bars, pos, DEFINE_START, DEFINE_END)
            holdout_bars, holdout_pos = slice_window(bars, pos, HOLDOUT_START, HOLDOUT_END)

            seed_define = deterministic_seed(name, ticker, "DEFINE")
            seed_holdout = deterministic_seed(name, ticker, "HOLDOUT")

            if len(define_bars) >= 2:
                cell = score_cell(define_bars, define_pos, cost_bps, seed_define)
                if cell is not None:
                    define_cells[ticker] = cell
            if len(holdout_bars) >= 2:
                cell = score_cell(holdout_bars, holdout_pos, cost_bps, seed_holdout)
                if cell is not None:
                    holdout_cells[ticker] = cell

        as_shown = score_as_shown(
            {t: bars_pool[t] for t in positions_by_ticker}, positions_by_ticker, cost_bps
        )

        strat_result = {
            "model": entry["model"],
            "universe": "U-CRYPTO" if is_crypto else "U-EQ",
            "cost_bps": cost_bps,
            "DEFINE": {
                "cells": {t: {k: v for k, v in c.items() if k not in ("daily_returns", "buy_hold_daily_returns")}
                          for t, c in define_cells.items()},
                "pooled": pooled_stats(define_cells),
            },
            "HOLDOUT": {
                "cells": {t: {k: v for k, v in c.items() if k not in ("daily_returns", "buy_hold_daily_returns")}
                          for t, c in holdout_cells.items()},
                "pooled": pooled_stats(holdout_cells),
            },
            "as_shown": as_shown,
        }
        results["strategies"][name] = strat_result

        elapsed = time.time() - t_strat
        if elapsed > SLOW_THRESHOLD_SECONDS:
            results["slow_strategies"].append({"name": name, "seconds": round(elapsed, 1)})
            deviations.append(f"- `{name}` took {elapsed:.0f}s (> 20 min threshold); recorded and continued.")
        print(f"  done in {elapsed:.1f}s", flush=True)

    results["wall_time_seconds"] = round(time.time() - t0, 1)
    (C02 / "out" / "results.json").write_text(json.dumps(results, indent=2, default=str))

    if deviations:
        with open(DEVIATIONS, "a") as fh:
            fh.write("\n## 03_score.py\n\n")
            fh.write("\n".join(deviations) + "\n")

    print(f"\nScoring done in {results['wall_time_seconds']}s")


if __name__ == "__main__":
    main()
