"""
C06 orchestration: runs every arm in PREREGISTRATION.md and writes
out/results.json, out/summary.txt, out/grid_dashboard_vs_truth.png and
out/band_grid_equity.png.

Grid (Mechanism 1): r in {10%,20%,30%} x levels in {10,20,50} = 9 settings,
each at 1x and 5x leverage, on the hourly arm (BTC-USD, ETH-USD, ~730 days)
and the daily arm (BTC-USD from 2014-09, ETH-USD from 2017-11), 90-day
(calendar) horizons starting every 7 days through the available history.

Band grid (Mechanism 2): U-FX (EURUSD=X, GBPUSD=X, USDJPY=X), hourly
(~730 days) and daily (2005-01 -> 2026-08-31), 2 sizings x 3 unit sizes,
one run per calendar-quarter start, each continuing to the end of data or
ruin.

Everything here is read-only against `common/` and writes only under
../out/. Seeds are fixed wherever a choice is made (none needed here beyond
what grid_sim/band_grid_sim already do deterministically).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.data import load_daily, load_intraday  # noqa: E402

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))
from grid_sim import run_grid  # noqa: E402
from band_grid_sim import run_band_grid  # noqa: E402

OUT_DIR = CODE_DIR.parent / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class _NumpyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)

DATA_END = "2026-08-31"
HORIZON_DAYS = 90
START_STEP_DAYS = 7
GRID_R_VALUES = [0.10, 0.20, 0.30]
GRID_LEVELS = [10, 20, 50]
GRID_CAPITAL = 10_000.0

BAND_TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
BAND_SIZINGS = ["constant", "martingale"]
BAND_UNIT_FRACS = [0.5, 1.0, 2.0]
BAND_EQUITY0 = 10_000.0
BAND_HOURLY_DAILY_END = "2026-08-31"
BAND_DAILY_START = "2005-01-01"


def _run_starts(index: pd.DatetimeIndex, horizon_days: int, step_days: int) -> list[int]:
    if len(index) == 0:
        return []
    starts = []
    i = 0
    last_date = index[-1]
    step = pd.Timedelta(days=step_days)
    horizon = pd.Timedelta(days=horizon_days)
    cursor = index[0]
    while cursor + horizon <= last_date:
        pos = index.searchsorted(cursor, side="left")
        if pos < len(index) and (not starts or pos != starts[-1]):
            starts.append(int(pos))
        cursor += step
    return starts


def _slice_horizon(bars: pd.DataFrame, start_pos: int, horizon_days: int) -> pd.DataFrame:
    start_date = bars.index[start_pos]
    end_date = start_date + pd.Timedelta(days=horizon_days)
    mask = (bars.index >= start_date) & (bars.index < end_date)
    return bars.loc[mask]


def run_grid_arm(bars: pd.DataFrame, arm_name: str, ticker: str) -> list[dict]:
    starts = _run_starts(bars.index, HORIZON_DAYS, START_STEP_DAYS)
    records = []
    for r in GRID_R_VALUES:
        for levels in GRID_LEVELS:
            for leverage in (1.0, 5.0):
                for start_pos in starts:
                    window = _slice_horizon(bars, start_pos, HORIZON_DAYS)
                    if len(window) < 2:
                        continue
                    p0 = float(window.iloc[0]["open"])
                    res = run_grid(
                        window, p0=p0, r=r, levels=levels, capital=GRID_CAPITAL, leverage=leverage
                    )
                    bh_qty = (1.0 - 10.0 / 10_000.0) / p0
                    bh_final = float(window.iloc[-1]["close"]) * bh_qty
                    bh_return = bh_final - 1.0
                    records.append(
                        {
                            "arm": arm_name,
                            "ticker": ticker,
                            "r": r,
                            "levels": levels,
                            "leverage": leverage,
                            "start_date": str(bars.index[start_pos].date()),
                            "grid_profit": res.grid_profit,
                            "true_pnl": res.true_pnl,
                            "true_pnl_frac": res.true_pnl_frac,
                            "buy_hold_return_frac": bh_return,
                            "cash_return_frac": 0.0,
                            "left_range_up": res.left_range_up,
                            "left_range_down": res.left_range_down,
                            "liquidated": res.liquidated,
                        }
                    )
    return records


def summarize_grid_setting(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {"n_runs": 0}
    grid_profit = np.array([r["grid_profit"] for r in records])
    true_pnl_frac = np.array([r["true_pnl_frac"] for r in records])
    bh = np.array([r["buy_hold_return_frac"] for r in records])
    liquidated = np.array([r["liquidated"] for r in records])
    left_up = np.array([r["left_range_up"] for r in records])
    left_down = np.array([r["left_range_down"] for r in records])

    out = {
        "n_runs": n,
        "share_grid_profit_positive": float(np.mean(grid_profit > 0)),
        "share_true_pnl_negative": float(np.mean(true_pnl_frac < 0)),
        "median_true_pnl_frac": float(np.median(true_pnl_frac)),
        "p05_true_pnl_frac": float(np.percentile(true_pnl_frac, 5)),
        "p95_true_pnl_frac": float(np.percentile(true_pnl_frac, 95)),
        "share_beat_buy_hold": float(np.mean(true_pnl_frac > bh)),
        "share_beat_cash": float(np.mean(true_pnl_frac > 0.0)),
        "share_left_range": float(np.mean(left_up | left_down)),
        "share_left_range_up": float(np.mean(left_up)),
        "share_left_range_down": float(np.mean(left_down)),
    }
    if np.any(liquidated) or True:
        out["share_liquidated"] = float(np.mean(liquidated))
    return out


def run_band_grid_arm(bars: pd.DataFrame, arm_name: str, ticker: str) -> list[dict]:
    quarter_starts = pd.date_range(bars.index[0], bars.index[-1], freq="QS")
    records = []
    for sizing in BAND_SIZINGS:
        for unit_frac in BAND_UNIT_FRACS:
            for q_start in quarter_starts:
                pos = bars.index.searchsorted(q_start, side="left")
                if pos >= len(bars):
                    continue
                window = bars.iloc[pos:]
                if len(window) < 25:
                    continue
                res = run_band_grid(
                    window,
                    equity0=BAND_EQUITY0,
                    unit_frac=unit_frac,
                    sizing=sizing,
                    fx_cost_bps=2.0,
                )
                data_days_after = (bars.index[-1] - bars.index[pos]).days
                records.append(
                    {
                        "arm": arm_name,
                        "ticker": ticker,
                        "sizing": sizing,
                        "unit_frac": unit_frac,
                        "start_date": str(bars.index[pos].date()),
                        "start_pos": int(pos),
                        "data_days_after_start": data_days_after,
                        "n_baskets_closed": res.n_baskets_closed,
                        "n_baskets_won": res.n_baskets_won,
                        "basket_pnls": res.basket_pnls,
                        "monthly_returns": res.monthly_returns,
                        "ruined": res.ruined,
                        "ruin_bar": res.ruin_bar,
                        "ruin_date": str(res.ruin_date.date()) if res.ruin_date is not None else None,
                        "n_bars_alive": len(res.equity_curve),
                    }
                )
    return records


def summarize_band_setting(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {"n_runs": 0}
    all_pnls = [p for r in records for p in r["basket_pnls"]]
    n_baskets = sum(r["n_baskets_closed"] for r in records)
    n_won = sum(r["n_baskets_won"] for r in records)
    all_monthly = [m for r in records for m in r["monthly_returns"]]
    ruined = [r["ruined"] for r in records]

    def ruin_within(years: int) -> dict:
        horizon_days = years * 365
        eligible = [r for r in records if r["data_days_after_start"] >= horizon_days]
        if not eligible:
            return {"share": None, "n_eligible": 0}
        ruined_within = [
            r for r in eligible if r["ruined"] and r["ruin_bar"] is not None and _bars_to_days(r) <= horizon_days
        ]
        return {"share": len(ruined_within) / len(eligible), "n_eligible": len(eligible)}

    def _bars_to_days(r: dict) -> float:
        start = pd.Timestamp(r["start_date"])
        end = pd.Timestamp(r["ruin_date"])
        return (end - start).days

    ruin_bar_days = [
        (pd.Timestamp(r["ruin_date"]) - pd.Timestamp(r["start_date"])).days
        for r in records
        if r["ruined"] and r["ruin_date"] is not None
    ]

    return {
        "n_runs": n,
        "n_baskets_total": n_baskets,
        "basket_win_rate": (n_won / n_baskets) if n_baskets else None,
        "median_monthly_return_while_alive": float(np.median(all_monthly)) if all_monthly else None,
        "monthly_return_definition": (
            "median over calendar months of each run's month-end-equity-over-prior-month-end-equity minus 1, "
            "pooled across all runs of this setting, using every month observed while the run was alive "
            "(a ruined run simply stops contributing months after ruin)"
        ),
        "share_ruined_within_1y": ruin_within(1),
        "share_ruined_within_3y": ruin_within(3),
        "share_ruined_within_5y": ruin_within(5),
        "median_time_to_ruin_days": float(np.median(ruin_bar_days)) if ruin_bar_days else None,
        "share_runs_ruined_overall": float(np.mean(ruined)),
    }


def build_grid_dashboard_figure(daily_records: list[dict], path: Path) -> None:
    # Unlevered runs only: a liquidated 5x run loses exactly its margin, which would draw a false
    # floor across the picture. The 5x arm is reported in numbers, not in this figure.
    daily_records = [r for r in daily_records if r["leverage"] == 1.0]
    fig, ax = plt.subplots(figsize=(8, 6))
    gp = np.array([r["grid_profit"] for r in daily_records])
    tp = np.array([r["true_pnl"] for r in daily_records])
    ax.scatter(gp, tp, s=6, alpha=0.25, color="#1f77b4")
    lims = [min(gp.min(), tp.min()), max(gp.max(), tp.max())]
    ax.plot(lims, lims, color="gray", linestyle="--", linewidth=1, label="grid profit = true P&L")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Grid profit ($) -- the dashboard number")
    ax.set_ylabel("True P&L ($) -- equity vs. starting capital")
    ax.set_title("C06 daily arm, 1x: grid-profit dashboard vs. true P&L ($10,000 start, all settings)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def build_band_grid_equity_figure(eurusd_daily: pd.DataFrame, path: Path) -> None:
    quarter_starts = pd.date_range(eurusd_daily.index[0], eurusd_daily.index[-1], freq="QS")
    runs = []
    for q_start in quarter_starts:
        pos = eurusd_daily.index.searchsorted(q_start, side="left")
        if pos >= len(eurusd_daily):
            continue
        window = eurusd_daily.iloc[pos:]
        if len(window) < 25:
            continue
        res = run_band_grid(window, equity0=BAND_EQUITY0, unit_frac=1.0, sizing="constant", fx_cost_bps=2.0)
        runs.append((str(eurusd_daily.index[pos].date()), res))

    q1_2005 = next((r for d, r in runs if d.startswith("2005")), None)
    final_equities = [(d, r, r.equity_curve.iloc[-1]) for d, r in runs]
    final_equities.sort(key=lambda x: x[2])
    median_run = final_equities[len(final_equities) // 2] if final_equities else None
    ruined_run = next(((d, r) for d, r in runs if r.ruined), None)

    fig, ax = plt.subplots(figsize=(9, 5))
    if ruined_run is not None:
        d, r = ruined_run
        ax.plot(r.equity_curve.index, r.equity_curve.values, label=f"ruined run, start {d}", color="#d62728")
    elif q1_2005 is not None:
        ax.plot(
            q1_2005.equity_curve.index,
            q1_2005.equity_curve.values,
            label="2005-Q1 start (no ruin in this run)",
            color="#d62728",
        )
    if median_run is not None:
        d, r, _ = median_run
        ax.plot(r.equity_curve.index, r.equity_curve.values, label=f"median-outcome run, start {d}", color="#2ca02c")
    ax.axhline(BAND_EQUITY0, color="gray", linestyle=":", linewidth=1)
    ax.axhline(0.20 * BAND_EQUITY0, color="black", linestyle="--", linewidth=1, label="ruin level (20% of start)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity ($)")
    ax.set_title("C06 band grid: EURUSD daily, 1x constant-unit sizing")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    results: dict = {"grid": {}, "band_grid": {}}

    print("Loading data...")
    btc_daily = load_daily(["BTC-USD"], "2014-09-01", DATA_END)["BTC-USD"]
    eth_daily = load_daily(["ETH-USD"], "2017-11-01", DATA_END)["ETH-USD"]
    btc_hourly = load_intraday("BTC-USD", "60m")
    eth_hourly = load_intraday("ETH-USD", "60m")

    all_daily_grid_records: list[dict] = []
    all_grid_records: list[dict] = []

    print("Running grid arm: hourly BTC/ETH...")
    for ticker, bars in [("BTC-USD", btc_hourly), ("ETH-USD", eth_hourly)]:
        recs = run_grid_arm(bars, "hourly", ticker)
        all_grid_records.extend(recs)

    print("Running grid arm: daily BTC/ETH...")
    for ticker, bars in [("BTC-USD", btc_daily), ("ETH-USD", eth_daily)]:
        recs = run_grid_arm(bars, "daily", ticker)
        all_grid_records.extend(recs)
        all_daily_grid_records.extend(recs)

    grid_settings_summary = {}
    for arm in ["hourly", "daily"]:
        for ticker in ["BTC-USD", "ETH-USD"]:
            for r in GRID_R_VALUES:
                for levels in GRID_LEVELS:
                    for leverage in (1.0, 5.0):
                        subset = [
                            rec
                            for rec in all_grid_records
                            if rec["arm"] == arm
                            and rec["ticker"] == ticker
                            and rec["r"] == r
                            and rec["levels"] == levels
                            and rec["leverage"] == leverage
                        ]
                        key = f"{arm}|{ticker}|r={r}|levels={levels}|lev={leverage}x"
                        grid_settings_summary[key] = summarize_grid_setting(subset)

    grid_pooled = {}
    for arm in ["hourly", "daily"]:
        for leverage in (1.0, 5.0):
            subset = [rec for rec in all_grid_records if rec["arm"] == arm and rec["leverage"] == leverage]
            grid_pooled[f"{arm}|pooled|lev={leverage}x"] = summarize_grid_setting(subset)

    results["grid"]["by_setting"] = grid_settings_summary
    results["grid"]["pooled"] = grid_pooled
    results["grid"]["n_total_runs"] = len(all_grid_records)

    print("Running band grid arm: hourly and daily U-FX...")
    band_records: list[dict] = []
    for ticker in BAND_TICKERS:
        hourly_bars = load_intraday(ticker, "60m")
        band_records.extend(run_band_grid_arm(hourly_bars, "hourly", ticker))
    for ticker in BAND_TICKERS:
        daily_bars = load_daily([ticker], BAND_DAILY_START, DATA_END)[ticker]
        band_records.extend(run_band_grid_arm(daily_bars, "daily", ticker))

    band_settings_summary = {}
    for arm in ["hourly", "daily"]:
        for ticker in BAND_TICKERS:
            for sizing in BAND_SIZINGS:
                for unit_frac in BAND_UNIT_FRACS:
                    subset = [
                        rec
                        for rec in band_records
                        if rec["arm"] == arm
                        and rec["ticker"] == ticker
                        and rec["sizing"] == sizing
                        and rec["unit_frac"] == unit_frac
                    ]
                    key = f"{arm}|{ticker}|{sizing}|unit={unit_frac}x"
                    band_settings_summary[key] = summarize_band_setting(subset)

    band_pooled = {}
    for arm in ["hourly", "daily"]:
        for sizing in BAND_SIZINGS:
            for unit_frac in BAND_UNIT_FRACS:
                subset = [
                    rec
                    for rec in band_records
                    if rec["arm"] == arm and rec["sizing"] == sizing and rec["unit_frac"] == unit_frac
                ]
                band_pooled[f"{arm}|pooled|{sizing}|unit={unit_frac}x"] = summarize_band_setting(subset)

    results["band_grid"]["by_setting"] = band_settings_summary
    results["band_grid"]["pooled"] = band_pooled
    results["band_grid"]["n_total_runs"] = len(band_records)

    print("Building figures...")
    build_grid_dashboard_figure(all_daily_grid_records, OUT_DIR / "grid_dashboard_vs_truth.png")
    eurusd_daily = load_daily(["EURUSD=X"], BAND_DAILY_START, DATA_END)["EURUSD=X"]
    build_band_grid_equity_figure(eurusd_daily, OUT_DIR / "band_grid_equity.png")

    wall_time = time.time() - t0
    results["wall_time_seconds"] = wall_time

    with open(OUT_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, cls=_NumpyJSONEncoder)

    summary_lines = build_summary_text(results, wall_time)
    (OUT_DIR / "summary.txt").write_text("\n".join(summary_lines) + "\n")
    print("\n".join(summary_lines))
    print(f"\nWall time: {wall_time:.1f}s")


def build_summary_text(results: dict, wall_time: float) -> list[str]:
    lines = []
    lines.append("C06 -- AI grid bot passive income -- results summary")
    lines.append(f"wall_time_seconds={wall_time:.1f}")
    lines.append("")
    lines.append("=== Mechanism 1: spot grid -- pooled by arm and leverage ===")
    for key, s in results["grid"]["pooled"].items():
        lines.append(f"-- {key} --")
        for k, v in s.items():
            lines.append(f"    {k}: {v}")
    lines.append("")
    lines.append("=== Mechanism 1: spot grid -- per setting ===")
    for key, s in results["grid"]["by_setting"].items():
        lines.append(f"-- {key} --")
        for k, v in s.items():
            lines.append(f"    {k}: {v}")
    lines.append("")
    lines.append("=== Mechanism 2: band grid -- pooled by arm/sizing/unit ===")
    for key, s in results["band_grid"]["pooled"].items():
        lines.append(f"-- {key} --")
        for k, v in s.items():
            lines.append(f"    {k}: {v}")
    lines.append("")
    lines.append("=== Mechanism 2: band grid -- per setting (ticker) ===")
    for key, s in results["band_grid"]["by_setting"].items():
        lines.append(f"-- {key} --")
        for k, v in s.items():
            lines.append(f"    {k}: {v}")
    return lines


if __name__ == "__main__":
    main()
