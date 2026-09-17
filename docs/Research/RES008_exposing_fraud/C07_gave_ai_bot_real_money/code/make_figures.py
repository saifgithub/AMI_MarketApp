"""
C07 figures: `out/one_week_vs_spy.png` (histogram of the zero-skill bot's
one-week excess return vs SPY, 0 marked, share above 0 annotated) and
`out/trending_month_winrate.png` (zero-skill trade win rate, all months vs
trending months, with Wilson intervals). Reads only from
`out/results_part2.json` and `out/part2_arrays.npz` -- no recomputation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

THIS_DIR = Path(__file__).resolve().parent
C07_DIR = THIS_DIR.parent
OUT_DIR = C07_DIR / "out"


def make_one_week_vs_spy(results: dict, arrays: np.lib.npyio.NpzFile) -> None:
    week_excess = arrays["week_excess_bot"]
    flat = week_excess.ravel()
    flat = flat[np.isfinite(flat)]
    share_above = float(np.mean(flat > 0.0))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(flat * 100.0, bins=120, color="#3b6fa0", edgecolor="none", alpha=0.9)
    ax.axvline(0.0, color="#c0392b", linewidth=1.5, linestyle="--")
    ax.set_xlabel("One-week (5-trading-day) excess return over SPY, %")
    ax.set_ylabel("Count of (bot, window) pairs")
    ax.set_title("Zero-skill bot: one-week excess return vs SPY")
    ax.text(
        0.98, 0.95,
        f"{share_above:.1%} of windows beat SPY",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=11, color="#c0392b",
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="#c0392b", alpha=0.9),
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "one_week_vs_spy.png", dpi=150)
    plt.close(fig)


def make_trending_month_winrate(results: dict) -> None:
    trend = results["trending_month_conditional"]
    labels = ["All months", "Trending months\n(basket up >= 8% / 21d)"]

    uncond_ci = trend["unconditional_trade_win_rate_wilson_ci"]
    trend_ci = trend["trend_trade_win_rate_wilson_ci"]

    estimates = [uncond_ci["estimate"], trend_ci["estimate"]]
    lowers = [uncond_ci["estimate"] - uncond_ci["lower"], trend_ci["estimate"] - trend_ci["lower"]]
    uppers = [uncond_ci["upper"] - uncond_ci["estimate"], trend_ci["upper"] - trend_ci["estimate"]]

    fig, ax = plt.subplots(figsize=(6, 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, [e * 100 for e in estimates], color=["#3b6fa0", "#e08214"], width=0.5)
    ax.errorbar(
        x, [e * 100 for e in estimates],
        yerr=[[l * 100 for l in lowers], [u * 100 for u in uppers]],
        fmt="none", ecolor="black", capsize=6, linewidth=1.5,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Trade win rate, %")
    ax.set_title("Zero-skill bot trade win rate: all months vs trending months\n(Wilson 95% intervals)")
    ax.set_ylim(0, 100)
    for xi, e, n in zip(x, estimates, [trend["n_all_trades"], trend["n_trend_trades"]]):
        ax.text(xi, e * 100 + 3, f"n={n}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "trending_month_winrate.png", dpi=150)
    plt.close(fig)


def main() -> None:
    with open(OUT_DIR / "results_part2.json") as f:
        results = json.load(f)
    arrays = np.load(OUT_DIR / "part2_arrays.npz")

    make_one_week_vs_spy(results, arrays)
    make_trending_month_winrate(results)
    print("Wrote out/one_week_vs_spy.png and out/trending_month_winrate.png")


if __name__ == "__main__":
    main()
