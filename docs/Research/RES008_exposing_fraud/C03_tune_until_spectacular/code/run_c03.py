"""
C03 -- "keep tweaking until the backtest is spectacular": Parts 1-3.

Part 1: for each of 23 instruments, run the fixed 420-config SuperTrend(+RSI)
(+ADX) grid over its tuning window and holdout window, pick the tuning-window
winner (max net total return), and measure T1 (holdout percentile among the
420), T2 (Spearman rank correlation tuning vs holdout), T3 (winner's holdout
net return minus buy-and-hold), T4 (shrinkage, per year of window). Pooled:
mean T1 with a bootstrap interval over instruments, count of T3 < 0, median
T2.

Part 2: 420 random long/flat strategies per instrument matched to the grid's
median trade count and exposure on the tuning window; report the best
random's tuning-window return next to the tuned winner's.

Part 3: the BTC tuning-window winner at 10x margin -- as-shown compounding
(no liquidation) vs a liquidation check (a bar whose low is >= 10% below the
prior close, or the entry open on the entry bar, wipes the margin), in both
windows; a 5x/20% line as an extra, unregistered robustness check.

Indicators are computed on each instrument's FULL available history (so the
window's first bars are not artificially flat for lack of warmup) and only
sliced to a window afterward -- see `strategy.compute_target_position` and
the window-slicing here.
"""

from __future__ import annotations

import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from common.backtest import run_positions  # noqa: E402
from common.bootstrap import stationary_block_bootstrap_ci  # noqa: E402
from common.data import load_daily  # noqa: E402

from strategy import build_grid, compute_target_position  # noqa: E402
from random_strategy import generate_random_configs  # noqa: E402

OUT_DIR = CODE_DIR.parent / "out"
DEVIATIONS_PATH = OUT_DIR / "DEVIATIONS.md"

U_EQ = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM",
    "PG", "KO", "WMT", "DIS", "INTC", "CSCO", "BA", "GE", "PFE", "T", "SPY", "QQQ",
]
BTC = "BTC-USD"
ALL_INSTRUMENTS = U_EQ + [BTC]

EQUITY_COST_BPS = 5.0
CRYPTO_COST_BPS = 10.0

DEFINE_START, DEFINE_END = "2005-01-01", "2018-12-31"
HOLDOUT_START, HOLDOUT_END = "2019-01-01", "2026-08-31"
BTC_DEFINE_START, BTC_DEFINE_END = "2014-09-17", "2020-12-31"
BTC_HOLDOUT_START, BTC_HOLDOUT_END = "2021-01-01", "2026-08-31"

DATA_LOAD_START = "2000-01-01"
DATA_LOAD_END = "2026-08-31"

N_RANDOM_CONFIGS = 420
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 0

LEVERAGE_10X_THRESHOLD = 0.10
LEVERAGE_5X_THRESHOLD = 0.20


def fixed_seed_for(*parts: str) -> int:
    """Deterministic seed from a label, independent of PYTHONHASHSEED.

    Python's built-in `hash()` on str/tuple is randomized per-process
    (PYTHONHASHSEED), so it cannot be used as a "fixed seed" -- crc32 over
    the literal bytes is stable across runs and processes.
    """
    return zlib.crc32("|".join(parts).encode("utf-8"))


def cost_bps_for(ticker: str) -> float:
    return CRYPTO_COST_BPS if ticker == BTC else EQUITY_COST_BPS


def windows_for(ticker: str) -> tuple[str, str, str, str]:
    if ticker == BTC:
        return BTC_DEFINE_START, BTC_DEFINE_END, BTC_HOLDOUT_START, BTC_HOLDOUT_END
    return DEFINE_START, DEFINE_END, HOLDOUT_START, HOLDOUT_END


def slice_bars(bars: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    mask = (bars.index >= pd.Timestamp(start)) & (bars.index <= pd.Timestamp(end))
    return bars.loc[mask]


def net_total_return(daily_returns: pd.Series) -> float:
    return float((1.0 + daily_returns).prod() - 1.0)


def buy_hold_return(bars: pd.DataFrame) -> float:
    close = bars["close"]
    return float(close.iloc[-1] / close.iloc[0] - 1.0) if len(close) > 1 else 0.0


def run_grid_for_instrument(
    full_bars: pd.DataFrame,
    ticker: str,
    grid: list,
    tune_start: str,
    tune_end: str,
    hold_start: str,
    hold_end: str,
) -> pd.DataFrame:
    """Return a DataFrame with one row per config: tune_return, holdout_return, tune_trades, tune_exposure."""
    cost_bps = cost_bps_for(ticker)
    rows = []
    for i, config in enumerate(grid):
        target = compute_target_position(full_bars, config)

        tune_bars = slice_bars(full_bars, tune_start, tune_end)
        tune_target = target.reindex(tune_bars.index)
        tune_result = run_positions(tune_bars, tune_target, cost_bps=cost_bps, execution="next_open")

        hold_bars = slice_bars(full_bars, hold_start, hold_end)
        hold_target = target.reindex(hold_bars.index)
        hold_result = run_positions(hold_bars, hold_target, cost_bps=cost_bps, execution="next_open")

        rows.append(
            {
                "config_index": i,
                "config_label": config.label,
                "tune_return": net_total_return(tune_result.daily_returns),
                "holdout_return": net_total_return(hold_result.daily_returns),
                "tune_trades": len(tune_result.trades),
                "tune_exposure": float((tune_result.positions_held != 0).mean()),
                "holdout_trades": len(hold_result.trades),
                "holdout_exposure": float((hold_result.positions_held != 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def compute_t1_t4(grid_df: pd.DataFrame, tune_bars: pd.DataFrame, hold_bars: pd.DataFrame) -> dict:
    winner_idx = grid_df["tune_return"].idxmax()
    winner = grid_df.loc[winner_idx]

    n = len(grid_df)
    t1 = 100.0 * float((grid_df["holdout_return"] <= winner["holdout_return"]).sum()) / n

    if grid_df["tune_return"].nunique() > 1 and grid_df["holdout_return"].nunique() > 1:
        rho, _ = stats.spearmanr(grid_df["tune_return"], grid_df["holdout_return"])
        t2 = float(rho)
    else:
        t2 = float("nan")

    hold_bh = buy_hold_return(hold_bars)
    t3 = float(winner["holdout_return"] - hold_bh)

    tune_years = (tune_bars.index[-1] - tune_bars.index[0]).days / 365.25
    hold_years = (hold_bars.index[-1] - hold_bars.index[0]).days / 365.25
    tune_return_annualized = winner["tune_return"] / tune_years
    holdout_return_annualized = winner["holdout_return"] / hold_years
    t4 = {
        "tune_return_per_year": float(tune_return_annualized),
        "holdout_return_per_year": float(holdout_return_annualized),
        "tune_years": float(tune_years),
        "holdout_years": float(hold_years),
    }

    return {
        "winner_config_index": int(winner["config_index"]),
        "winner_config_label": str(winner["config_label"]),
        "winner_tune_return": float(winner["tune_return"]),
        "winner_holdout_return": float(winner["holdout_return"]),
        "winner_tune_trades": int(winner["tune_trades"]),
        "winner_tune_exposure": float(winner["tune_exposure"]),
        "T1_holdout_percentile": t1,
        "T2_spearman": t2,
        "T3_vs_buy_hold": t3,
        "T4_shrinkage": t4,
        "holdout_buy_hold_return": hold_bh,
    }


def run_part2(
    full_bars: pd.DataFrame, ticker: str, grid_df: pd.DataFrame, tune_start: str, tune_end: str
) -> dict:
    cost_bps = cost_bps_for(ticker)
    tune_bars = slice_bars(full_bars, tune_start, tune_end)

    median_trades = float(grid_df["tune_trades"].median())
    median_exposure = float(grid_df["tune_exposure"].median())

    random_targets = generate_random_configs(
        tune_bars,
        n_configs=N_RANDOM_CONFIGS,
        median_trades=median_trades,
        median_exposure=median_exposure,
        seed=fixed_seed_for("c03_part2", ticker),
    )

    best_random_return = float("-inf")
    for target in random_targets:
        result = run_positions(tune_bars, target, cost_bps=cost_bps, execution="next_open")
        r = net_total_return(result.daily_returns)
        if r > best_random_return:
            best_random_return = r

    winner_idx = grid_df["tune_return"].idxmax()
    winner_tune_return = float(grid_df.loc[winner_idx, "tune_return"])

    return {
        "median_trades_matched": median_trades,
        "median_exposure_matched": median_exposure,
        "best_random_tune_return": best_random_return,
        "tuned_winner_tune_return": winner_tune_return,
    }


def leverage_path(
    bars: pd.DataFrame,
    positions_held: pd.Series,
    daily_returns: pd.Series,
    leverage: float,
    adverse_threshold: float,
) -> dict:
    """As-shown (no-liquidation) vs liquidated equity path for a levered long."""
    idx = bars.index
    close = bars["close"]
    low = bars["low"]
    open_ = bars["open"]
    prev_close = close.shift(1)

    held = positions_held.reindex(idx).fillna(0.0).to_numpy()
    lev_returns = leverage * daily_returns.reindex(idx).fillna(0.0).to_numpy()
    as_shown_equity = np.cumprod(1.0 + lev_returns)

    liquidation_events = []
    n = len(idx)
    prev_pos = 0.0
    for t in range(n):
        pos = held[t]
        if pos > 0:
            if prev_pos <= 0:
                reference = float(open_.iloc[t])
            else:
                reference = float(prev_close.iloc[t]) if not np.isnan(prev_close.iloc[t]) else float(open_.iloc[t])
            bar_low = float(low.iloc[t])
            drawdown = bar_low / reference - 1.0
            if drawdown <= -adverse_threshold:
                liquidation_events.append({"date": str(idx[t].date()), "drawdown_vs_reference": drawdown})
        prev_pos = pos

    liquidated_equity = as_shown_equity.copy()
    if liquidation_events:
        first_date = pd.Timestamp(liquidation_events[0]["date"])
        first_pos = idx.get_loc(first_date)
        liquidated_equity[first_pos:] = 0.0

    return {
        "leverage": leverage,
        "adverse_threshold": adverse_threshold,
        "n_liquidation_events": len(liquidation_events),
        "liquidation_dates": [e["date"] for e in liquidation_events],
        "as_shown_final_equity_multiple": float(as_shown_equity[-1]) if n else 1.0,
        "as_shown_net_return": float(as_shown_equity[-1] - 1.0) if n else 0.0,
        "liquidated_final_equity_multiple": float(liquidated_equity[-1]) if n else 1.0,
        "as_shown_equity_curve": as_shown_equity.tolist(),
        "liquidated_equity_curve": liquidated_equity.tolist(),
        "dates": [str(d.date()) for d in idx],
    }


def run_part3(full_bars: pd.DataFrame, winner_config, tune_start, tune_end, hold_start, hold_end) -> dict:
    cost_bps = cost_bps_for(BTC)
    target = compute_target_position(full_bars, winner_config)

    out = {}
    for window_name, start, end in [("tuning", tune_start, tune_end), ("holdout", hold_start, hold_end)]:
        window_bars = slice_bars(full_bars, start, end)
        window_target = target.reindex(window_bars.index)
        result = run_positions(window_bars, window_target, cost_bps=cost_bps, execution="next_open")

        lev10 = leverage_path(
            window_bars, result.positions_held, result.daily_returns, leverage=10.0, adverse_threshold=LEVERAGE_10X_THRESHOLD
        )
        lev5 = leverage_path(
            window_bars, result.positions_held, result.daily_returns, leverage=5.0, adverse_threshold=LEVERAGE_5X_THRESHOLD
        )
        out[window_name] = {"leverage_10x": lev10, "leverage_5x_extra_not_preregistered": lev5}
    return out


def main() -> None:
    t_start = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grid = build_grid()

    per_instrument = {}
    t1_values = []
    t2_values = []
    t3_values = []

    for ticker in ALL_INSTRUMENTS:
        tune_start, tune_end, hold_start, hold_end = windows_for(ticker)
        load_start = tune_start if ticker == BTC else DATA_LOAD_START
        bars_dict = load_daily([ticker], start=load_start, end=DATA_LOAD_END)
        full_bars = bars_dict[ticker]

        grid_df = run_grid_for_instrument(full_bars, ticker, grid, tune_start, tune_end, hold_start, hold_end)
        grid_csv_path = OUT_DIR / f"grid_returns_{ticker.replace('/', '_')}.csv"
        grid_df.to_csv(grid_csv_path, index=False)

        tune_bars = slice_bars(full_bars, tune_start, tune_end)
        hold_bars = slice_bars(full_bars, hold_start, hold_end)

        t_metrics = compute_t1_t4(grid_df, tune_bars, hold_bars)
        part2 = run_part2(full_bars, ticker, grid_df, tune_start, tune_end)

        per_instrument[ticker] = {
            "tune_window": [tune_start, tune_end],
            "holdout_window": [hold_start, hold_end],
            **t_metrics,
            "part2_random_placebo": part2,
        }

        t1_values.append(t_metrics["T1_holdout_percentile"])
        t2_values.append(t_metrics["T2_spearman"])
        t3_values.append(t_metrics["T3_vs_buy_hold"])

        print(f"{ticker}: T1={t_metrics['T1_holdout_percentile']:.1f} T3={t_metrics['T3_vs_buy_hold']:.4f}", flush=True)

    t1_arr = np.array(t1_values, dtype=float)
    t3_arr = np.array(t3_values, dtype=float)
    t2_arr = np.array([v for v in t2_values if not np.isnan(v)], dtype=float)

    # Part 1 pooled stat is explicitly a SIMPLE IID bootstrap over INSTRUMENTS
    # (not days) per the spec -- block_len=1 degenerates the stationary-
    # bootstrap machinery in common/bootstrap.py to plain iid resampling with
    # replacement, while reusing its fixed-seed percentile-CI implementation.
    t1_ci = stationary_block_bootstrap_ci(
        t1_arr, stat=np.mean, block_len=1, n_boot=BOOTSTRAP_N, seed=BOOTSTRAP_SEED
    )

    pooled = {
        "mean_T1": t1_ci["estimate"],
        "mean_T1_ci_lower": t1_ci["lower"],
        "mean_T1_ci_upper": t1_ci["upper"],
        "n_boot": BOOTSTRAP_N,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "n_instruments_T3_negative": int((t3_arr < 0).sum()),
        "n_instruments": len(ALL_INSTRUMENTS),
        "median_T2": float(np.median(t2_arr)) if len(t2_arr) else float("nan"),
    }

    btc_data = per_instrument[BTC]
    btc_winner_config = None
    for config in grid:
        if config.label == btc_data["winner_config_label"]:
            btc_winner_config = config
            break
    assert btc_winner_config is not None

    btc_tune_start, btc_tune_end, btc_hold_start, btc_hold_end = windows_for(BTC)
    btc_full_bars = load_daily([BTC], start=btc_tune_start, end=DATA_LOAD_END)[BTC]
    part3 = run_part3(btc_full_bars, btc_winner_config, btc_tune_start, btc_tune_end, btc_hold_start, btc_hold_end)

    h1_supported = pooled["mean_T1"] < 65 and pooled["mean_T1_ci_lower"] <= 50 <= pooled["mean_T1_ci_upper"]
    h2_supported = pooled["n_instruments_T3_negative"] > pooled["n_instruments"] / 2
    h3_supported = (
        part3["tuning"]["leverage_10x"]["n_liquidation_events"] >= 1
    )

    claim_condition_1 = (
        pooled["mean_T1"] >= 75
        and not (pooled["mean_T1_ci_lower"] <= 50 <= pooled["mean_T1_ci_upper"])
        and pooled["n_instruments_T3_negative"] < pooled["n_instruments"] / 2
    )
    claim_condition_2 = (
        part3["tuning"]["leverage_10x"]["n_liquidation_events"] == 0
        and part3["holdout"]["leverage_10x"]["n_liquidation_events"] == 0
    )

    results = {
        "grid_size": len(grid),
        "n_instruments": len(ALL_INSTRUMENTS),
        "costs_bps": {"equities": EQUITY_COST_BPS, "crypto": CRYPTO_COST_BPS},
        "per_instrument": per_instrument,
        "pooled": pooled,
        "part3_btc_leverage": part3,
        "part3_btc_winner_config": btc_data["winner_config_label"],
        "hypotheses": {
            "H1_mean_T1_below_65_ci_includes_50": h1_supported,
            "H2_T3_negative_majority": h2_supported,
            "H3_btc_10x_liquidated_in_tuning_window": h3_supported,
        },
        "claim_support": {
            "condition_1_mean_T1_ge_75_ci_excludes_50_and_T3_majority_positive": claim_condition_1,
            "condition_2_10x_never_liquidated_either_window": claim_condition_2,
        },
        "wall_time_seconds": None,
    }

    wall_time = time.time() - t_start
    results["wall_time_seconds"] = wall_time

    with open(OUT_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    write_summary(results)
    make_figures(results, grid)

    print(f"Done in {wall_time:.1f}s", flush=True)


def write_summary(results: dict) -> None:
    pooled = results["pooled"]
    lines = []
    lines.append("C03 -- keep tweaking until the backtest is spectacular")
    lines.append("")
    lines.append(f"Instruments: {results['n_instruments']}  Grid size: {results['grid_size']}")
    lines.append(
        f"Pooled mean T1 (holdout percentile of tuning-window winner): "
        f"{pooled['mean_T1']:.2f}  95% CI [{pooled['mean_T1_ci_lower']:.2f}, {pooled['mean_T1_ci_upper']:.2f}] "
        f"(iid bootstrap over instruments, n_boot={pooled['n_boot']}, seed={pooled['bootstrap_seed']})"
    )
    lines.append(f"Median T2 (Spearman tune vs holdout, across instruments): {pooled['median_T2']:.3f}")
    lines.append(
        f"Instruments with T3 < 0 (winner holdout return below buy-and-hold): "
        f"{pooled['n_instruments_T3_negative']} / {pooled['n_instruments']}"
    )
    lines.append("")
    lines.append("Per-instrument T1 / T3:")
    for ticker, data in results["per_instrument"].items():
        lines.append(
            f"  {ticker:10s} T1={data['T1_holdout_percentile']:6.1f}  T2={data['T2_spearman']:7.3f}  "
            f"T3={data['T3_vs_buy_hold']:9.4f}  winner={data['winner_config_label']}"
        )
    lines.append("")

    lines.append("Part 2 -- tuned winner vs best of 420 random long/flat placebos (tuning window):")
    for ticker, data in results["per_instrument"].items():
        p2 = data["part2_random_placebo"]
        lines.append(
            f"  {ticker:10s} tuned_winner={p2['tuned_winner_tune_return']:9.4f}  "
            f"best_random={p2['best_random_tune_return']:9.4f}"
        )
    lines.append("")

    lines.append(f"Part 3 -- BTC tuned winner ({results['part3_btc_winner_config']}) at leverage:")
    for window_name in ("tuning", "holdout"):
        w = results["part3_btc_leverage"][window_name]
        lev10 = w["leverage_10x"]
        lev5 = w["leverage_5x_extra_not_preregistered"]
        lines.append(f"  {window_name} window:")
        lines.append(
            f"    10x as-shown net return: {lev10['as_shown_net_return']:.4f}  "
            f"liquidation events: {lev10['n_liquidation_events']}  dates: {lev10['liquidation_dates']}"
        )
        lines.append(
            f"    10x liquidated-path final equity multiple: {lev10['liquidated_final_equity_multiple']:.6f}"
        )
        lines.append(
            f"    [extra, not pre-registered] 5x as-shown net return: {lev5['as_shown_net_return']:.4f}  "
            f"liquidation events: {lev5['n_liquidation_events']}  dates: {lev5['liquidation_dates']}"
        )
    lines.append("")

    h = results["hypotheses"]
    lines.append("Hypotheses:")
    lines.append(f"  H1 (mean T1 < 65, CI includes 50): {h['H1_mean_T1_below_65_ci_includes_50']}")
    lines.append(f"  H2 (T3 < 0 for majority of instruments): {h['H2_T3_negative_majority']}")
    lines.append(f"  H3 (BTC 10x liquidated at least once in tuning window): {h['H3_btc_10x_liquidated_in_tuning_window']}")
    lines.append("")
    c = results["claim_support"]
    lines.append("What would support the claim instead:")
    lines.append(f"  mean T1 >= 75 with CI excluding 50 AND T3 > 0 majority: {c['condition_1_mean_T1_ge_75_ci_excludes_50_and_T3_majority_positive']}")
    lines.append(f"  10x path never liquidated in either window: {c['condition_2_10x_never_liquidated_either_window']}")
    lines.append("")
    lines.append(f"Wall time: {results['wall_time_seconds']:.1f}s")

    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n")


def make_figures(results: dict, grid: list) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    btc_csv = OUT_DIR / "grid_returns_BTC-USD.csv"
    btc_grid = pd.read_csv(btc_csv)
    btc_grid["tune_rank"] = btc_grid["tune_return"].rank(ascending=False, method="min")
    btc_grid["holdout_rank"] = btc_grid["holdout_return"].rank(ascending=False, method="min")
    winner_label = results["per_instrument"]["BTC-USD"]["winner_config_label"]
    winner_row = btc_grid[btc_grid["config_label"] == winner_label].iloc[0]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(btc_grid["tune_rank"], btc_grid["holdout_rank"], alpha=0.5, s=18, label="420 configs")
    ax.scatter(
        [winner_row["tune_rank"]], [winner_row["holdout_rank"]], color="red", s=90, marker="*", label="tuning-window winner"
    )
    ax.set_xlabel("Tuning-window return rank (1 = best)")
    ax.set_ylabel("Holdout return rank (1 = best)")
    ax.set_title("BTC-USD: in-sample rank vs holdout rank (420 configs)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "is_vs_oos_rank_BTC.png", dpi=150)
    plt.close(fig)

    tickers = list(results["per_instrument"].keys())
    t1s = [results["per_instrument"][t]["T1_holdout_percentile"] for t in tickers]
    order = np.argsort(t1s)
    tickers_sorted = [tickers[i] for i in order]
    t1s_sorted = [t1s[i] for i in order]

    fig, ax = plt.subplots(figsize=(7, 8))
    ax.scatter(t1s_sorted, range(len(tickers_sorted)), color="steelblue")
    ax.axvline(50, color="grey", linestyle="--", label="50 = selection told you nothing")
    ax.set_yticks(range(len(tickers_sorted)))
    ax.set_yticklabels(tickers_sorted, fontsize=8)
    ax.set_xlabel("T1: winner's holdout percentile among the 420")
    ax.set_title("Winner holdout percentile, 23 instruments")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "winner_holdout_percentiles.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, window_name in zip(axes, ("tuning", "holdout")):
        w = results["part3_btc_leverage"][window_name]
        lev10 = w["leverage_10x"]
        dates = pd.to_datetime(lev10["dates"])
        ax.plot(dates, lev10["as_shown_equity_curve"], label="as-shown (no liquidation)")
        ax.plot(dates, lev10["liquidated_equity_curve"], label="liquidated path", linestyle="--")
        ax.set_yscale("log")
        ax.set_title(f"BTC 10x -- {window_name} window")
        ax.set_xlabel("Date")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Equity multiple (log scale)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "leverage_10x_BTC.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
