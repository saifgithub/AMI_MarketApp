"""
C04 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json. Every number on a chart is read from
that file at run time; nothing is typed in.

Run from the RES008 root:
    .venv/bin/python C04_win_rate_proves_edge/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

RESULTS = json.loads((CLAIM_DIR / "out" / "results.json").read_text())
GEOMETRIES = list(RESULTS["part1_pooled_by_geometry"].keys())
SOURCE = "C04_win_rate_proves_edge/out/results.json"


def _pct1(value_pct: float) -> str:
    """One decimal, rounded half up, so a chart label matches RESULTS.md (84.25 -> 84.3)."""
    from decimal import ROUND_HALF_UP, Decimal
    return f"{Decimal(repr(round(float(value_pct), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _label(geometry: str) -> str:
    t, s = geometry.split(":")
    return f"target {t} : stop {s}"


def chart_01_win_rate_dial() -> Path:
    """Beat 5: win rate per target:stop setting against stop / (target + stop);
    below it, net expectancy per trade with its interval and a zero line."""
    pooled = RESULTS["part1_pooled_by_geometry"]
    win = [100 * pooled[g]["win_rate"]["estimate"] for g in GEOMETRIES]
    ref = [100 * pooled[g]["random_walk_reference_win_rate"] for g in GEOMETRIES]
    net = [100 * pooled[g]["expectancy_pct"]["net"]["estimate"] for g in GEOMETRIES]
    lo = [100 * pooled[g]["expectancy_pct"]["net"]["lower"] for g in GEOMETRIES]
    hi = [100 * pooled[g]["expectancy_pct"]["net"]["upper"] for g in GEOMETRIES]
    n_trades = pooled[GEOMETRIES[0]]["n_trades"]
    x = range(len(GEOMETRIES))

    fig, (top, bottom) = S.new_figure(
        "Same coin-flip entries. Seven places to put the target and the stop.",
        f"Random entries, random direction · {n_trades:,} trades per setting · 27 markets · costs included",
        nrows=2,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12},
    )

    bars = top.bar(x, win, color=S.MEASURED, width=0.62, label="Measured win rate")
    top.plot(x, ref, color=S.CLAIM, marker="o", markersize=11, linewidth=2.5, label="stop ÷ (target + stop)")
    for rect, value, reference in zip(bars, win, ref):
        top.text(rect.get_x() + rect.get_width() / 2, max(value, reference) + 3.5, _pct1(value), ha="center",
                 va="bottom", fontsize=22, fontweight="bold", family=S.mono())
    top.set_ylim(0, 112)
    top.set_ylabel("Win rate, %")
    top.legend(loc="upper right")
    top.grid(axis="x", visible=False)

    err = [[n - l for n, l in zip(net, lo)], [h - n for n, h in zip(net, hi)]]
    colors = [S.BAD if h < 0 else S.BENCHMARK for h in hi]
    bottom.axhline(0, color=S.TEXT, linewidth=1.6)
    for xi, value, lower, upper, color in zip(x, net, err[0], err[1], colors):
        bottom.errorbar(xi, value, yerr=[[lower], [upper]], fmt="o", color=color, markersize=12, capsize=8,
                        elinewidth=3, capthick=3)
    bottom.set_ylabel("Net per trade,\n% of price")
    bottom.set_xticks(list(x))
    bottom.set_xticklabels([f"target {g.split(':')[0]} : stop {g.split(':')[1]}" for g in GEOMETRIES], fontsize=16)
    bottom.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "red = 95% interval entirely below zero")
    return S.save(fig, CHART_DIR / "01_win_rate_dial.png")


def chart_02_brackets_to_scale() -> Path:
    """Beat 4: the seven target/stop brackets side by side, drawn to scale in
    multiples of s. One column per setting so brackets that share a target or a
    stop distance do not hide each other."""
    pooled = RESULTS["part1_pooled_by_geometry"]
    fig, ax = S.new_figure(
        "Seven places to put the target and the stop, drawn to scale",
        "Distances from the entry price, in multiples of each market's own typical daily range, s",
    )
    width = 0.46
    for xi, geometry in enumerate(GEOMETRIES):
        target = pooled[geometry]["target_mult"]
        stop = pooled[geometry]["stop_mult"]
        ax.bar(xi, target, width=width, color=S.GOOD, alpha=0.85, zorder=3)
        ax.bar(xi, -stop, width=width, color=S.BAD, alpha=0.85, zorder=3)
        ax.text(xi, target + 0.18, f"+{target:g} s", ha="center", va="bottom", fontsize=20, fontweight="bold",
                color=S.GOOD, family=S.mono())
        ax.text(xi, -stop - 0.18, f"\u2212{stop:g} s", ha="center", va="top", fontsize=20, fontweight="bold",
                color=S.BAD, family=S.mono())
    ax.axhline(0, color=S.TEXT, linewidth=2.0, zorder=4)
    ax.text(len(GEOMETRIES) - 0.62, 0.12, "entry", ha="left", va="bottom", fontsize=16, color=S.TEXT)
    ax.set_xticks(range(len(GEOMETRIES)))
    ax.set_xticklabels([f"target {g.split(':')[0]}\nstop {g.split(':')[1]}" for g in GEOMETRIES], fontsize=17)
    ax.set_xlim(-0.6, len(GEOMETRIES) - 0.1)
    ax.set_ylim(-6.2, 6.2)
    ax.set_ylabel("Distance from entry, in s")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "green = profit target, red = stop-loss · sizes from part1_pooled_by_geometry target_mult / stop_mult")
    return S.save(fig, CHART_DIR / "02_brackets_to_scale.png")


def chart_03_wilson_intervals() -> Path:
    """Beat 7: Wilson 95% intervals for the four sample sizes quoted in the videos read."""
    wilson = RESULTS["part2_analytic"]["wilson_intervals"]
    order = ["2/2", "9/12", "22/25", "31/47"]
    est = [100 * wilson[k]["estimate"] for k in order]
    lo = [100 * wilson[k]["lower"] for k in order]
    hi = [100 * wilson[k]["upper"] for k in order]
    y = range(len(order))

    fig, ax = S.new_figure(
        "A quoted win rate is a range, not a point",
        "95% Wilson interval for each sample size of the kind shown in the videos we reviewed",
    )
    fig.subplots_adjust(left=0.22)
    for yi, e, l, h in zip(y, est, lo, hi):
        ax.plot([l, h], [yi, yi], color=S.MEASURED, linewidth=6, solid_capstyle="round", zorder=2)
        ax.scatter([e], [yi], color=S.TEXT, s=140, zorder=3)
        ax.text(h + 2.5, yi, f"{e:.0f}%  ({l:.0f}–{h:.0f})", color=S.TEXT, fontsize=18, va="center", family=S.mono())
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{k.replace('/', ' of ')} trades" for k in order])
    ax.set_xlim(0, 118)
    ax.set_xlabel("Win rate, %")
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)

    S.footer(fig, SOURCE, "part2_analytic.wilson_intervals — arithmetic on the sample sizes shown, not new trades")
    return S.save(fig, CHART_DIR / "03_wilson_intervals.png")


def chart_04_best_of_k_grid() -> Path:
    """Beat 7: probability the best of k tries shows >= 22 of 25 wins, by true win rate."""
    grid = RESULTS["part2_analytic"]["p_best_of_k_reaches_22_of_25"]
    ks = ["1", "5", "20"]
    rates = ["0.5", "0.6", "0.7"]
    data = np.array([[100 * grid[k][r] for r in rates] for k in ks])

    fig, ax = S.new_figure(
        "Try enough versions, and the best one looks like skill",
        "Probability the best of k tries shows 22 or more wins in 25, if the true win rate is r",
    )
    fig.subplots_adjust(left=0.24)
    from matplotlib.colors import LinearSegmentedColormap

    ami_seq = LinearSegmentedColormap.from_list("ami_seq", [S.PANEL, S.CARD, S.BLUE])
    im = ax.imshow(data, cmap=ami_seq, vmin=0, vmax=data.max(), aspect="auto")
    ax.set_xticks(range(len(rates)))
    ax.set_xticklabels([f"true win rate {float(r) * 100:.0f}%" for r in rates])
    ax.set_yticks(range(len(ks)))
    ax.set_yticklabels([f"{k} version{'s' if k != '1' else ''} tried" for k in ks])
    ax.grid(False)
    for i, k in enumerate(ks):
        for j, r in enumerate(rates):
            highlight = (k == "20" and r == "0.7")
            value = data[i, j]
            color = S.TEXT
            ax.text(j, i, _pct1(value), ha="center", va="center", fontsize=22 if highlight else 19,
                     fontweight="bold" if highlight else "normal", color=color)
            if highlight:
                ax.add_patch(plt_rect(j, i))
    S.footer(fig, SOURCE, "part2_analytic.p_best_of_k_reaches_22_of_25 — arithmetic, no data; highlighted cell in beat 7")
    return S.save(fig, CHART_DIR / "04_best_of_k_grid.png")


def plt_rect(j: int, i: int):
    from matplotlib.patches import Rectangle
    return Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=S.CLAIM, linewidth=4)


def _dial_frame(geometry: str, filename: str) -> Path:
    """One key frame of the WIN RATE dial: needle at this geometry's measured win rate."""
    pooled = RESULTS["part1_pooled_by_geometry"]
    g = pooled[geometry]
    win_pct = 100 * g["win_rate"]["estimate"]
    ref_pct = 100 * g["random_walk_reference_win_rate"]

    fig, ax = S.new_figure(
        "Win rate",
        f"{_label(geometry)} · random entries · {g['n_trades']:,} trades",
    )
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.15, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")

    theta = np.linspace(np.pi, 0, 200)
    ax.plot(np.cos(theta), np.sin(theta), color=S.BORDER, linewidth=22, solid_capstyle="butt", zorder=1)

    # 0% sits at the left end of the arc (theta = pi) and 100% at the right (theta = 0),
    # so a value v maps to theta = pi * (1 - v). One colour for every dial: the fill is
    # a measurement, not a judgement.
    frac = win_pct / 100.0
    theta_fill = np.linspace(np.pi, np.pi * (1 - frac), 120)
    ax.plot(np.cos(theta_fill), np.sin(theta_fill), color=S.MEASURED, linewidth=22, solid_capstyle="butt", zorder=2)

    # Needle is short and stays inside the dial (upper half-plane, y >= 0); all
    # text sits below the diameter line (y < 0) so nothing can cross it.
    needle_theta = np.pi * (1 - frac)
    ax.plot([0, 0.62 * np.cos(needle_theta)], [0, 0.62 * np.sin(needle_theta)], color=S.TEXT, linewidth=5, zorder=4)
    ax.scatter([0], [0], color=S.TEXT, s=180, zorder=5)

    ref_theta = np.pi * (1 - ref_pct / 100.0)
    ax.plot([1.05 * np.cos(ref_theta), 1.18 * np.cos(ref_theta)], [1.05 * np.sin(ref_theta), 1.18 * np.sin(ref_theta)],
             color=S.CLAIM, linewidth=4)

    ax.text(-1.05, -0.05, "0%", color=S.MUTED, fontsize=18, ha="center", va="top")
    ax.text(1.05, -0.05, "100%", color=S.MUTED, fontsize=18, ha="center", va="top")
    # S.big_number always draws in axes-fraction coordinates; convert this data
    # point to a fraction of the (-1.15, 1.2) y-range set above.
    y0, y1 = -1.15, 1.2
    to_frac = lambda y: (y - y0) / (y1 - y0)
    S.big_number(ax, 0.5, to_frac(-0.35), _pct1(win_pct), color=S.TEXT, size=76, ha="center", va="center")
    ax.text(0, -0.66, "WIN RATE", color=S.MUTED, fontsize=22, fontweight="bold", ha="center", va="center",
            family=S.mono())
    ax.text(0, -0.85, f"reference: stop ÷ (target + stop) = {_pct1(ref_pct)}", color=S.MUTED, fontsize=15,
            ha="center", va="center")

    S.footer(fig, SOURCE, "needle position = part1_pooled_by_geometry win_rate.estimate")
    return S.save(fig, CHART_DIR / filename)


def chart_05a_dial_low_target() -> Path:
    """Beat 1/5/thumbnail: dial key frame at the 0.5:5 setting (89.2% wins)."""
    return _dial_frame("0.5:5", "05a_dial_0.5_5.png")


def chart_05b_dial_even() -> Path:
    """Beat 5: dial key frame at the 1:1 setting (49.3% wins)."""
    return _dial_frame("1:1", "05b_dial_1_1.png")


def chart_05c_dial_high_target() -> Path:
    """Beat 1/5: dial key frame at the 5:1 setting (18.9% wins)."""
    return _dial_frame("5:1", "05c_dial_5_1.png")


def chart_06_crypto_table() -> Path:
    """Beat 8: the crypto asset-class win rate + net expectancy, stamped as descriptive."""
    by_class = RESULTS["part1_by_asset_class_by_geometry"]
    geometries = ["0.5:5", "1:1", "3:1", "5:1"]
    win = [100 * by_class[g]["crypto"]["win_rate"]["estimate"] for g in geometries]
    net = [100 * by_class[g]["crypto"]["expectancy_pct"]["net"]["estimate"] for g in geometries]
    lo = [100 * by_class[g]["crypto"]["expectancy_pct"]["net"]["lower"] for g in geometries]
    hi = [100 * by_class[g]["crypto"]["expectancy_pct"]["net"]["upper"] for g in geometries]
    n_trades = by_class[geometries[0]]["crypto"]["n_trades"]
    x = range(len(geometries))

    fig, (top, bottom) = S.new_figure(
        "In two cryptocurrencies, the pattern ran backwards",
        f"Random entries · {n_trades:,} trades per setting · 2 coins, one history · descriptive, not a strategy",
        nrows=2,
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.15},
    )
    bars = top.bar(x, win, color=S.MEASURED, width=0.55)
    for rect, value in zip(bars, win):
        top.text(rect.get_x() + rect.get_width() / 2, value + 3, _pct1(value), ha="center", va="bottom",
                  fontsize=20, fontweight="bold", family=S.mono())
    top.set_ylabel("Win rate, %")
    top.set_ylim(0, 105)
    top.grid(axis="x", visible=False)

    colors = [S.GOOD if l > 0 else (S.BAD if h < 0 else S.BENCHMARK) for l, h in zip(lo, hi)]
    bottom.axhline(0, color=S.TEXT, linewidth=1.6)
    err = [[n - l for n, l in zip(net, lo)], [h - n for n, h in zip(net, hi)]]
    for xi, value, lower, upper, color in zip(x, net, err[0], err[1], colors):
        bottom.errorbar(xi, value, yerr=[[lower], [upper]], fmt="o", color=color, markersize=13, capsize=9,
                         elinewidth=3, capthick=3)
    bottom.set_ylabel("Net per trade,\n% of price")
    bottom.set_xticks(list(x))
    bottom.set_xticklabels([_label(g) for g in geometries])
    bottom.grid(axis="x", visible=False)

    S.stamp(fig, "NOT A PRE-REGISTERED TEST — 2 COINS, ONE HISTORY")
    S.footer(fig, SOURCE, "part1_by_asset_class_by_geometry.*.crypto — descriptive only, not a strategy")
    return S.save(fig, CHART_DIR / "06_crypto_asset_class.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_win_rate_dial,
        chart_02_brackets_to_scale,
        chart_03_wilson_intervals,
        chart_04_best_of_k_grid,
        chart_05a_dial_low_target,
        chart_05b_dial_even,
        chart_05c_dial_high_target,
        chart_06_crypto_table,
    )
    for chart in charts:
        print("wrote", chart().relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
