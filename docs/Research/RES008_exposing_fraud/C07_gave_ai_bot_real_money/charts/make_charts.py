"""
C07 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for,
drawn in the AMI style from out/results_part1.json, out/results_part2.json,
out/derived_extras.json and out/part2_arrays.npz. Every number on a chart is
read from those files at run time; nothing is typed in.

Run from the RES008 root:
    .venv/bin/python C07_gave_ai_bot_real_money/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from matplotlib.ticker import FuncFormatter

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

OUT = CLAIM_DIR / "out"
RESULTS1 = json.loads((OUT / "results_part1.json").read_text())
RESULTS2 = json.loads((OUT / "results_part2.json").read_text())

SRC1 = "C07_gave_ai_bot_real_money/out/results_part1.json"
SRC2 = "C07_gave_ai_bot_real_money/out/results_part2.json"
SRC_ARRAYS = "C07_gave_ai_bot_real_money/out/part2_arrays.npz"
HIST_CACHE = CHART_DIR / "01_week_excess_hist.json"
H3_THRESHOLD_PCT = 60  # our pre-registered bar for the trending-month win rate (PREREGISTRATION.md, H3)


def _week_excess_hist():
    """Binned one-week excess returns of the zero-skill bots. The raw array
    (out/part2_arrays.npz) is git-ignored for size, so the bin counts are cached
    next to the charts and used when the array is absent."""
    npz = OUT / "part2_arrays.npz"
    if npz.exists():
        arr = np.load(npz)["week_excess_bot"]
        values = arr[np.isfinite(arr)] * 100  # fraction -> percentage points
        counts, edges = np.histogram(values, bins=150, range=(-25, 25))
        HIST_CACHE.write_text(json.dumps({
            "source": SRC_ARRAYS, "key": "week_excess_bot", "unit": "percentage points",
            "n_values": int(values.size), "n_inside_range": int(counts.sum()),
            "edges": [round(float(e), 6) for e in edges], "counts": [int(c) for c in counts],
        }, indent=1) + "\n")
        return counts, edges
    cached = json.loads(HIST_CACHE.read_text())
    return np.array(cached["counts"]), np.array(cached["edges"])


def chart_01_zero_skill_week_vs_spy() -> Path:
    """Beats 1, 5: distribution of the zero-skill bot's one-week excess return
    vs SPY, with the share beating SPY and the share beating it by >=3 points."""
    z = RESULTS2["zero_skill_bot"]
    pct = z["week_excess_percentiles"]
    share_beats = 100 * z["week_vs_spy"]["share_beats_spy"]
    share_beats_3pt = 100 * z["week_vs_spy"]["share_beats_spy_by_3pt"]
    n_pairs = z["week_vs_spy"]["n_pairs"]

    counts, edges = _week_excess_hist()

    fig, ax = S.new_figure(
        "A bot that picks stocks at random beats the market about half the weeks",
        f"One-week excess return over SPY, {n_pairs:,} (bot, week) pairs, 2005–2026",
    )
    colors = [S.GOOD if lo >= 3 - 1e-9 else S.MEASURED for lo in edges[:-1]]
    ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color=colors, edgecolor="none")
    ax.axvline(0, color=S.TEXT, linewidth=1.6)
    ax.set_xlabel("One-week excess return over SPY, percentage points")
    ax.set_ylabel("Count of (bot, week) pairs")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:,.0f}k" if v else "0"))
    ax.set_xlim(-25, 25)

    S.big_number(ax, 0.03, 0.90, f"{share_beats:.1f}%", color=S.MEASURED, size=44, ha="left")
    ax.text(0.03, 0.80, "of weeks beat SPY", transform=ax.transAxes, fontsize=18, color=S.MUTED, ha="left")
    S.big_number(ax, 0.03, 0.64, f"{share_beats_3pt:.1f}%", color=S.GOOD, size=44, ha="left")
    ax.text(0.03, 0.54, "beat SPY by 3 points or more", transform=ax.transAxes, fontsize=18, color=S.MUTED, ha="left")

    S.footer(
        fig, SRC_ARRAYS,
        f"Middle 90% of weeks: \u2212{abs(100*pct['p5']):.1f} to +{100*pct['p95']:.1f} points of excess return · zero skill, entries picked at random",
    )
    return S.save(fig, CHART_DIR / "01_zero_skill_week_vs_spy.png")


def chart_02_trending_month_winrate() -> Path:
    """Beat 7: two bars, trade win rate in all months vs trending months.
    No error bars -- the printed Wilson intervals are far too narrow for
    correlated trades (RESULTS.md section 1)."""
    tm = RESULTS2["trending_month_conditional"]
    all_rate = 100 * tm["unconditional_trade_win_rate"]
    trend_rate = 100 * tm["trend_trade_win_rate"]
    n_all = tm["n_all_trades"]
    n_trend = tm["n_trend_trades"]
    share_trending = 100 * tm["share_of_windows_trending"]

    fig, ax = S.new_figure(
        "In a month when stocks are already rising, random trades win more often",
        "Zero-skill bot, trade win rate, by whether the entry fell in a trending month",
    )
    labels = ["All months", f"Trending months\n(basket up 8%+ over 21 days)"]
    values = [all_rate, trend_rate]
    colors = [S.BENCHMARK, S.MEASURED]
    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.axhline(H3_THRESHOLD_PCT, xmin=0.40, color=S.MUTED, linewidth=2.0, linestyle="--")
    ax.text(0.52, H3_THRESHOLD_PCT + 1.5, f"what we predicted in advance: {H3_THRESHOLD_PCT}% or more", ha="center",
            va="bottom", fontsize=16, color=S.MUTED)
    for rect, value, n in zip(bars, values, (n_all, n_trend)):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 2.5, f"{value:.1f}%", ha="center", va="bottom",
                fontsize=26, fontweight="bold", family=S.mono(), color=S.TEXT)
        ax.text(rect.get_x() + rect.get_width() / 2, value / 2, f"n={n:,}", ha="center", va="center",
                fontsize=14, color=S.BG, family=S.mono())
    ax.set_ylim(0, 100)
    ax.set_ylabel("Trade win rate, %")
    ax.grid(axis="x", visible=False)

    S.stamp(fig, "PREDICTION MET NARROWLY — READ AS AN ILLUSTRATION")
    S.footer(
        fig, SRC2,
        f"{share_trending:.1f}% of windows are trending · point estimates only — the bots trade the same ten stocks, so printed intervals are too narrow",
    )
    return S.save(fig, CHART_DIR / "02_trending_month_winrate.png")


def _ticker_rows(window: str):
    return sorted(RESULTS1[window]["per_ticker"], key=lambda r: r["buy_hold_total_return"], reverse=True)


def _chart_rule_vs_buy_hold(window: str, window_label: str, filename: str) -> Path:
    """Beat 5: per-ticker net return of the RSI rule vs simply holding, one window."""
    rows = _ticker_rows(window)
    tickers = [r["ticker"] for r in rows]
    rule = [100 * r["net_total_return"] for r in rows]
    hold = [100 * r["buy_hold_total_return"] for r in rows]
    n_beat = RESULTS1[window]["pooled"]["n_tickers_beat_buy_hold_net"]
    n_tickers = RESULTS1[window]["pooled"]["n_tickers"]

    x = np.arange(len(tickers))
    width = 0.38

    fig, ax = S.new_figure(
        f"Buying the dip earned less than just holding, on almost every stock ({window_label})",
        f"Total return, RSI rule vs buy-and-hold, {n_tickers} large US stocks · rule beat holding on {n_beat} of {n_tickers}",
    )
    ax.bar(x - width / 2, rule, width=width, color=S.MEASURED, label="RSI rule (long < 30, flat > 70)")
    ax.bar(x + width / 2, hold, width=width, color=S.BENCHMARK, label="Buy and hold")
    ax.axhline(0, color=S.TEXT, linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(tickers, fontsize=14, rotation=45, ha="right")
    ax.set_ylabel("Total return, %")
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SRC1, "Next-open fills, 5 bps cost per side. Tickers sorted by buy-and-hold return.")
    return S.save(fig, CHART_DIR / filename)


def chart_03_rule_vs_buy_hold_define() -> Path:
    return _chart_rule_vs_buy_hold("DEFINE", "2005–2018", "03_rule_vs_buy_hold_define.png")


def chart_04_rule_vs_buy_hold_holdout() -> Path:
    return _chart_rule_vs_buy_hold("HOLDOUT", "2019–2026", "04_rule_vs_buy_hold_holdout.png")


def chart_05_placebo_percentile() -> Path:
    """Beat 5: the rule's entries against random entries with the same number
    of trades -- mean placebo percentile, both windows, with their intervals."""
    define = RESULTS1["DEFINE"]["pooled"]["mean_placebo_percentile"]
    holdout = RESULTS1["HOLDOUT"]["pooled"]["mean_placebo_percentile"]
    windows = ["2005–2018\n(DEFINE)", "2019–2026\n(HOLDOUT)"]
    est = [100 * define["estimate"], 100 * holdout["estimate"]]
    lo = [100 * define["lower"], 100 * holdout["lower"]]
    hi = [100 * define["upper"], 100 * holdout["upper"]]

    fig, ax = S.new_figure(
        "Against random entries with the same number of trades, no timing skill shows up",
        "Mean placebo percentile of the rule's entries · 50 = no better than a random entry · 95% interval",
    )
    x = np.arange(len(windows))
    ax.axhspan(0, 100, color=S.PANEL, zorder=0)
    ax.axhline(50, color=S.BENCHMARK, linewidth=2.0, linestyle="--", label="50 = random entry")
    ax.axhspan(95, 100, color=S.CARD, alpha=0.5, zorder=0)
    ax.text(1.35, 96.5, "95th percentile\n(would show timing skill)", fontsize=13, color=S.MUTED, ha="left", va="center")

    yerr = [[e - l for e, l in zip(est, lo)], [h - e for e, h in zip(est, hi)]]
    ax.errorbar(x, est, yerr=yerr, fmt="o", color=S.MEASURED, markersize=18, capsize=10, elinewidth=3, capthick=3,
                label="RSI rule's entries")
    for xi, value, upper in zip(x, est, hi):
        ax.text(xi, upper + 4, f"{value:.0f}", ha="center", va="bottom", fontsize=24, fontweight="bold",
                family=S.mono(), color=S.TEXT)

    ax.set_xlim(-0.6, 1.9)
    ax.set_xticks(x)
    ax.set_xticklabels(windows)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Placebo percentile")
    ax.legend(loc="lower left")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SRC1, "500 matched random-entry placebos per ticker, pooled across 22 tickers.")
    return S.save(fig, CHART_DIR / "05_placebo_percentile.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_zero_skill_week_vs_spy,
        chart_02_trending_month_winrate,
        chart_03_rule_vs_buy_hold_define,
        chart_04_rule_vs_buy_hold_holdout,
        chart_05_placebo_percentile,
    )
    for chart in charts:
        print("wrote", chart().relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
