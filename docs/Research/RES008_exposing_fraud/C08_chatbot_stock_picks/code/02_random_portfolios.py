"""C08 Part 1 -- what luck alone does, no chatbot involved.

For each month-start 12-month window from 2006-01 to 2025-08 (window = first
trading day of the month to the first trading day twelve months later, total-
return adjusted closes), draws 10,000 random equal-weight 10-stock buy-and-
hold portfolios from U_LARGE100 names with data at the window start. Reports,
pooled over all windows and per window: share beating the universe equal-
weight mean and SPY (same buy-and-hold convention); the distribution of
excess return over the universe mean; how often a random portfolio clears the
video's gaps (+3/+13/+22 ahead, -8 behind); the analytic and measured-p
binomial probability of >=3-of-4 independent draws beating the benchmark.

Vectorised: one (n_windows x n_names) total-return matrix, then a single
random ticker-index draw per window replicated 10,000 times, averaged with
matrix multiplication -- no Python-level loop over portfolios.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.data import load_daily  # noqa: E402

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))
from universe_large100 import U_LARGE100  # noqa: E402

OUT_DIR = CODE_DIR.parent / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_DRAWS = 10_000
PORTFOLIO_SIZE = 10
SEED = 20260917
WINDOW_MONTHS = 12
FIRST_WINDOW_START_MONTH = "2006-01"
LAST_WINDOW_START_MONTH = "2025-08"
DATA_END = "2026-08-31"
GAP_MARKS_AHEAD = (3, 13, 22)
GAP_MARK_BEHIND = -8
REPRESENTATIVE_WINDOW = "2024-12"


def first_trading_day_on_or_after(index: pd.DatetimeIndex, month_start: pd.Timestamp) -> pd.Timestamp | None:
    candidates = index[index >= month_start]
    if len(candidates) == 0:
        return None
    return candidates[0]


def build_window_starts() -> list[pd.Timestamp]:
    return list(pd.date_range(FIRST_WINDOW_START_MONTH + "-01", LAST_WINDOW_START_MONTH + "-01", freq="MS"))


def analytic_p_ge3_of4(p: float) -> float:
    return float(sum(stats.binom.pmf(k, 4, p) for k in (3, 4)))


def draw_portfolio_returns(
    available_rets: np.ndarray, n_draws: int, portfolio_size: int, rng: np.random.Generator
) -> np.ndarray:
    """Mean return of `n_draws` random equal-weight `portfolio_size`-name portfolios.

    Vectorised without-replacement sampling: argsort a (n_draws x n_available)
    matrix of uniform randoms per row and keep the first `portfolio_size`
    columns as the chosen indices, so there is no per-portfolio Python loop.
    """
    n_available = len(available_rets)
    rand_keys = rng.random((n_draws, n_available))
    draw_local_idx = np.argsort(rand_keys, axis=1)[:, :portfolio_size]
    return available_rets[draw_local_idx].mean(axis=1)


def main() -> None:
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    print("loading daily bars for U_LARGE100 + SPY ...", flush=True)
    bars: dict[str, pd.DataFrame] = {}
    load_errors: dict[str, str] = {}
    for ticker in U_LARGE100 + ["SPY"]:
        try:
            bars[ticker] = load_daily([ticker], start="2005-06-01", end=DATA_END)[ticker]
        except Exception as exc:  # BK: known no-data ticker, recorded not substituted
            load_errors[ticker] = repr(exc)
    spy_bars = bars.pop("SPY")
    print(f"loaded {len(bars)}/{len(U_LARGE100)} universe names; load errors: {load_errors}", flush=True)

    all_dates = spy_bars.index
    window_start_months = build_window_starts()

    windows = []
    for month_start in window_start_months:
        end_month_start = month_start + pd.DateOffset(months=WINDOW_MONTHS)
        start_day = first_trading_day_on_or_after(all_dates, month_start)
        end_day = first_trading_day_on_or_after(all_dates, end_month_start)
        if start_day is None or end_day is None:
            continue
        windows.append({
            "label": month_start.strftime("%Y-%m"),
            "start": start_day,
            "end": end_day,
        })

    print(f"{len(windows)} windows built ({windows[0]['label']} .. {windows[-1]['label']})", flush=True)

    tickers = U_LARGE100
    n_tickers = len(tickers)

    per_window_records = []
    pooled_excess = []
    pooled_beat_universe = []
    pooled_beat_spy = []
    within_window_spreads = []
    representative_window_excess = None
    representative_window_meta = None

    for w in windows:
        start, end = w["start"], w["end"]

        available_mask = np.zeros(n_tickers, dtype=bool)
        rets = np.full(n_tickers, np.nan)
        for i, t in enumerate(tickers):
            df = bars.get(t)
            if df is None:
                continue
            if start not in df.index or end not in df.index:
                continue
            p0 = df.loc[start, "close"]
            p1 = df.loc[end, "close"]
            if p0 <= 0 or pd.isna(p0) or pd.isna(p1):
                continue
            rets[i] = p1 / p0 - 1.0
            available_mask[i] = True

        available_idx = np.where(available_mask)[0]
        n_available = len(available_idx)
        if n_available < PORTFOLIO_SIZE:
            raise RuntimeError(f"window {w['label']}: only {n_available} names available, need {PORTFOLIO_SIZE}")

        available_rets = rets[available_idx]
        universe_mean_return = float(np.mean(available_rets))

        spy_p0 = spy_bars.loc[start, "close"]
        spy_p1 = spy_bars.loc[end, "close"]
        spy_return = float(spy_p1 / spy_p0 - 1.0)

        portfolio_returns = draw_portfolio_returns(available_rets, N_DRAWS, PORTFOLIO_SIZE, rng)

        excess_vs_universe = (portfolio_returns - universe_mean_return) * 100.0
        excess_vs_spy = (portfolio_returns - spy_return) * 100.0

        beat_universe_share = float(np.mean(portfolio_returns > universe_mean_return))
        beat_spy_share = float(np.mean(portfolio_returns > spy_return))

        pcts = np.percentile(excess_vs_universe, [5, 25, 50, 75, 95])
        iqr = float(pcts[3] - pcts[1])
        spread_5_95 = float(pcts[4] - pcts[0])

        gap_shares_vs_spy_ahead = {
            f"+{g}": float(np.mean(excess_vs_spy >= g)) for g in GAP_MARKS_AHEAD
        }
        gap_share_vs_spy_behind = float(np.mean(excess_vs_spy <= GAP_MARK_BEHIND))
        gap_shares_vs_universe_ahead = {
            f"+{g}": float(np.mean(excess_vs_universe >= g)) for g in GAP_MARKS_AHEAD
        }
        gap_share_vs_universe_behind = float(np.mean(excess_vs_universe <= GAP_MARK_BEHIND))

        p_analytic = analytic_p_ge3_of4(0.5)
        p_measured_vs_spy = analytic_p_ge3_of4(beat_spy_share)

        per_window_records.append({
            "window": w["label"],
            "start": str(start.date()),
            "end": str(end.date()),
            "n_available": int(n_available),
            "universe_mean_return_pct": universe_mean_return * 100.0,
            "spy_return_pct": spy_return * 100.0,
            "beat_universe_share": beat_universe_share,
            "beat_spy_share": beat_spy_share,
            "excess_vs_universe_pct": {
                "p5": float(pcts[0]), "p25": float(pcts[1]), "p50": float(pcts[2]),
                "p75": float(pcts[3]), "p95": float(pcts[4]),
                "iqr": iqr, "spread_5_95": spread_5_95,
            },
            "gap_share_vs_spy_ahead": gap_shares_vs_spy_ahead,
            "gap_share_vs_spy_behind_-8": gap_share_vs_spy_behind,
            "gap_share_vs_universe_ahead": gap_shares_vs_universe_ahead,
            "gap_share_vs_universe_behind_-8": gap_share_vs_universe_behind,
            "p_ge3of4_analytic_p50": p_analytic,
            "p_ge3of4_measured_p_beat_spy": p_measured_vs_spy,
        })

        pooled_excess.append(excess_vs_universe)
        pooled_beat_universe.append(portfolio_returns > universe_mean_return)
        pooled_beat_spy.append(portfolio_returns > spy_return)
        within_window_spreads.append(spread_5_95)

        if w["label"] == REPRESENTATIVE_WINDOW:
            representative_window_excess = excess_vs_spy.copy()
            representative_window_meta = {
                "window": w["label"], "start": str(start.date()), "end": str(end.date()),
                "spy_return_pct": spy_return * 100.0, "universe_mean_return_pct": universe_mean_return * 100.0,
            }

    pooled_excess_arr = np.concatenate(pooled_excess)
    pooled_beat_universe_arr = np.concatenate(pooled_beat_universe)
    pooled_beat_spy_arr = np.concatenate(pooled_beat_spy)

    pooled_pcts = np.percentile(pooled_excess_arr, [5, 25, 50, 75, 95])
    pooled_iqr = float(pooled_pcts[3] - pooled_pcts[1])
    pooled_spread_5_95 = float(pooled_pcts[4] - pooled_pcts[0])
    median_within_window_spread_5_95 = float(np.median(within_window_spreads))

    pooled_beat_universe_share = float(np.mean(pooled_beat_universe_arr))
    pooled_beat_spy_share = float(np.mean(pooled_beat_spy_arr))

    p_analytic_p50 = analytic_p_ge3_of4(0.5)
    p_measured_beat_spy_pooled = analytic_p_ge3_of4(pooled_beat_spy_share)
    p_measured_beat_universe_pooled = analytic_p_ge3_of4(pooled_beat_universe_share)

    results = {
        "meta": {
            "n_windows": len(windows),
            "n_draws_per_window": N_DRAWS,
            "portfolio_size": PORTFOLIO_SIZE,
            "seed": SEED,
            "data_end": DATA_END,
            "load_errors": load_errors,
            "representative_window": REPRESENTATIVE_WINDOW,
        },
        "pooled": {
            "beat_universe_share": pooled_beat_universe_share,
            "beat_spy_share": pooled_beat_spy_share,
            "excess_vs_universe_pct": {
                "p5": float(pooled_pcts[0]), "p25": float(pooled_pcts[1]), "p50": float(pooled_pcts[2]),
                "p75": float(pooled_pcts[3]), "p95": float(pooled_pcts[4]),
                "iqr": pooled_iqr, "spread_5_95_pooled_across_windows": pooled_spread_5_95,
                "median_within_window_spread_5_95": median_within_window_spread_5_95,
            },
            "p_ge3of4_analytic_p50": p_analytic_p50,
            "p_ge3of4_measured_p_beat_spy": p_measured_beat_spy_pooled,
            "p_ge3of4_measured_p_beat_universe": p_measured_beat_universe_pooled,
        },
        "per_window": per_window_records,
    }

    (OUT_DIR / "part1_random_portfolios.json").write_text(json.dumps(results, indent=2))

    if representative_window_excess is not None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 5.5))
        ax.hist(representative_window_excess, bins=80, color="#4C72B0", alpha=0.85)
        for g in GAP_MARKS_AHEAD:
            ax.axvline(g, color="#C44E52", linestyle="--", linewidth=1.2)
            ax.text(g, ax.get_ylim()[1] * 0.95, f"+{g}", color="#C44E52", ha="center")
        ax.axvline(GAP_MARK_BEHIND, color="#55A868", linestyle="--", linewidth=1.2)
        ax.text(GAP_MARK_BEHIND, ax.get_ylim()[1] * 0.95, f"{GAP_MARK_BEHIND}", color="#55A868", ha="center")
        ax.set_xlabel("one-year excess return vs SPY (percentage points)")
        ax.set_ylabel("random portfolios (of 10,000)")
        meta = representative_window_meta
        ax.set_title(
            f"Random 10-stock portfolios vs SPY, window {meta['window']} "
            f"({meta['start']} -> {meta['end']})"
        )
        fig.tight_layout()
        fig.savefig(OUT_DIR / "random_portfolio_spread.png", dpi=150)
        plt.close(fig)
    else:
        raise RuntimeError(f"representative window {REPRESENTATIVE_WINDOW} not found among built windows")

    elapsed = time.time() - t0
    print(f"Part 1 done in {elapsed:.1f}s. pooled beat_universe_share={pooled_beat_universe_share:.4f} "
          f"beat_spy_share={pooled_beat_spy_share:.4f} "
          f"median_within_window_5-95_spread={median_within_window_spread_5_95:.2f}pp", flush=True)


if __name__ == "__main__":
    main()
