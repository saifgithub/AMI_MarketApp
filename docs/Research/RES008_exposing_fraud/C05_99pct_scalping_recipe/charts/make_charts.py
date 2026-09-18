"""
C05 chart pack -- the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json and out/posthoc_diagnostic.json. Every
number on a chart is read from those files at run time; nothing is typed in.
The two claim lines (80%, 99%) are the claim itself, as advertised -- named
constants, not measurements -- per PREREGISTRATION.md.

Run from the RES008 root:
    .venv/bin/python C05_99pct_scalping_recipe/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

OUT_DIR = CLAIM_DIR / "out"
RESULTS_PATH = OUT_DIR / "results.json"
POSTHOC_PATH = OUT_DIR / "posthoc_diagnostic.json"
SOURCE_RESULTS = "C05_99pct_scalping_recipe/out/results.json"
SOURCE_POSTHOC = "C05_99pct_scalping_recipe/out/posthoc_diagnostic.json"

# The claim as advertised (PREREGISTRATION.md: "wins 80% of the time alone and
# 90-99% with the confirmation") -- not a measurement, so not read from out/.
CLAIM_LOW_PCT = 80.0
CLAIM_HIGH_PCT = 99.0

CELL_ORDER = [
    "V1_strict_60m", "V1_loose_60m", "V2_strict_60m", "V2_loose_60m",
    "V1_strict_5m", "V1_loose_5m", "V2_strict_5m", "V2_loose_5m",
    "V1_strict_daily", "V1_loose_daily", "V2_strict_daily", "V2_loose_daily",
]


def _pct1(value_pct: float) -> str:
    """One decimal, rounded half up, so a chart label matches RESULTS.md (43.59 -> 43.6)."""
    return f"{Decimal(repr(round(float(value_pct), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _r3(value_r: float) -> str:
    """Three decimals for an R-multiple, half up, with a real minus sign."""
    q = Decimal(repr(round(float(value_r), 6))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    s = f"{q:+.3f}".replace("-", "−")
    return s


def _label(cell: str) -> str:
    """Plain-word label for a version code, e.g. V1_loose_60m -> 'target 1.5R · loose filter · hourly'."""
    version, reading, tf = cell.split("_")
    target = "1.5× stop" if version == "V1" else "2× stop"
    tf_word = {"60m": "hourly", "5m": "5-minute", "daily": "daily"}[tf]
    return f"target {target} · {reading} filter · {tf_word}"


def _short_label(cell: str) -> str:
    version, reading, tf = cell.split("_")
    tf_word = {"60m": "hourly", "5m": "5-min", "daily": "daily"}[tf]
    return f"{version} {reading}\n{tf_word}"


def chart_01_win_rate_vs_claim() -> Path:
    """Beat 1/5: measured win rate in each of the 12 versions against the
    advertised 80/99% claim lines and against the breakeven win rate implied
    by where the target and stop sit (1 / (1 + target R))."""
    if not RESULTS_PATH.exists():
        print(f"skipped 01_win_rate_vs_claim: {RESULTS_PATH} not present")
        return None
    results = json.loads(RESULTS_PATH.read_text())
    cells = results["cells"]

    win = [100 * cells[c]["win_rate"]["estimate"] for c in CELL_ORDER]
    lo = [100 * cells[c]["win_rate"]["lower"] for c in CELL_ORDER]
    hi = [100 * cells[c]["win_rate"]["upper"] for c in CELL_ORDER]
    breakeven = [100.0 / (1.0 + cells[c]["target_r"]) for c in CELL_ORDER]
    n_total = sum(cells[c]["n_trades"] for c in CELL_ORDER)
    x = range(len(CELL_ORDER))

    fig, ax = S.new_figure(
        "The ‘99% win rate’ strategy won 43.6% at best, across 9,363 trades",
        f"Win rate in all 12 versions tested · {n_total:,} trades · 7 markets · costs included",
    )
    ax.axhline(CLAIM_HIGH_PCT, color=S.CLAIM, linewidth=2.2, linestyle="--", zorder=2)
    ax.axhline(CLAIM_LOW_PCT, color=S.CLAIM, linewidth=2.2, linestyle="--", zorder=2)
    ax.text(len(CELL_ORDER) - 0.4, CLAIM_HIGH_PCT + 1.6, "claimed 90–99%", color=S.CLAIM,
             fontsize=15, ha="right", va="bottom", fontweight="bold")
    ax.text(len(CELL_ORDER) - 0.4, CLAIM_LOW_PCT - 1.6, "claimed 80%", color=S.CLAIM,
             fontsize=15, ha="right", va="top", fontweight="bold")

    err = [[m - l for m, l in zip(win, lo)], [h - m for h, m in zip(hi, win)]]
    ax.errorbar(x, win, yerr=err, fmt="o", color=S.MEASURED, markersize=13, capsize=7,
                elinewidth=2.8, capthick=2.8, zorder=4, label="Measured win rate (95% interval)")
    ax.plot(x, breakeven, color=S.BENCHMARK, marker="D", markersize=8, linewidth=1.8,
            linestyle=":", zorder=3, label="Breakeven win rate = 1 / (1 + target)")

    for xi, value in zip(x, win):
        ax.text(xi, value - 5.5, _pct1(value), ha="center", va="top", fontsize=13,
                 fontweight="bold", color=S.TEXT, family=S.mono())

    ax.set_ylim(0, 108)
    ax.set_ylabel("Win rate, %")
    ax.set_xticks(list(x))
    ax.set_xticklabels([_short_label(c) for c in CELL_ORDER], fontsize=13)
    ax.set_xlim(-0.6, len(CELL_ORDER) - 0.4)
    ax.legend(loc="center left", bbox_to_anchor=(0.0, 0.62), ncols=1, fontsize=15)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE_RESULTS,
              "cells.*.win_rate.{estimate,lower,upper}, .target_r · claim lines from PREREGISTRATION.md, not measured")
    return S.save(fig, CHART_DIR / "01_win_rate_vs_claim.png")


def chart_02_win_rate_vs_geometry() -> Path:
    """Beat 6 / Short: the 12 win rates plotted against 1 / (1 + target), the
    two horizontal markers at 40% and 33.3% (breakeven for 1.5R and 2R)."""
    if not RESULTS_PATH.exists():
        print(f"skipped 02_win_rate_vs_geometry: {RESULTS_PATH} not present")
        return None
    results = json.loads(RESULTS_PATH.read_text())
    cells = results["cells"]

    win = [100 * cells[c]["win_rate"]["estimate"] for c in CELL_ORDER]
    breakeven_by_target = {1.5: 100.0 / 2.5, 2.0: 100.0 / 3.0}
    x = range(len(CELL_ORDER))

    fig, ax = S.new_figure(
        "The win rate came from the target, not the indicator",
        "Measured win rate against 1 / (1 + target) — what a coin flip wins at this target-to-stop ratio",
    )
    # the two labels sit at different x as well as different y: at 14pt they are wide
    # enough to collide if they are merely stacked.
    label_pos = {1.5: (0.10, 15.0), 2.0: (6.40, 6.0)}
    for target, marker_pct in breakeven_by_target.items():
        label = f"breakeven at target {target:g}× stop = {_pct1(marker_pct)}"
        label_x, label_y = label_pos[target]
        ax.axhline(marker_pct, color=S.BENCHMARK, linewidth=2.0, linestyle="--", zorder=2)
        ax.annotate(label, xy=(label_x, marker_pct), xytext=(label_x, label_y),
                    color=S.MUTED, fontsize=14, ha="left", va="center",
                    arrowprops={"arrowstyle": "-", "color": S.BORDER, "linewidth": 1.4})

    colors = [S.MEASURED if cells[c]["target_r"] == 1.5 else S.CYAN for c in CELL_ORDER]
    ax.scatter(list(x), win, c=colors, s=170, zorder=4, edgecolors=S.TEXT, linewidths=1.2)
    for xi, value in zip(x, win):
        ax.text(xi, value + 3.6, _pct1(value), ha="center", va="bottom", fontsize=13,
                 fontweight="bold", color=S.TEXT, family=S.mono())

    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=S.MEASURED, markeredgecolor=S.TEXT,
               markersize=13, label="target 1.5× stop"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=S.CYAN, markeredgecolor=S.TEXT,
               markersize=13, label="target 2× stop"),
    ]
    ax.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 1.0))

    ax.set_ylim(0, 64)
    ax.set_ylabel("Win rate, %")
    ax.set_xticks(list(x))
    ax.set_xticklabels([_short_label(c) for c in CELL_ORDER], fontsize=13)
    ax.set_xlim(-0.6, len(CELL_ORDER) - 0.4)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE_RESULTS,
              "cells.*.win_rate.estimate, .target_r · breakeven = 100 / (1 + target_r), arithmetic")
    return S.save(fig, CHART_DIR / "02_win_rate_vs_geometry.png")


def chart_03_expectancy_bars() -> Path:
    """Beat 5: net and gross expectancy per trade, in R, with intervals, for
    all 12 versions, zero line."""
    if not RESULTS_PATH.exists():
        print(f"skipped 03_expectancy_bars: {RESULTS_PATH} not present")
        return None
    results = json.loads(RESULTS_PATH.read_text())
    cells = results["cells"]

    net = [cells[c]["expectancy_r"]["net"]["estimate"] for c in CELL_ORDER]
    net_lo = [cells[c]["expectancy_r"]["net"]["lower"] for c in CELL_ORDER]
    net_hi = [cells[c]["expectancy_r"]["net"]["upper"] for c in CELL_ORDER]
    gross = [cells[c]["expectancy_r"]["gross"]["estimate"] for c in CELL_ORDER]
    gross_lo = [cells[c]["expectancy_r"]["gross"]["lower"] for c in CELL_ORDER]
    gross_hi = [cells[c]["expectancy_r"]["gross"]["upper"] for c in CELL_ORDER]
    x = range(len(CELL_ORDER))

    fig, (top, bottom) = S.new_figure(
        "After costs, every version lost money on average",
        "Expectancy per trade, in R (profit ÷ stop distance) · 95% interval · 12 versions",
        nrows=2, sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.34},
    )
    # top=0.74 keeps the upper panel clear of the subtitle; the generous hspace plus
    # pruned end ticks stop the two panels' tick labels from meeting in the middle.
    fig.subplots_adjust(left=0.16, top=0.74, bottom=0.22)

    top.axhline(0, color=S.TEXT, linewidth=1.6)
    net_err = [[n - l for n, l in zip(net, net_lo)], [h - n for h, n in zip(net_hi, net)]]
    net_colors = [S.BAD if h < 0 else S.BENCHMARK for h in net_hi]
    for xi, value, lower, upper, color in zip(x, net, net_err[0], net_err[1], net_colors):
        top.errorbar(xi, value, yerr=[[lower], [upper]], fmt="o", color=color, markersize=12,
                     capsize=7, elinewidth=2.8, capthick=2.8)
    top.set_ylabel("Net, R per trade")
    top.locator_params(axis="y", nbins=5)
    top.yaxis.get_major_locator().set_params(prune="lower")
    top.grid(axis="x", visible=False)

    bottom.axhline(0, color=S.TEXT, linewidth=1.6)
    gross_err = [[n - l for n, l in zip(gross, gross_lo)], [h - n for h, n in zip(gross_hi, gross)]]
    gross_colors = [S.GOOD if l > 0 else (S.BAD if h < 0 else S.BENCHMARK) for l, h in zip(gross_lo, gross_hi)]
    for xi, value, lower, upper, color in zip(x, gross, gross_err[0], gross_err[1], gross_colors):
        bottom.errorbar(xi, value, yerr=[[lower], [upper]], fmt="o", color=color, markersize=12,
                        capsize=7, elinewidth=2.8, capthick=2.8)
    bottom.set_ylabel("Gross, R per trade\n(before costs)")
    bottom.locator_params(axis="y", nbins=5)
    bottom.yaxis.get_major_locator().set_params(prune="upper")
    bottom.set_xticks(list(x))
    bottom.set_xticklabels([_short_label(c) for c in CELL_ORDER], fontsize=13)
    bottom.grid(axis="x", visible=False)

    S.footer(fig, SOURCE_RESULTS,
              "cells.*.expectancy_r.{net,gross}.{estimate,lower,upper} · red = interval entirely below zero, green = entirely above")
    return S.save(fig, CHART_DIR / "03_expectancy_bars.png")


def chart_04_cost_in_r() -> Path:
    """Beats 5, 7: the recipe's cost per trade in R by timeframe (pre-registered),
    with the placebo's cost in R added and stamped after-the-fact (beat 7's point
    that a fixed-% cost divided by a tiny stop inflates R-cost for narrow stops)."""
    if not RESULTS_PATH.exists():
        print(f"skipped 04_cost_in_r: {RESULTS_PATH} not present")
        return None
    results = json.loads(RESULTS_PATH.read_text())
    cells = results["cells"]

    tf_order = ["daily", "60m", "5m"]
    tf_word = {"daily": "daily", "60m": "hourly", "5m": "5-minute"}
    # Pool recipe cost/trade (in R) across the 4 versions sharing a timeframe,
    # weighted by n_trades -- matches RESULTS.md §2/§3's 0.02 / 0.09 / 0.52 figures.
    recipe_cost = {}
    for tf in tf_order:
        matching = [c for c in CELL_ORDER if c.endswith(f"_{tf}")]
        total_n = sum(cells[c]["n_trades"] for c in matching)
        recipe_cost[tf] = sum(cells[c]["avg_cost_r"] * cells[c]["n_trades"] for c in matching) / total_n

    have_posthoc = POSTHOC_PATH.exists()
    placebo_cost = {}
    if have_posthoc:
        posthoc = json.loads(POSTHOC_PATH.read_text())
        pcells = posthoc["cells"]
        for tf in tf_order:
            matching = [c for c in CELL_ORDER if c.endswith(f"_{tf}")]
            total_n = sum(pcells[c]["n_trades"] for c in matching)
            placebo_cost[tf] = sum(pcells[c]["avg_cost_r"]["placebo_p50"] * pcells[c]["n_trades"] for c in matching) / total_n

    fig, ax = S.new_figure(
        "A fixed-percent cost is a small bite in R with a wide stop, a huge one with a narrow stop",
        "Cost per trade, in R (fixed % cost ÷ each trade's own stop distance) · pooled across versions sharing a timeframe",
    )
    width = 0.32 if have_posthoc else 0.5
    x = range(len(tf_order))
    recipe_vals = [recipe_cost[tf] for tf in tf_order]
    offset = width / 2 if have_posthoc else 0
    bars = ax.bar([xi - offset for xi in x], recipe_vals, width=width, color=S.MEASURED, label="Recipe's own stop")
    for rect, value in zip(bars, recipe_vals):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.06, f"{value:.2f} R", ha="center", va="bottom",
                fontsize=15, fontweight="bold", family=S.mono(), color=S.TEXT)

    if have_posthoc:
        placebo_vals = [placebo_cost[tf] for tf in tf_order]
        bars2 = ax.bar([xi + offset for xi in x], placebo_vals, width=width, color=S.BENCHMARK,
                       label="Random entry's own stop (after the fact)")
        for rect, value in zip(bars2, placebo_vals):
            ax.text(rect.get_x() + rect.get_width() / 2, value + 0.06, f"{value:.2f} R", ha="center", va="bottom",
                    fontsize=15, fontweight="bold", family=S.mono(), color=S.TEXT)
        S.stamp(fig, "PLACEBO COST BARS: AFTER THE FACT — NOT PRE-REGISTERED")

    ax.set_xticks(list(x))
    ax.set_xticklabels([tf_word[tf] for tf in tf_order])
    ax.set_ylabel("Cost per trade, R")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)

    note = "cells.*.avg_cost_r, n_trades, pooled by timeframe"
    if have_posthoc:
        note += " · placebo bars: out/posthoc_diagnostic.json cells.*.avg_cost_r.placebo_p50"
        S.footer(fig, "C05_99pct_scalping_recipe/out/", note)
    else:
        S.footer(fig, SOURCE_RESULTS, note)
    return S.save(fig, CHART_DIR / "04_cost_in_r.png")


def chart_05_long_vs_short() -> Path:
    """Beat 7: long vs short net % per trade, pooled over instruments, for the
    8 hourly and daily cells (RESULTS.md §5) -- after-the-fact, stamped."""
    if not POSTHOC_PATH.exists():
        print(f"skipped 05_long_vs_short: {POSTHOC_PATH} not present")
        return None
    posthoc = json.loads(POSTHOC_PATH.read_text())
    pcells = posthoc["cells"]

    cells_shown = [c for c in CELL_ORDER if c.endswith("_60m") or c.endswith("_daily")]
    long_pct, short_pct = [], []
    for c in cells_shown:
        by_side = pcells[c]["by_side_instrument"]
        long_n = sum(v["long"]["n"] for v in by_side.values())
        short_n = sum(v["short"]["n"] for v in by_side.values())
        long_pct.append(100 * sum(v["long"]["n"] * v["long"]["net_pct"] for v in by_side.values()) / long_n)
        short_pct.append(100 * sum(v["short"]["n"] * v["short"]["net_pct"] for v in by_side.values()) / short_n)

    x = range(len(cells_shown))
    width = 0.38

    fig, ax = S.new_figure(
        "The short side of the recipe lost money in every version tested",
        "Net % per trade by direction, pooled over 7 markets — all seven rose over the sample",
    )
    bars_l = ax.bar([xi - width / 2 for xi in x], long_pct, width=width, color=S.GOOD, label="Long trades")
    bars_s = ax.bar([xi + width / 2 for xi in x], short_pct, width=width, color=S.BAD, label="Short trades")
    for rect, value in zip(bars_l, long_pct):
        ax.text(rect.get_x() + rect.get_width() / 2, value + (0.06 if value >= 0 else -0.06), f"{value:+.2f}%".replace("-", "\u2212"),
                ha="center", va="bottom" if value >= 0 else "top", fontsize=12, fontweight="bold", family=S.mono())
    for rect, value in zip(bars_s, short_pct):
        ax.text(rect.get_x() + rect.get_width() / 2, value + (0.06 if value >= 0 else -0.06), f"{value:+.2f}%".replace("-", "\u2212"),
                ha="center", va="bottom" if value >= 0 else "top", fontsize=12, fontweight="bold", family=S.mono())

    ax.axhline(0, color=S.TEXT, linewidth=1.6)
    ax.set_ylabel("Net % per trade")
    ax.set_xticks(list(x))
    ax.set_xticklabels([_short_label(c) for c in cells_shown], fontsize=13)
    ax.set_ylim(top=max(long_pct) * 1.28)
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)

    S.stamp(fig, "AFTER THE FACT — NOT PRE-REGISTERED")
    S.footer(fig, SOURCE_POSTHOC,
              "cells.*.by_side_instrument.*.{long,short}.{n,net_pct}, pooled by n · hourly + daily cells only")
    return S.save(fig, CHART_DIR / "05_long_vs_short.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_win_rate_vs_claim,
        chart_02_win_rate_vs_geometry,
        chart_03_expectancy_bars,
        chart_04_cost_in_r,
        chart_05_long_vs_short,
    )
    for chart in charts:
        result = chart()
        if result is not None:
            print("wrote", result.relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
