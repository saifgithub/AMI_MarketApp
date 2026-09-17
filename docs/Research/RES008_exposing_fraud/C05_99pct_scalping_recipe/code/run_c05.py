"""
C05 "the 99% win rate scalping recipe" -- pre-registered test runner.

Two UT Bot variants (V1: one instance, key 2 / ATR 6, both sides, target
1.5R; V2: two instances, BUY from key 2 / ATR 1 and SELL from key 2 / ATR
300, target 2R), each gated by an STC(length 80, fast 27, slow 50)
confirmation read two ways (R-strict: rising AND below 25 for longs, falling
AND above 75 for shorts; R-loose: rising/falling alone), on three
timeframes (60-minute primary, 5-minute, daily full history) -- 2x2x3 = 12
cells, each pooled across BTC-USD, ETH-USD, SPY, QQQ, AAPL, NVDA, TSLA.

Every trade's stop is the 10-bar swing low/high up to and including its own
signal bar (`swing_stop_resolver.run_swing_r_brackets`, proven to agree
with `common.backtest.run_brackets` in `test_swing_stop_agrees_with_run_brackets.py`),
entry at the next bar's open, one position at a time, costs per
PREREG_COMMON (5 bps/side equities+ETFs, 10 bps/side crypto). Each cell also
runs a 500-replication placebo through the identical resolver
(`placebo_swing.run_placebo_replications`): same per-instrument trade count
and long/short mix, random signal bars, same stop rule, same R target, same
costs.

Entry point: `python run_c05.py` from this file's directory (cwd must be
able to resolve `import common`, i.e. run from the RES008_exposing_fraud
repo root or with it on sys.path -- this file inserts it itself). Writes
`out/results.json`, `out/summary.txt`, `out/win_rate_vs_claim.png`, and
`out/DEVIATIONS.md` if any deviation from the literal pre-registration is
hit at run time.
"""

from __future__ import annotations

import json
import sys
import time
import zlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent.parent
OUT_DIR = CODE_DIR.parent / "out"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE_DIR))

from common.bootstrap import proportion_ci, stationary_block_bootstrap_ci  # noqa: E402
from common.data import load_daily, load_intraday  # noqa: E402

from indicators import stc, ut_bot  # noqa: E402
from placebo_swing import run_placebo_replications  # noqa: E402
from swing_stop_resolver import run_swing_r_brackets  # noqa: E402

SEED = 20260917

TICKERS = ["BTC-USD", "ETH-USD", "SPY", "QQQ", "AAPL", "NVDA", "TSLA"]
ASSET_CLASS = {
    "BTC-USD": "crypto", "ETH-USD": "crypto",
    "SPY": "equity", "QQQ": "equity", "AAPL": "equity", "NVDA": "equity", "TSLA": "equity",
}
COST_BPS = {"equity": 5.0, "crypto": 10.0}

HISTORY_END = "2026-08-31"
DAILY_HISTORY_START = "1990-01-01"  # earlier than any of the 7 instruments' first bar

STC_LENGTH, STC_FAST, STC_SLOW = 80, 27, 50
LOOKBACK = 10
MAX_BARS = 200
N_BOOT = 5000
N_PLACEBO_REPS = 500

TIMEFRAMES = ["60m", "5m", "daily"]
VARIANTS = ["V1", "V2"]
READINGS = ["strict", "loose"]

TARGET_R = {"V1": 1.5, "V2": 2.0}

CELLS = [(v, r, tf) for v in VARIANTS for r in READINGS for tf in TIMEFRAMES]

deviations: list[str] = [
    "STC 'rising'/'falling' operationalised as STC[t] > STC[t-1] / STC[t] < STC[t-1] "
    "(simple one-bar-back comparison) -- the pre-registration describes the direction "
    "qualitatively without a lookback, and a single prior bar is the most literal reading "
    "of a two-point trend description.",
    "Entry filter (STC confirmation) evaluated at the SAME bar as the UT Bot cross, using "
    "that bar's own STC value and its comparison to the prior bar -- both indicators are "
    "read causally at the signal bar's close, matching 'a signal on bar t enters at the "
    "open of t+1'.",
    "Daily timeframe 'full history': loaded from 1990-01-01 (before any of the 7 "
    "instruments' first bar) through the pinned data end 2026-08-31; each instrument "
    "starts at its own first available bar, per PREREG_COMMON.",
    "A bar where a variant's long and short signals fire simultaneously (both filters "
    "true at once) keeps the long signal and drops the short one on that bar, rather than "
    "skipping both or taking both -- occurrences logged per (variant, reading, timeframe, "
    "ticker) below if any occur.",
    "'Run pytest bare' was run scoped to this claim's own directory "
    "(`pytest C05_99pct_scalping_recipe -q`), not repo-root-wide: a bare repo-root `pytest` "
    "fails on collection because C03_tune_until_spectacular/code/test_indicators.py and "
    "this claim's code/test_indicators.py share a basename with no __init__.py in either "
    "code/ dir (pytest cannot disambiguate two same-named modules at repo-root rootdir) -- "
    "a pre-existing repo-wide convention (every prior claim's tests are likewise run scoped "
    "to that claim's own folder, per C03/C04 precedent), not something introduced here, and "
    "not something this claim is allowed to fix by editing another claim's files.",
]


def log_deviation(text: str) -> None:
    deviations.append(text)
    print(f"[DEVIATION] {text}")


def stable_subseed(*parts: str) -> int:
    key = "|".join(parts).encode("utf-8")
    return zlib.crc32(key) % 1_000_000


def load_all_bars() -> dict[str, dict[str, pd.DataFrame]]:
    """bars[ticker][timeframe] -> OHLC DataFrame."""
    bars: dict[str, dict[str, pd.DataFrame]] = {t: {} for t in TICKERS}
    for ticker in TICKERS:
        bars[ticker]["60m"] = load_intraday(ticker, "60m")
        bars[ticker]["5m"] = load_intraday(ticker, "5m")
    daily = load_daily(TICKERS, DAILY_HISTORY_START, HISTORY_END)
    for ticker in TICKERS:
        bars[ticker]["daily"] = daily[ticker]
    return bars


def compute_signals(bars: pd.DataFrame, variant: str, reading: str) -> pd.DataFrame:
    """Returns a DataFrame aligned to `bars.index` with boolean `long`/`short`
    columns: UT Bot cross (variant-specific instance(s)) AND same-bar STC
    confirmation (reading-specific), evaluated causally at each bar's own
    close -- "rising"/"falling" reads as STC[t] compared to STC[t-1], the
    literal reading of a two-point trend description with nothing else
    specified (recorded once in DEVIATIONS.md, not per cell).
    """
    s = stc(bars["close"], length=STC_LENGTH, fast=STC_FAST, slow=STC_SLOW)
    rising = s.diff() > 0
    falling = s.diff() < 0

    if variant == "V1":
        u = ut_bot(bars, key=2.0, atr_period=6)
        buy_cross = u["buy"]
        sell_cross = u["sell"]
    else:
        u_buy = ut_bot(bars, key=2.0, atr_period=1)
        u_sell = ut_bot(bars, key=2.0, atr_period=300)
        buy_cross = u_buy["buy"]
        sell_cross = u_sell["sell"]

    if reading == "strict":
        long_filter = rising & (s < 25.0)
        short_filter = falling & (s > 75.0)
    else:
        long_filter = rising
        short_filter = falling

    long_sig = (buy_cross & long_filter).fillna(False)
    short_sig = (sell_cross & short_filter).fillna(False)

    both = long_sig & short_sig
    n_both = int(both.sum())
    if n_both > 0:
        long_sig = long_sig & ~both
        # both-sides-fired handling: prefer long, deviation logged by caller
        # with full context (ticker/variant/reading/timeframe).

    return pd.DataFrame({"long": long_sig, "short": short_sig}, index=bars.index), n_both


def run_cell(
    variant: str, reading: str, timeframe: str, all_bars: dict[str, dict[str, pd.DataFrame]]
) -> dict:
    target_r = TARGET_R[variant]
    per_instrument = {}
    all_trades = []

    for ticker in TICKERS:
        bars = all_bars[ticker][timeframe]
        cost_bps = COST_BPS[ASSET_CLASS[ticker]]

        signals, n_both = compute_signals(bars, variant, reading)
        if n_both > 0:
            log_deviation(
                f"{variant}/{reading}/{timeframe}/{ticker}: {n_both} bar(s) fired both long "
                "and short signals simultaneously; long kept, short dropped on those bars."
            )

        result = run_swing_r_brackets(
            bars, signals, target_r=target_r, cost_bps=cost_bps, max_bars=MAX_BARS, lookback=LOOKBACK
        )
        trades = result.trades.copy()
        trades["ticker"] = ticker
        trades["asset_class"] = ASSET_CLASS[ticker]
        all_trades.append(trades)

        taken = trades[~trades["skipped"]]
        n_taken = len(taken)
        n_skipped = result.n_skipped

        seed = SEED + stable_subseed(variant, reading, timeframe, ticker)
        n_long = int((taken["side"] == "long").sum())

        open_ = bars["open"].to_numpy(dtype=float)
        high = bars["high"].to_numpy(dtype=float)
        low = bars["low"].to_numpy(dtype=float)
        close = bars["close"].to_numpy(dtype=float)
        placebo = run_placebo_replications(
            open_, high, low, close,
            n_trades=n_taken, n_long=n_long, target_r=target_r,
            cost_rate=cost_bps / 10_000.0, max_bars=MAX_BARS, lookback=LOOKBACK,
            n_reps=N_PLACEBO_REPS, seed=seed,
        )

        per_instrument[ticker] = {
            "n_taken": n_taken,
            "n_skipped": n_skipped,
            "n_long": n_long,
            "n_short": n_taken - n_long,
            "win_rate": float((taken["net_r"] > 0).mean()) if n_taken > 0 else float("nan"),
            "placebo": placebo,
        }

        print(
            f"  {variant} {reading:6s} {timeframe:5s} {ticker:8s} "
            f"n_taken={n_taken:4d} n_skipped={n_skipped:3d} "
            f"win_rate={per_instrument[ticker]['win_rate']:.3f}"
        )

    pooled_trades = pd.concat(all_trades, ignore_index=True)
    taken_pooled = pooled_trades[~pooled_trades["skipped"]].sort_values("signal_date").reset_index(drop=True)

    cell_seed = SEED + stable_subseed(variant, reading, timeframe, "pool")
    summary = summarize_cell(taken_pooled, per_instrument, cell_seed)
    summary["target_r"] = target_r
    return summary


def summarize_cell(taken: pd.DataFrame, per_instrument: dict, seed: int) -> dict:
    n = len(taken)
    net_r = taken["net_r"].to_numpy()
    gross_r = taken["gross_r"].to_numpy()
    net_pct = taken["net_return"].to_numpy()
    gross_pct = taken["gross_return"].to_numpy()
    wins = int((net_r > 0).sum())

    win_rate_ci = proportion_ci(wins, n) if n > 0 else {"estimate": float("nan"), "lower": float("nan"), "upper": float("nan")}
    gross_win_rate = float((gross_r > 0).mean()) if n > 0 else float("nan")

    if n > 0:
        exp_r_net_ci = stationary_block_bootstrap_ci(net_r, stat=np.mean, n_boot=N_BOOT, seed=seed)
        exp_r_gross_ci = stationary_block_bootstrap_ci(gross_r, stat=np.mean, n_boot=N_BOOT, seed=seed)
        exp_pct_net_ci = stationary_block_bootstrap_ci(net_pct, stat=np.mean, n_boot=N_BOOT, seed=seed)
        exp_pct_gross_ci = stationary_block_bootstrap_ci(gross_pct, stat=np.mean, n_boot=N_BOOT, seed=seed)
        exp_r_net_ci.pop("replicates")
        exp_r_gross_ci.pop("replicates")
        exp_pct_net_ci.pop("replicates")
        exp_pct_gross_ci.pop("replicates")
        avg_cost_r = float(np.mean(gross_r - net_r))
    else:
        empty_ci = {"estimate": float("nan"), "lower": float("nan"), "upper": float("nan")}
        exp_r_net_ci = exp_r_gross_ci = exp_pct_net_ci = exp_pct_gross_ci = empty_ci
        avg_cost_r = float("nan")

    exit_reason_counts = taken["exit_reason"].value_counts().to_dict() if n > 0 else {}
    n_skipped_total = sum(v["n_skipped"] for v in per_instrument.values())

    pooled_win_count = np.zeros(N_PLACEBO_REPS, dtype=np.int64)
    pooled_n_realised = np.zeros(N_PLACEBO_REPS, dtype=np.int64)
    pooled_sum_net_r = np.zeros(N_PLACEBO_REPS, dtype=np.float64)
    pooled_sum_gross_r = np.zeros(N_PLACEBO_REPS, dtype=np.float64)
    for v in per_instrument.values():
        p = v["placebo"]
        pooled_win_count = pooled_win_count + p["win_count"]
        pooled_n_realised = pooled_n_realised + p["n_realised"]
        pooled_sum_net_r = pooled_sum_net_r + p["sum_net_r"]
        pooled_sum_gross_r = pooled_sum_gross_r + p["sum_gross_r"]

    valid_reps = pooled_n_realised > 0
    placebo_win_rate = np.full(N_PLACEBO_REPS, np.nan)
    placebo_net_exp_r = np.full(N_PLACEBO_REPS, np.nan)
    placebo_gross_exp_r = np.full(N_PLACEBO_REPS, np.nan)
    placebo_win_rate[valid_reps] = pooled_win_count[valid_reps] / pooled_n_realised[valid_reps]
    placebo_net_exp_r[valid_reps] = pooled_sum_net_r[valid_reps] / pooled_n_realised[valid_reps]
    placebo_gross_exp_r[valid_reps] = pooled_sum_gross_r[valid_reps] / pooled_n_realised[valid_reps]

    placebo_win_rate_valid = placebo_win_rate[valid_reps]
    placebo_net_exp_valid = placebo_net_exp_r[valid_reps]

    actual_win_rate = win_rate_ci["estimate"]
    actual_net_exp_r = exp_r_net_ci["estimate"]

    win_rate_percentile = (
        float(np.mean(placebo_win_rate_valid <= actual_win_rate)) if len(placebo_win_rate_valid) > 0 and n > 0 else float("nan")
    )
    net_exp_percentile = (
        float(np.mean(placebo_net_exp_valid <= actual_net_exp_r)) if len(placebo_net_exp_valid) > 0 and n > 0 else float("nan")
    )

    def _pct(arr, q):
        arr = arr[~np.isnan(arr)]
        return float(np.percentile(arr, q)) if len(arr) > 0 else float("nan")

    return {
        "n_trades": n,
        "n_skipped": n_skipped_total,
        "win_rate": win_rate_ci,
        "gross_win_rate": gross_win_rate,
        "expectancy_r": {"net": exp_r_net_ci, "gross": exp_r_gross_ci},
        "expectancy_pct": {"net": exp_pct_net_ci, "gross": exp_pct_gross_ci},
        "avg_cost_r": avg_cost_r,
        "exit_reason_counts": exit_reason_counts,
        "placebo": {
            "n_reps": N_PLACEBO_REPS,
            "win_rate_p5": _pct(placebo_win_rate, 5),
            "win_rate_p50": _pct(placebo_win_rate, 50),
            "win_rate_p95": _pct(placebo_win_rate, 95),
            "net_expectancy_r_p5": _pct(placebo_net_exp_r, 5),
            "net_expectancy_r_p50": _pct(placebo_net_exp_r, 50),
            "net_expectancy_r_p95": _pct(placebo_net_exp_r, 95),
            "gross_expectancy_r_p50": _pct(placebo_gross_exp_r, 50),
            "actual_win_rate_percentile_in_placebo": win_rate_percentile,
            "actual_net_expectancy_r_percentile_in_placebo": net_exp_percentile,
        },
        "per_instrument": {
            t: {
                "n_taken": v["n_taken"],
                "n_skipped": v["n_skipped"],
                "n_long": v["n_long"],
                "n_short": v["n_short"],
                "win_rate": v["win_rate"],
            }
            for t, v in per_instrument.items()
        },
    }


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {len(TICKERS)} instruments x {len(TIMEFRAMES)} timeframes ...")
    all_bars = load_all_bars()
    for ticker in TICKERS:
        for tf in TIMEFRAMES:
            n_bars = len(all_bars[ticker][tf])
            print(f"  {ticker:8s} {tf:5s} n_bars={n_bars}")
            if tf == "5m" and ticker not in ("BTC-USD", "ETH-USD") and n_bars < 300:
                log_deviation(f"{ticker} 5m: only {n_bars} bars available, thinner than expected.")

    results_by_cell = {}
    for variant, reading, timeframe in CELLS:
        cell_key = f"{variant}_{reading}_{timeframe}"
        print(f"\n=== Cell {cell_key} ===")
        results_by_cell[cell_key] = run_cell(variant, reading, timeframe, all_bars)

    results = {
        "meta": {
            "seed": SEED,
            "history_end": HISTORY_END,
            "tickers": TICKERS,
            "cost_bps": COST_BPS,
            "target_r": TARGET_R,
            "stc_length": STC_LENGTH,
            "stc_fast": STC_FAST,
            "stc_slow": STC_SLOW,
            "lookback": LOOKBACK,
            "max_bars": MAX_BARS,
            "n_boot": N_BOOT,
            "n_placebo_reps": N_PLACEBO_REPS,
        },
        "cells": results_by_cell,
    }

    with open(OUT_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    write_summary_txt(results)
    write_win_rate_vs_claim(results)

    if deviations:
        write_deviations_md()

    wall_time = time.time() - t0
    print(f"\nDone in {wall_time:.1f}s")


def _fmt_ci(ci: dict, digits: int = 4) -> str:
    return f"{ci['estimate']:.{digits}f} [{ci['lower']:.{digits}f}, {ci['upper']:.{digits}f}]"


def write_summary_txt(results: dict) -> None:
    lines = []
    lines.append("C05 -- 'The 99% win rate scalping recipe' -- results summary")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"Seed: {results['meta']['seed']}")
    lines.append(f"Instruments: {', '.join(results['meta']['tickers'])}")
    lines.append(f"Costs (bps/side): {results['meta']['cost_bps']}")
    lines.append(f"Target R: {results['meta']['target_r']}")
    lines.append(
        f"STC length/fast/slow: {results['meta']['stc_length']}/{results['meta']['stc_fast']}/{results['meta']['stc_slow']}"
    )
    lines.append(f"Swing-stop lookback: {results['meta']['lookback']} bars, max hold: {results['meta']['max_bars']} bars")
    lines.append(f"Placebo replications per cell: {results['meta']['n_placebo_reps']}")
    lines.append("")

    header = (
        f"{'cell':22s} {'n':>5s} {'win_rate [95% CI]':>22s} {'placebo 5-95':>16s} "
        f"{'net exp R [95% CI]':>24s} {'placebo p95':>10s} {'gross exp R':>12s} {'cost/trade R':>12s}"
    )
    lines.append(header)
    lines.append("-" * 130)
    for variant, reading, timeframe in CELLS:
        cell_key = f"{variant}_{reading}_{timeframe}"
        c = results["cells"][cell_key]
        wr = c["win_rate"]
        exp_r_net = c["expectancy_r"]["net"]
        exp_r_gross = c["expectancy_r"]["gross"]
        pb = c["placebo"]
        lines.append(
            f"{cell_key:22s} {c['n_trades']:5d} "
            f"{wr['estimate']:.3f} [{wr['lower']:.3f},{wr['upper']:.3f}]  "
            f"{pb['win_rate_p5']:.3f}-{pb['win_rate_p95']:.3f}  "
            f"{exp_r_net['estimate']:7.4f} [{exp_r_net['lower']:7.4f},{exp_r_net['upper']:7.4f}]  "
            f"{pb['net_expectancy_r_p95']:8.4f}  "
            f"{exp_r_gross['estimate']:8.4f}  "
            f"{c['avg_cost_r']:8.4f}"
        )
    lines.append("")

    lines.append("Per-cell detail (skipped trades, exit reasons, per-instrument win rate):")
    lines.append("-" * 100)
    for variant, reading, timeframe in CELLS:
        cell_key = f"{variant}_{reading}_{timeframe}"
        c = results["cells"][cell_key]
        lines.append(f"{cell_key}: n_trades={c['n_trades']} n_skipped={c['n_skipped']}")
        lines.append(f"  gross_win_rate={c['gross_win_rate']:.3f}  exit_reasons={c['exit_reason_counts']}")
        lines.append(
            f"  placebo actual_win_rate_percentile={c['placebo']['actual_win_rate_percentile_in_placebo']:.3f} "
            f"actual_net_expectancy_percentile={c['placebo']['actual_net_expectancy_r_percentile_in_placebo']:.3f}"
        )
        for ticker, v in c["per_instrument"].items():
            lines.append(
                f"    {ticker:8s} n_taken={v['n_taken']:4d} n_skipped={v['n_skipped']:3d} "
                f"long/short={v['n_long']}/{v['n_short']} win_rate={v['win_rate']:.3f}"
            )
        lines.append("")

    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n")


def write_win_rate_vs_claim(results: dict) -> None:
    cell_keys = [f"{v}_{r}_{tf}" for v, r, tf in CELLS]
    win_rates = [results["cells"][k]["win_rate"]["estimate"] for k in cell_keys]
    lo = [results["cells"][k]["win_rate"]["lower"] for k in cell_keys]
    hi = [results["cells"][k]["win_rate"]["upper"] for k in cell_keys]
    placebo_p5 = [results["cells"][k]["placebo"]["win_rate_p5"] for k in cell_keys]
    placebo_p95 = [results["cells"][k]["placebo"]["win_rate_p95"] for k in cell_keys]

    x = np.arange(len(cell_keys))
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.fill_between(x, placebo_p5, placebo_p95, color="#999999", alpha=0.3, label="placebo 5th-95th pct")

    yerr_lo = np.array(win_rates) - np.array(lo)
    yerr_hi = np.array(hi) - np.array(win_rates)
    ax.errorbar(
        x, win_rates, yerr=[yerr_lo, yerr_hi], fmt="o", color="#4C72B0",
        label="recipe win rate [95% CI]", capsize=4,
    )

    ax.axhline(0.80, color="#C44E52", linewidth=1.2, linestyle="--", label="claimed 80%")
    ax.axhline(0.99, color="#8B0000", linewidth=1.2, linestyle="--", label="claimed 99%")
    ax.axhline(1.0 / (1.0 + 1.5), color="#55A868", linewidth=1.0, linestyle=":", label="breakeven @1.5R (40%)")
    ax.axhline(1.0 / (1.0 + 2.0), color="#2E7D32", linewidth=1.0, linestyle=":", label="breakeven @2R (33.3%)")

    ax.set_xticks(x)
    ax.set_xticklabels(cell_keys, rotation=45, ha="right")
    ax.set_ylabel("win rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("C05: the 99% win rate scalping recipe vs. its own placebo")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "win_rate_vs_claim.png", dpi=150)
    plt.close(fig)


def write_deviations_md() -> None:
    lines = ["# C05 DEVIATIONS", "", "Recorded at run time, most literal reading kept in each case.", ""]
    for d in deviations:
        lines.append(f"- {d}")
    (OUT_DIR / "DEVIATIONS.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
