"""
C04 "a win rate proves the strategy works" -- pre-registered test runner.

Part 1: random-entry, random-side (50/50) bracket trades across U-EQ +
U-CRYPTO + U-FX, seven take-profit:stop geometries in units of each
instrument's own frozen volatility scale s (median ATR(14)/close over
DEFINE), net and gross of PREREG_COMMON costs. Reports, pooled across
instruments per geometry and also split by asset class: win rate (Wilson),
the driftless random-walk reference stop/(target+stop), expectancy per
trade in units of s and in percent with stationary-block-bootstrap 95%
intervals over the pooled trade sequence in time order, and the share of
exits by reason.

Part 2 is analytic (no market data): Wilson 95% intervals for four quoted
(wins, n) pairs, and P(best of k variants shows >= 22/25 | true p) via the
binomial survival function, for k in {1, 5, 20} and p in {0.50, 0.60, 0.70}.

Entry point: `python run_c04.py` from this file's directory. Writes
`out/results.json`, `out/summary.txt`, `out/win_rate_dial.png`, and appends
to `out/DEVIATIONS.md` if a deviation from the literal pre-registration is
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
from scipy import stats

CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent.parent
OUT_DIR = CODE_DIR.parent / "out"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE_DIR))

from common.bootstrap import proportion_ci, stationary_block_bootstrap_ci  # noqa: E402
from common.data import load_daily  # noqa: E402

from brackets_mixed import draw_entry_bars_mixed, run_mixed_brackets  # noqa: E402

SEED = 20260917

DEFINE_START = "2005-01-01"
DEFINE_END = "2018-12-31"
HISTORY_END = "2026-08-31"

U_EQ = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM",
    "PG", "KO", "WMT", "DIS", "INTC", "CSCO", "BA", "GE", "PFE", "T", "SPY", "QQQ",
]
U_CRYPTO = ["BTC-USD", "ETH-USD"]
U_FX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
ALL_TICKERS = U_EQ + U_CRYPTO + U_FX

ASSET_CLASS = {t: "equity" for t in U_EQ}
ASSET_CLASS.update({t: "crypto" for t in U_CRYPTO})
ASSET_CLASS.update({t: "fx" for t in U_FX})

COST_BPS = {"equity": 5.0, "crypto": 10.0, "fx": 2.0}

GEOMETRIES = [
    ("0.5:5", 0.5, 5.0),
    ("1:5", 1.0, 5.0),
    ("1:3", 1.0, 3.0),
    ("1:1", 1.0, 1.0),
    ("2:1", 2.0, 1.0),
    ("3:1", 3.0, 1.0),
    ("5:1", 5.0, 1.0),
]

N_TRADES_PER_CELL = 2000
MAX_BARS = 60
N_BOOT = 5000

EXIT_REASONS = ["take_profit", "stop", "stop_gap", "time_exit"]
EXIT_REASON_LABELS = {"take_profit": "tp", "stop": "stop", "stop_gap": "gap", "time_exit": "time"}


def stable_subseed(*parts: str) -> int:
    """Deterministic per-cell seed offset, independent of PYTHONHASHSEED.

    Python's built-in `hash()` on str/tuple is randomised per process
    unless PYTHONHASHSEED is pinned in the environment, which would silence
    the "fixed seed" requirement across otherwise-identical runs. CRC32 over
    a fixed byte encoding is stable across processes and interpreters.
    """
    key = "|".join(parts).encode("utf-8")
    return zlib.crc32(key) % 1_000_000


deviations: list[str] = []


def log_deviation(text: str) -> None:
    deviations.append(text)
    print(f"[DEVIATION] {text}")


def wilder_atr14(bars: pd.DataFrame) -> pd.Series:
    high = bars["high"]
    low = bars["low"]
    close = bars["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    tr = tr.iloc[1:]
    alpha = 1.0 / 14.0
    atr = tr.ewm(alpha=alpha, adjust=False, min_periods=14).mean()
    return atr


def compute_volatility_scale(ticker: str, full_bars: pd.DataFrame) -> tuple[float, int]:
    define_bars = full_bars.loc[(full_bars.index >= DEFINE_START) & (full_bars.index <= DEFINE_END)]
    if define_bars.empty:
        raise ValueError(f"{ticker}: no bars in DEFINE window at all")
    atr = wilder_atr14(define_bars)
    ratio = (atr / define_bars["close"]).dropna()
    if ratio.empty:
        raise ValueError(f"{ticker}: ATR(14) never warms up inside DEFINE window")
    return float(ratio.median()), len(ratio)


def run_cell(
    ticker: str,
    bars: pd.DataFrame,
    s: float,
    geometry_name: str,
    tp_mult: float,
    sl_mult: float,
    cost_bps: float,
    seed: int,
) -> pd.DataFrame:
    take_profit_pct = tp_mult * s
    stop_loss_pct = sl_mult * s
    n_bars = len(bars)

    rng = np.random.default_rng(seed)
    groups = draw_entry_bars_mixed(
        n_bars=n_bars, n_trades=N_TRADES_PER_CELL, max_bars=MAX_BARS, rng=rng
    )
    n_passes = len(groups)
    if n_passes > 1:
        log_deviation(
            f"{ticker} {geometry_name}: history required {n_passes} resampling passes "
            f"to realise {N_TRADES_PER_CELL} trades (n_bars={n_bars}, max_bars={MAX_BARS})."
        )

    pass_trades = []
    for signal_bars, sides in groups:
        entries = pd.Series(False, index=bars.index)
        entries.iloc[signal_bars] = True
        side_series = pd.Series("long", index=bars.index, dtype=object)
        for sb, sd in zip(signal_bars, sides):
            side_series.iloc[sb] = sd

        result_net = run_mixed_brackets(
            bars, entries, side_series,
            take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct,
            max_bars=MAX_BARS, cost_bps=cost_bps,
        )
        result_gross = run_mixed_brackets(
            bars, entries, side_series,
            take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct,
            max_bars=MAX_BARS, cost_bps=0.0,
        )
        pass_df = result_net.trades.copy()
        pass_df["gross_return"] = result_gross.trades["net_return"].to_numpy()
        pass_trades.append(pass_df)

    trades = pd.concat(pass_trades, ignore_index=True)
    trades["ticker"] = ticker
    trades["asset_class"] = ASSET_CLASS[ticker]
    trades["s"] = s

    realised_n = len(trades)
    if realised_n != N_TRADES_PER_CELL:
        log_deviation(
            f"{ticker} {geometry_name}: realised {realised_n} trades, requested {N_TRADES_PER_CELL}."
        )

    return trades


def summarize_pool(trades: pd.DataFrame, seed: int) -> dict:
    trades_sorted = trades.sort_values("entry_date").reset_index(drop=True)
    n = len(trades_sorted)
    net = trades_sorted["net_return"].to_numpy()
    gross = trades_sorted["gross_return"].to_numpy()
    s_arr = trades_sorted["s"].to_numpy()
    wins = int((net > 0).sum())

    win_rate_ci = proportion_ci(wins, n)

    net_pct_ci = stationary_block_bootstrap_ci(net, stat=np.mean, n_boot=N_BOOT, seed=seed)
    gross_pct_ci = stationary_block_bootstrap_ci(gross, stat=np.mean, n_boot=N_BOOT, seed=seed)
    net_pct_ci.pop("replicates")
    gross_pct_ci.pop("replicates")

    net_units_s = net / s_arr
    gross_units_s = gross / s_arr
    net_units_ci = stationary_block_bootstrap_ci(net_units_s, stat=np.mean, n_boot=N_BOOT, seed=seed)
    gross_units_ci = stationary_block_bootstrap_ci(gross_units_s, stat=np.mean, n_boot=N_BOOT, seed=seed)
    net_units_ci.pop("replicates")
    gross_units_ci.pop("replicates")

    exit_counts = trades_sorted["exit_reason"].value_counts()
    exit_share = {EXIT_REASON_LABELS[r]: float(exit_counts.get(r, 0) / n) for r in EXIT_REASONS}

    return {
        "n_trades": n,
        "win_rate": win_rate_ci,
        "expectancy_pct": {"net": net_pct_ci, "gross": gross_pct_ci},
        "expectancy_units_s": {"net": net_units_ci, "gross": gross_units_ci},
        "exit_share": exit_share,
    }


def wilson_table() -> dict:
    pairs = [(2, 2), (9, 12), (22, 25), (31, 47)]
    out = {}
    for wins, n in pairs:
        out[f"{wins}/{n}"] = proportion_ci(wins, n)
    return out


def best_of_k_prob(k: int, p: float, n: int = 25, threshold: int = 22) -> float:
    p_single = float(stats.binom.sf(threshold - 1, n, p))
    return float(1.0 - (1.0 - p_single) ** k)


def part2_analytic() -> dict:
    wilson = wilson_table()
    ks = [1, 5, 20]
    ps = [0.50, 0.60, 0.70]
    best_of_k = {}
    for k in ks:
        best_of_k[str(k)] = {}
        for p in ps:
            best_of_k[str(k)][str(p)] = best_of_k_prob(k, p)
    return {"wilson_intervals": wilson, "p_best_of_k_reaches_22_of_25": best_of_k}


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {len(ALL_TICKERS)} instruments {DEFINE_START} -> {HISTORY_END} ...")
    raw = load_daily(ALL_TICKERS, DEFINE_START, HISTORY_END)

    scales = {}
    for ticker in ALL_TICKERS:
        bars = raw[ticker]
        s, n_atr_obs = compute_volatility_scale(ticker, bars)
        scales[ticker] = {"s": s, "n_define_atr_obs": n_atr_obs}
        if ticker == "ETH-USD":
            log_deviation(
                f"ETH-USD: DEFINE window (2005-01-01..2018-12-31) contains only "
                f"{n_atr_obs} ATR(14) observations (ETH-USD starts 2017-11-09); "
                f"s computed from what exists in DEFINE, s={s:.6f}, per PREREGISTRATION.md."
            )
        print(f"  s[{ticker}] = {s:.6f} (n_define_atr_obs={n_atr_obs})")

    all_trades = {name: [] for name, _, _ in GEOMETRIES}

    for ticker in ALL_TICKERS:
        bars = raw[ticker]
        s = scales[ticker]["s"]
        cost_bps = COST_BPS[ASSET_CLASS[ticker]]
        for gi, (geometry_name, tp_mult, sl_mult) in enumerate(GEOMETRIES):
            seed = SEED + stable_subseed(ticker, geometry_name)
            trades = run_cell(ticker, bars, s, geometry_name, tp_mult, sl_mult, cost_bps, seed)
            all_trades[geometry_name].append(trades)
            print(
                f"  {ticker:10s} {geometry_name:6s} n={len(trades):5d} "
                f"win_rate={float((trades['net_return'] > 0).mean()):.3f}"
            )

    pooled_by_geometry = {}
    by_class_by_geometry = {}
    for geometry_name, tp_mult, sl_mult in GEOMETRIES:
        pooled = pd.concat(all_trades[geometry_name], ignore_index=True)
        seed = SEED + stable_subseed("pool", geometry_name)
        summary = summarize_pool(pooled, seed)
        summary["target_mult"] = tp_mult
        summary["stop_mult"] = sl_mult
        summary["random_walk_reference_win_rate"] = sl_mult / (tp_mult + sl_mult)
        pooled_by_geometry[geometry_name] = summary

        by_class = {}
        for asset_class in ("equity", "crypto", "fx"):
            subset = pooled[pooled["asset_class"] == asset_class]
            if len(subset) == 0:
                continue
            seed_c = SEED + stable_subseed("pool", geometry_name, asset_class)
            by_class[asset_class] = summarize_pool(subset, seed_c)
        by_class_by_geometry[geometry_name] = by_class

    part2 = part2_analytic()

    results = {
        "meta": {
            "seed": SEED,
            "define_start": DEFINE_START,
            "define_end": DEFINE_END,
            "history_end": HISTORY_END,
            "n_trades_per_cell_requested": N_TRADES_PER_CELL,
            "max_bars": MAX_BARS,
            "n_boot": N_BOOT,
            "cost_bps": COST_BPS,
            "geometries": [{"name": n, "target_mult": t, "stop_mult": s} for n, t, s in GEOMETRIES],
            "universe": {"U-EQ": U_EQ, "U-CRYPTO": U_CRYPTO, "U-FX": U_FX},
        },
        "volatility_scale_s": scales,
        "part1_pooled_by_geometry": pooled_by_geometry,
        "part1_by_asset_class_by_geometry": by_class_by_geometry,
        "part2_analytic": part2,
    }

    with open(OUT_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    write_summary_txt(results)
    write_win_rate_dial(results)

    if deviations:
        write_deviations_md()

    wall_time = time.time() - t0
    print(f"\nDone in {wall_time:.1f}s")


def _fmt_ci(ci: dict, digits: int = 4) -> str:
    return f"{ci['estimate']:.{digits}f} [{ci['lower']:.{digits}f}, {ci['upper']:.{digits}f}]"


def write_summary_txt(results: dict) -> None:
    lines = []
    lines.append("C04 -- 'A win rate proves the strategy works' -- results summary")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Seed: {results['meta']['seed']}")
    lines.append(f"DEFINE window: {DEFINE_START} -> {DEFINE_END} (volatility scale s frozen here)")
    lines.append(f"Full history: {DEFINE_START} -> {HISTORY_END}")
    lines.append(f"Requested trades per instrument per geometry: {N_TRADES_PER_CELL}")
    lines.append(f"Max holding period: {MAX_BARS} bars, time exit at close after that")
    lines.append("")
    lines.append("Volatility scale s (median ATR(14)/close over DEFINE):")
    for ticker, info in results["volatility_scale_s"].items():
        lines.append(f"  {ticker:10s} s={info['s']:.6f}  (n_define_atr_obs={info['n_define_atr_obs']})")
    lines.append("")

    lines.append("PART 1 -- pooled across all 27 instruments, per geometry")
    lines.append("-" * 72)
    header = (
        f"{'geom':6s} {'n':>6s} {'win_rate':>18s} {'rw_ref':>8s} "
        f"{'exp_pct_net':>22s} {'exp_units_s_net':>22s} {'tp/stop/gap/time':>20s}"
    )
    lines.append(header)
    for geometry_name, _, _ in GEOMETRIES:
        g = results["part1_pooled_by_geometry"][geometry_name]
        wr = g["win_rate"]
        exp_pct = g["expectancy_pct"]["net"]
        exp_units = g["expectancy_units_s"]["net"]
        share = g["exit_share"]
        lines.append(
            f"{geometry_name:6s} {g['n_trades']:6d} "
            f"{wr['estimate']:.3f} [{wr['lower']:.3f},{wr['upper']:.3f}] "
            f"{g['random_walk_reference_win_rate']:8.3f} "
            f"{_fmt_ci(exp_pct, 5):>22s} {_fmt_ci(exp_units, 4):>22s} "
            f"{share['tp']:.2f}/{share['stop']:.2f}/{share['gap']:.2f}/{share['time']:.2f}"
        )
    lines.append("")
    lines.append("(gross expectancy, net/gross by asset class, and full CIs are in results.json)")
    lines.append("")

    lines.append("PART 1 -- split by asset class")
    lines.append("-" * 72)
    for geometry_name, _, _ in GEOMETRIES:
        lines.append(f"Geometry {geometry_name}:")
        by_class = results["part1_by_asset_class_by_geometry"][geometry_name]
        for asset_class, g in by_class.items():
            wr = g["win_rate"]
            exp_pct = g["expectancy_pct"]["net"]
            lines.append(
                f"  {asset_class:8s} n={g['n_trades']:5d} "
                f"win_rate={wr['estimate']:.3f} [{wr['lower']:.3f},{wr['upper']:.3f}] "
                f"exp_pct_net={_fmt_ci(exp_pct, 5)}"
            )
    lines.append("")

    lines.append("PART 2 -- analytic, no data")
    lines.append("-" * 72)
    lines.append("Wilson 95% intervals:")
    for label, ci in results["part2_analytic"]["wilson_intervals"].items():
        lines.append(f"  {label:8s} p_hat={ci['estimate']:.4f}  [{ci['lower']:.4f}, {ci['upper']:.4f}]")
    lines.append("")
    lines.append("P(best of k variants shows >= 22/25 | true p):")
    best_of_k = results["part2_analytic"]["p_best_of_k_reaches_22_of_25"]
    lines.append(f"  {'k':>4s} " + " ".join(f"p={p:>4s}" for p in ["0.5", "0.6", "0.7"]))
    for k in ["1", "5", "20"]:
        row = best_of_k[k]
        lines.append(
            f"  {k:>4s} " + " ".join(f"{row[p]:.4f}" for p in ["0.5", "0.6", "0.7"])
        )
    lines.append("")

    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n")


def write_win_rate_dial(results: dict) -> None:
    names = [g for g, _, _ in GEOMETRIES]
    win_rates = [results["part1_pooled_by_geometry"][n]["win_rate"]["estimate"] for n in names]
    exp_units = [results["part1_pooled_by_geometry"][n]["expectancy_units_s"]["net"]["estimate"] for n in names]
    exp_lo = [results["part1_pooled_by_geometry"][n]["expectancy_units_s"]["net"]["lower"] for n in names]
    exp_hi = [results["part1_pooled_by_geometry"][n]["expectancy_units_s"]["net"]["upper"] for n in names]

    fig, ax1 = plt.subplots(figsize=(9, 5))
    x = np.arange(len(names))

    ax1.bar(x, win_rates, color="#4C72B0", alpha=0.7, label="win rate")
    ax1.set_ylabel("win rate")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names)
    ax1.set_ylim(0, 1)
    ax1.set_xlabel("geometry (target:stop, units of s)")
    ax1.axhline(0.5, color="gray", linewidth=0.8, linestyle=":")

    ax2 = ax1.twinx()
    yerr_lo = np.array(exp_units) - np.array(exp_lo)
    yerr_hi = np.array(exp_hi) - np.array(exp_units)
    ax2.errorbar(
        x, exp_units, yerr=[yerr_lo, yerr_hi], fmt="o", color="#C44E52",
        label="net expectancy (units of s)", capsize=4,
    )
    ax2.axhline(0.0, color="#C44E52", linewidth=0.8, linestyle="--")
    ax2.set_ylabel("net expectancy per trade (units of s)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    ax1.set_title("C04: win rate is a dial, not evidence of edge\n(random entries, random side, pooled across 27 instruments)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "win_rate_dial.png", dpi=150)
    plt.close(fig)


def write_deviations_md() -> None:
    lines = ["# C04 DEVIATIONS", "", "Recorded at run time, most literal reading kept in each case.", ""]
    for d in deviations:
        lines.append(f"- {d}")
    (OUT_DIR / "DEVIATIONS.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
