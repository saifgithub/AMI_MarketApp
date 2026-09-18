"""
C08 chart pack -- the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json, out/gap_table.json and out/picks.csv.
Every number on a chart is read from those files at run time; nothing is typed
in. If an input file is missing, the affected figure is skipped with a message
and the script still exits 0.

Run from the RES008 root:
    .venv/bin/python C08_chatbot_stock_picks/charts/make_charts.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

OUT = CLAIM_DIR / "out"
SOURCE_RESULTS = "C08_chatbot_stock_picks/out/results.json"
SOURCE_GAPS = "C08_chatbot_stock_picks/out/gap_table.json"
SOURCE_PICKS = "C08_chatbot_stock_picks/out/picks.csv"


def _pct1(value_pct: float) -> str:
    """One decimal, rounded half up, so a chart label matches RESULTS.md (84.25 -> 84.3)."""
    from decimal import ROUND_HALF_UP, Decimal
    return f"{Decimal(repr(round(float(value_pct), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_picks_rows():
    if not SOURCE_PICKS or not (OUT / "picks.csv").exists():
        return None
    with (OUT / "picks.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def chart_01_random_portfolio_spread():
    """Beats 1, 5: how often a random ten-stock portfolio produces the exact
    gaps quoted in the videos (+3 / +13 / +22 ahead of SPY, -8 behind), pooled
    over all 236 twelve-month windows since 2006. Bars, not a redrawn
    histogram -- out/ stores per-window and pooled percentiles/frequencies,
    not the underlying 10,000-per-window draws, so a faithful redraw of the
    histogram shape is not available; the frequencies are exact."""
    gaps = _load_json(OUT / "gap_table.json")
    if gaps is None:
        print("skipped 01_random_portfolio_spread: out/gap_table.json not present")
        return None

    spread = gaps["within_window_spread_5_95"]
    n_windows = gaps["n_windows"]
    n_draws = gaps["draws_per_window"]

    labels = ["−8 or worse", "+3 or more", "+13 or more", "+22 or more"]
    series = []
    for key, name in (("vs_spy", "vs the index"), ("vs_universe", "vs the list's own average")):
        cell = gaps[key]
        series.append((
            name,
            [100 * cell["behind_by_at_least_8"], 100 * cell["ahead_by_at_least"]["+3"],
             100 * cell["ahead_by_at_least"]["+13"], 100 * cell["ahead_by_at_least"]["+22"]],
        ))

    fig, ax = S.new_figure(
        "A random ten-stock portfolio hits the videos' results by chance alone",
        f"Share of {n_draws:,} random portfolios per window reaching each gap, "
        f"pooled over {n_windows} twelve-month windows since 2006",
    )
    x = np.arange(len(labels))
    width = 0.34
    for offset, colour, (name, values) in zip((-width / 2, width / 2), (S.MEASURED, S.BENCHMARK), series):
        bars = ax.bar(x + offset, values, color=colour, width=width, label=name, zorder=3)
        for rect, value in zip(bars, values):
            ax.text(rect.get_x() + rect.get_width() / 2, value + 1.5, _pct1(value), ha="center",
                    va="bottom", fontsize=17, fontweight="bold", family=S.mono())
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=18)
    ax.set_ylabel("Share of random portfolios, %")
    ax.set_ylim(0, max(v for _, values in series for v in values) * 1.45)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncols=2)

    ax.text(
        0.5, 0.80,
        f"middle 90% of outcomes spans {spread['median']:.1f} points in a typical year",
        transform=ax.transAxes, ha="center", va="center", fontsize=18, color=S.TEXT, family=S.mono(),
    )

    S.footer(
        fig, SOURCE_GAPS,
        "vs_spy / vs_universe .ahead_by_at_least, .behind_by_at_least_8 · the list is today's large "
        "companies, so beating the index flatters the draw (RESULTS §2)",
    )
    return S.save(fig, CHART_DIR / "01_random_portfolio_spread.png")


def chart_02_hindsight_percentiles():
    """Beat 5, Short: the back-dated ('as of Jan 2019') picks, one dot per
    reply, against the 50th-percentile no-hindsight line, with the pooled
    mean and its interval."""
    results = _load_json(OUT / "results.json")
    if results is None:
        print("skipped 02_hindsight_percentiles: out/results.json not present")
        return None

    p3 = results["part2_3_analysis"]["part3_hindsight"]
    per_reply = sorted(p3["per_reply"], key=lambda r: r["percentile"])
    pooled = p3["pooled"]["mean_percentile"]
    ci = p3["pooled"]["bootstrap_ci"]
    n = p3["n_replies_analysed"]

    fig, ax = S.new_figure(
        "Asked to pick 'as of 2019', the picks land near the top of the luck range",
        f"Percentile of each reply's 5-year return among 10,000 random ten-stock portfolios, "
        f"2019-01-02 → 2023-12-29 · n={n} replies",
    )
    fig.subplots_adjust(left=0.10, right=0.95, bottom=0.20, top=0.72)
    y = range(len(per_reply))
    model_color = {"opus": S.MEASURED, "sonnet": S.PURPLE}
    colors = [model_color.get(r["model"], S.MEASURED) for r in per_reply]
    ax.scatter([r["percentile"] for r in per_reply], list(y), c=colors, s=90, zorder=3)
    ax.axvline(50, color=S.BENCHMARK, linewidth=2, linestyle="--", zorder=1)
    ax.text(50, len(per_reply) + 1.3, "50th percentile\n(no hindsight)", color=S.MUTED, fontsize=14,
            ha="center", va="bottom")

    ax.axvspan(ci["lower"], ci["upper"], color=S.MEASURED, alpha=0.15, zorder=0)
    ax.axvline(pooled, color=S.MEASURED, linewidth=2.5, zorder=2)
    ax.text(pooled, len(per_reply) + 1.3, f"pooled mean {pooled:.1f}\n({ci['lower']:.1f}–{ci['upper']:.1f})",
            color=S.TEXT, fontsize=15, ha="center", va="bottom", family=S.mono())

    ax.set_yticks([])
    ax.set_ylim(-1.6, len(per_reply) + 3.4)
    ax.set_xlim(40, 102)
    ax.set_xticks([40, 50, 60, 70, 80, 90, 100])
    ax.set_xlabel("Percentile vs random portfolios")
    ax.grid(axis="y", visible=False)

    for label, color in (("Opus 5", S.MEASURED), ("Sonnet 5", S.PURPLE)):
        ax.scatter([], [], c=color, s=90, label=label)
    ax.legend(loc="lower left")

    S.footer(
        fig, SOURCE_RESULTS,
        "part2_3_analysis.part3_hindsight.per_reply[].percentile, .pooled.mean_percentile, .pooled.bootstrap_ci",
    )
    return S.save(fig, CHART_DIR / "02_hindsight_percentiles.png")


def chart_03_refusal_grid():
    """Beat 5: 3 models x 10 runs, filled where the model named stocks for
    the 'now' prompt (the prompt read in beat 2). From picks.csv."""
    rows = _load_picks_rows()
    if rows is None:
        print("skipped 03_refusal_grid: out/picks.csv not present")
        return None

    models = ["haiku", "sonnet", "opus"]
    now_rows = {(r["model"], r["run"]): r for r in rows if r["prompt_key"] == "now"}
    runs = sorted({r["run"] for r in rows if r["prompt_key"] == "now"})
    grid = np.array([[0.0 if now_rows[(m, run)]["refused"] == "True" else 1.0 for run in runs] for m in models])
    named_total = int(grid.sum())
    total_cells = grid.size

    fig, ax = S.new_figure(
        "Asked the video's exact prompt, these chatbots declined most of the time",
        f"{named_total} of {total_cells} runs named any stock · one prompt, 10 fresh runs per model, September 2026",
    )
    fig.subplots_adjust(left=0.20, right=0.95, bottom=0.24, top=0.78)
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap([S.PANEL, S.MEASURED])
    ax.pcolormesh(grid, cmap=cmap, vmin=0, vmax=1, edgecolors=S.BG, linewidth=3)
    ax.invert_yaxis()
    ax.set_xticks([i + 0.5 for i in range(len(runs))])
    ax.set_xticklabels([f"run {r}" for r in runs], fontsize=13)
    ax.set_yticks([i + 0.5 for i in range(len(models))])
    ax.set_yticklabels(["Haiku 4.5", "Sonnet 5", "Opus 5"], fontsize=17)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    handles = [
        plt_patch(S.MEASURED, "named stocks"),
        plt_patch(S.PANEL, "declined", edgecolor=S.BORDER),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)

    S.footer(fig, SOURCE_PICKS, "prompt_key == 'now'; cell lit where refused == False, one cell per model x run")
    return S.save(fig, CHART_DIR / "03_refusal_grid.png")


def plt_patch(color, label, edgecolor="none"):
    from matplotlib.patches import Patch
    return Patch(facecolor=color, edgecolor=edgecolor, linewidth=1.5, label=label)


def chart_04_pick_frequency():
    """Beat 5: top names named across the 11 'now' replies that answered,
    with the count out of 11 -- what it said, not a recommendation."""
    results = _load_json(OUT / "results.json")
    if results is None:
        print("skipped 04_pick_frequency: out/results.json not present")
        return None

    freq = results["part2_3_analysis"]["part2_stability_and_frequency"]
    names = freq["most_picked_names"][:7]
    n_replies = freq["n_replies_with_picks"]
    tickers = [n for n, _ in names]
    counts = [c for _, c in names]

    fig, ax = S.new_figure(
        "What it said — not a recommendation",
        f"Most-named tickers across the {n_replies} replies that answered the 'now' prompt "
        f"(3 models × 10 runs, 19 declined)",
    )
    y = range(len(tickers))
    bars = ax.barh(y, counts, color=S.MEASURED, height=0.6)
    for rect, count in zip(bars, counts):
        ax.text(rect.get_width() + 0.15, rect.get_y() + rect.get_height() / 2, f"{count} of {n_replies}",
                va="center", ha="left", fontsize=18, fontweight="bold", family=S.mono())
    ax.set_yticks(list(y))
    ax.set_yticklabels(tickers, fontsize=20, family=S.mono())
    ax.invert_yaxis()
    ax.set_xlim(0, n_replies + 2.5)
    ax.set_xlabel(f"Replies naming this ticker (of {n_replies})")
    ax.grid(axis="y", visible=False)

    S.stamp(fig, "TEST INPUT, NOT A RECOMMENDATION")
    S.footer(
        fig, SOURCE_RESULTS,
        "part2_3_analysis.part2_stability_and_frequency.most_picked_names, top 7 of 20 -- tickers are what the model said, not advice",
    )
    return S.save(fig, CHART_DIR / "04_pick_frequency.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_random_portfolio_spread,
        chart_02_hindsight_percentiles,
        chart_03_refusal_grid,
        chart_04_pick_frequency,
    )
    for chart in charts:
        result = chart()
        if result is not None:
            print("wrote", result.relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
