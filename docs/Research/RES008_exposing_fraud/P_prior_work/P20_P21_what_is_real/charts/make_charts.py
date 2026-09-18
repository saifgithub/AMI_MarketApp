"""
P20/P21 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from the two source studies' out/results.json. Every number on a
chart is read from those files at run time; nothing is typed in.

Source studies (read-only, never modified):
    RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json
    RES001_finding_the_edge/04_gamma_transition_dispersion/out/results.json

Run from the RES008 root:
    .venv/bin/python P_prior_work/P20_P21_what_is_real/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.lines as mlines
from matplotlib.patches import Patch

CHART_DIR = Path(__file__).resolve().parent
ROOT = CHART_DIR.parents[2]  # RES008_exposing_fraud
sys.path.insert(0, str(ROOT))

from common import ami_style as S  # noqa: E402

SRC_ROOT = ROOT.parent / "RES001_finding_the_edge"
VOL_JSON = SRC_ROOT / "03_volatility_regime_sizing" / "out" / "results.json"
DISP_JSON = SRC_ROOT / "04_gamma_transition_dispersion" / "out" / "results.json"

SRC_VOL = "RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json"
SRC_DISP = "RES001_finding_the_edge/04_gamma_transition_dispersion/out/results.json"

HORIZONS = ["5", "10", "21"]
HORIZON_LABEL = {"5": "next 5 days", "10": "next 10 days", "21": "next 21 days (about a month)"}
DEF_LABEL = "2005–2018"
HOLD_LABEL = "2019–2026"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace("-", "−")


def chart_01_test_a_bars() -> Path | None:
    """Beats 1, 5, Short: Test A — stressed / calm forward volatility ratio, six
    bars (3 horizons x 2 periods), reference line at 1.0."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 01_test_a_forward_volatility: {VOL_JSON} not present")
        return None

    est_def = [data["definition"]["AB"][h]["A_vol_ratio"] for h in HORIZONS]
    lo_def = [data["definition"]["AB"][h]["A_ci"][0] for h in HORIZONS]
    hi_def = [data["definition"]["AB"][h]["A_ci"][1] for h in HORIZONS]
    est_hold = [data["holdout"]["AB"][h]["A_vol_ratio"] for h in HORIZONS]
    lo_hold = [data["holdout"]["AB"][h]["A_ci"][0] for h in HORIZONS]
    hi_hold = [data["holdout"]["AB"][h]["A_ci"][1] for h in HORIZONS]

    import numpy as np

    fig, ax = S.new_figure(
        "After a stressed day, the market moves about twice as much",
        "Forward volatility, stressed ÷ calm — 95% interval — reference line at 1.0 (no difference)",
    )
    x = np.arange(len(HORIZONS))
    width = 0.32
    for offset, est, lo, hi, color in (
        (-width / 2, est_def, lo_def, hi_def, S.CYAN),
        (width / 2, est_hold, lo_hold, hi_hold, S.PURPLE),
    ):
        xi = x + offset
        err = [[e - l for e, l in zip(est, lo)], [h - e for e, h in zip(est, hi)]]
        ax.bar(xi, est, width=width, color=color, alpha=0.9, zorder=3)
        ax.errorbar(xi, est, yerr=err, fmt="none", ecolor=S.TEXT, elinewidth=2.5, capsize=8, capthick=2.5, zorder=4)
        for xv, e, h in zip(xi, est, hi):
            ax.text(xv, h + 0.10, _fmt(e) + "×", ha="center", va="bottom", fontsize=17, fontweight="bold",
                     color=S.TEXT, family=S.mono())

    ax.axhline(1.0, color=S.BENCHMARK, linewidth=2.2, linestyle="--", zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([HORIZON_LABEL[h] for h in HORIZONS])
    ax.set_ylabel("Stressed ÷ calm\nforward volatility")
    ax.set_ylim(0, max(hi_def + hi_hold) * 1.42)
    ax.set_xlim(x[0] - 0.6, x[-1] + 0.9)
    ax.grid(axis="x", visible=False)
    handles = [
        Patch(color=S.CYAN, label=f"Definition period, {DEF_LABEL}"),
        Patch(color=S.PURPLE, label=f"Holdout period, {HOLD_LABEL}"),
        mlines.Line2D([0], [0], color=S.BENCHMARK, linewidth=2.2, linestyle="--", label="1.0 = no difference"),
    ]
    ax.legend(handles=handles, loc="upper right")

    S.footer(fig, SRC_VOL, "definition.AB / holdout.AB — A_vol_ratio and A_ci per horizon")
    return S.save(fig, CHART_DIR / "01_test_a_forward_volatility.png")


def chart_02_test_b_dots() -> Path | None:
    """Beats 5, 7: Test B — forward direction, stressed minus calm, six dots
    around zero, two periods in two colours, the excluded-zero cell ringed."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 02_test_b_forward_direction: {VOL_JSON} not present")
        return None

    fig, ax = S.new_figure(
        "Which way? Mostly nothing",
        "Forward return, stressed minus calm — 95% interval — the sign flips between the periods",
    )
    fig.subplots_adjust(left=0.22)
    rows = []
    for h in HORIZONS:
        d = data["definition"]["AB"][h]
        rows.append((f"{HORIZON_LABEL[h]}\n{DEF_LABEL}", d["B_ret_diff"], d["B_ci"][0], d["B_ci"][1], S.CYAN))
    for h in HORIZONS:
        d = data["holdout"]["AB"][h]
        rows.append((f"{HORIZON_LABEL[h]}\n{HOLD_LABEL}", d["B_ret_diff"], d["B_ci"][0], d["B_ci"][1], S.PURPLE))

    y = list(range(len(rows)))
    for yi, (_, est, lo, hi, color) in zip(y, rows):
        excludes_zero = lo > 0 or hi < 0
        ax.plot([100 * lo, 100 * hi], [yi, yi], color=color, linewidth=6, solid_capstyle="round", zorder=2)
        ax.scatter([100 * est], [yi], color=S.TEXT, s=150, zorder=3)
        label = f"{100 * est:+.2f}%".replace("-", "\u2212")
        ax.text(100 * hi + 0.30, yi, label, color=S.TEXT, fontsize=16, va="center", family=S.mono())
        if excludes_zero:
            ax.scatter([100 * est], [yi], s=520, facecolors="none", edgecolors=S.CLAIM, linewidths=3, zorder=4)

    ax.axvline(0, color=S.BENCHMARK, linewidth=2.2, linestyle="--", zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=15)
    ax.invert_yaxis()
    ax.set_xlabel("Forward return, stressed minus calm, %")
    xs = [100 * r[2] for r in rows] + [100 * r[3] for r in rows]
    ax.set_xlim(min(xs) - 0.6, max(xs) + 1.5)
    ax.grid(axis="y", visible=False)
    handles = [
        mlines.Line2D([0], [0], color=S.CYAN, linewidth=6, label=f"Definition, {DEF_LABEL}"),
        mlines.Line2D([0], [0], color=S.PURPLE, linewidth=6, label=f"Holdout, {HOLD_LABEL}"),
    ]
    ax.legend(handles=handles, loc="upper right")

    S.stamp(fig, "RECORDED DEVIATION — ONE CELL")
    S.footer(
        fig, SRC_VOL,
        "definition.AB / holdout.AB — B_ret_diff and B_ci per horizon; ringed cell: holdout, next 21 days",
    )
    return S.save(fig, CHART_DIR / "02_test_b_forward_direction.png")


def chart_03_test_c_variance() -> Path | None:
    """Beat 5: Test C — variance of regime-scaled sizing vs a shuffled placebo,
    six bars below a line at 1.0."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 03_test_c_variance_ratio: {VOL_JSON} not present")
        return None

    est_def = [data["definition"]["C"][h]["C_var_ratio_scaled_vs_shuffled"] for h in HORIZONS]
    lo_def = [data["definition"]["C"][h]["C_ci"][0] for h in HORIZONS]
    hi_def = [data["definition"]["C"][h]["C_ci"][1] for h in HORIZONS]
    est_hold = [data["holdout"]["C"][h]["C_var_ratio_scaled_vs_shuffled"] for h in HORIZONS]
    lo_hold = [data["holdout"]["C"][h]["C_ci"][0] for h in HORIZONS]
    hi_hold = [data["holdout"]["C"][h]["C_ci"][1] for h in HORIZONS]

    import numpy as np

    fig, ax = S.new_figure(
        "Knowing the regime cuts variance more than sizing at random",
        "Variance of per-trade result, regime-scaled ÷ shuffled placebo — 95% interval — line at 1.0 (no gain over random)",
    )
    x = np.arange(len(HORIZONS))
    width = 0.32
    for offset, est, lo, hi, color in (
        (-width / 2, est_def, lo_def, hi_def, S.CYAN),
        (width / 2, est_hold, lo_hold, hi_hold, S.PURPLE),
    ):
        xi = x + offset
        err = [[e - l for e, l in zip(est, lo)], [h - e for e, h in zip(est, hi)]]
        ax.bar(xi, est, width=width, color=color, alpha=0.9, zorder=3)
        ax.errorbar(xi, est, yerr=err, fmt="none", ecolor=S.TEXT, elinewidth=2.5, capsize=8, capthick=2.5, zorder=4)
        for xv, e, h in zip(xi, est, hi):
            ax.text(xv, h + 0.045, _fmt(e), ha="center", va="bottom", fontsize=17, fontweight="bold", color=S.TEXT,
                     family=S.mono())

    ax.axhline(1.0, color=S.BENCHMARK, linewidth=2.2, linestyle="--", zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([HORIZON_LABEL[h] for h in HORIZONS])
    ax.set_ylabel("Variance ratio,\nscaled ÷ shuffled")
    ax.set_ylim(0, 1.55)
    ax.set_xlim(x[0] - 0.6, x[-1] + 0.9)
    ax.grid(axis="x", visible=False)
    handles = [
        Patch(color=S.CYAN, label=f"Definition period, {DEF_LABEL}"),
        Patch(color=S.PURPLE, label=f"Holdout period, {HOLD_LABEL}"),
        mlines.Line2D([0], [0], color=S.BENCHMARK, linewidth=2.2, linestyle="--", label="1.0 = no gain over random"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0))

    S.footer(fig, SRC_VOL, "definition.C / holdout.C — C_var_ratio_scaled_vs_shuffled and C_ci per horizon")
    return S.save(fig, CHART_DIR / "03_test_c_variance_ratio.png")


def chart_04_cost_pair() -> Path | None:
    """Beat 6: the cost — mean per trade (constant / scaled / shuffled) and
    excess kurtosis (constant / scaled), holdout h=21 (both windows for kurtosis)."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 04_cost_pair: {VOL_JSON} not present")
        return None

    hold21 = data["holdout"]["C"]["21"]
    def21 = data["definition"]["C"]["21"]

    fig, (left, right) = S.new_figure(
        "It isn't free, and one tail got worse",
        "Holdout period, 2019–2026, next 21 days (about a month)",
        ncols=2,
    )
    fig.subplots_adjust(top=0.70, wspace=0.32)

    mean_labels = ["Constant\nsizing", "Regime-\nscaled", "Shuffled\nplacebo"]
    mean_vals = [100 * hold21["mean_const"], 100 * hold21["mean_scaled"], 100 * hold21["mean_shuffled"]]
    mean_colors = [S.BENCHMARK, S.BAD, S.MEASURED]
    xb = range(len(mean_labels))
    bars = left.bar(xb, mean_vals, color=mean_colors, width=0.6, zorder=3)
    for xi, v in zip(xb, mean_vals):
        left.text(xi, v + 0.02, f"{v:.2f}%", ha="center", va="bottom", fontsize=17, fontweight="bold",
                   color=S.TEXT, family=S.mono())
    left.set_xticks(list(xb))
    left.set_xticklabels(mean_labels, fontsize=15)
    left.set_ylabel("Mean result per trade, %")
    left.set_ylim(0, max(mean_vals) * 1.35)
    left.grid(axis="x", visible=False)
    left.set_title("Average result per trade fell", fontsize=19, color=S.MUTED, pad=12)

    kurt_labels = [f"Definition\n{DEF_LABEL}", f"Holdout\n{HOLD_LABEL}"]
    kurt_const = [def21["kurt_const"], hold21["kurt_const"]]
    kurt_scaled = [def21["kurt_scaled"], hold21["kurt_scaled"]]
    xk = list(range(len(kurt_labels)))
    width = 0.32
    right.bar([v - width / 2 for v in xk], kurt_const, width=width, color=S.BENCHMARK, label="Constant sizing", zorder=3)
    right.bar([v + width / 2 for v in xk], kurt_scaled, width=width, color=S.BAD, label="Regime-scaled", zorder=3)
    for v, c, s in zip(xk, kurt_const, kurt_scaled):
        right.text(v - width / 2, c + 0.4, f"{c:.1f}", ha="center", va="bottom", fontsize=15, fontweight="bold",
                    color=S.TEXT, family=S.mono())
        right.text(v + width / 2, s + 0.4, f"{s:.1f}", ha="center", va="bottom", fontsize=15, fontweight="bold",
                    color=S.TEXT, family=S.mono())
    right.set_xticks(xk)
    right.set_xticklabels(kurt_labels, fontsize=15)
    right.set_ylabel("Excess kurtosis\n(tail-heaviness)")
    right.set_ylim(0, max(kurt_const + kurt_scaled) * 1.25)
    right.grid(axis="x", visible=False)
    right.legend(loc="upper left")
    right.set_title("The tail measure rose in the unseen period", fontsize=19, color=S.MUTED, pad=12)

    S.stamp(fig, "NO SHARPE — MEANS NOT ESTIMABLE")
    S.footer(
        fig, SRC_VOL,
        "holdout.C['21'] mean_const/mean_scaled/mean_shuffled; definition.C['21'] and holdout.C['21'] kurt_const/kurt_scaled",
    )
    return S.save(fig, CHART_DIR / "04_cost_pair.png")


def chart_05_sector_correlation() -> Path | None:
    """Beat 7: sector dispersion / correlation, calm vs stressed, both periods,
    from part 04 H2."""
    data = _load(DISP_JSON)
    if data is None:
        print(f"skipped 05_sector_correlation: {DISP_JSON} not present")
        return None

    fig, (left, right) = S.new_figure(
        "Calm markets spread out; stressed markets move together",
        "Nine sector funds, mean pairwise correlation and dispersion ÷ index volatility — 95% interval on the gap",
        ncols=2,
    )
    fig.subplots_adjust(top=0.70, wspace=0.32)

    periods = [("definition", DEF_LABEL, S.CYAN), ("holdout", HOLD_LABEL, S.PURPLE)]

    x = list(range(2))
    width = 0.32
    for offset, (key, label, color) in zip((-width / 2, width / 2), periods):
        h2 = data[key]["H2"]
        vals = [h2["corr_calm"], h2["corr_stressed"]]
        left.bar([v + offset for v in x], vals, width=width, color=color, zorder=3, label=label)
        for v, val in zip(x, vals):
            left.text(v + offset, val + 0.015, f"{val:.3f}", ha="center", va="bottom", fontsize=14,
                       fontweight="bold", color=S.TEXT, family=S.mono())
    left.set_xticks(x)
    left.set_xticklabels(["Calm", "Stressed"])
    left.set_ylabel("Mean pairwise\ncorrelation")
    left.set_ylim(0, 0.85)
    left.grid(axis="x", visible=False)
    left.legend(loc="upper left")
    left.set_title("Correlation, calm vs stressed", fontsize=19, color=S.MUTED, pad=12)

    gap_labels = [DEF_LABEL, HOLD_LABEL]
    gap_colors = [S.CYAN, S.PURPLE]
    gaps = [data["definition"]["H2"]["corr_stressed_minus_calm"], data["holdout"]["H2"]["corr_stressed_minus_calm"]]
    gap_lo = [data["definition"]["H2"]["corr_ci"][0], data["holdout"]["H2"]["corr_ci"][0]]
    gap_hi = [data["definition"]["H2"]["corr_ci"][1], data["holdout"]["H2"]["corr_ci"][1]]
    xg = list(range(2))
    err = [[g - l for g, l in zip(gaps, gap_lo)], [h - g for g, h in zip(gaps, gap_hi)]]
    right.bar(xg, gaps, width=0.5, color=gap_colors, zorder=3)
    right.errorbar(xg, gaps, yerr=err, fmt="none", ecolor=S.TEXT, elinewidth=2.5, capsize=9, capthick=2.5, zorder=4)
    for v, g in zip(xg, gaps):
        right.text(v, g + 0.012, f"+{g:.3f}", ha="center", va="bottom", fontsize=16, fontweight="bold",
                    color=S.TEXT, family=S.mono())
    right.axhline(0, color=S.BENCHMARK, linewidth=2.0, linestyle="--", zorder=2)
    right.set_xticks(xg)
    right.set_xticklabels(gap_labels)
    right.set_ylabel("Correlation gap,\nstressed − calm")
    right.set_ylim(0, max(gap_hi) * 1.3)
    right.grid(axis="x", visible=False)
    right.set_title("Gap excludes zero, both periods", fontsize=19, color=S.MUTED, pad=12)

    S.footer(
        fig, SRC_DISP,
        "definition.H2 / holdout.H2 — corr_calm, corr_stressed, corr_stressed_minus_calm, corr_ci",
    )
    return S.save(fig, CHART_DIR / "05_sector_correlation.png")


def chart_06_two_gauge_card() -> Path | None:
    """Beat 1, thumbnail: two gauges, "how much" needle at the holdout h=5 ratio,
    "which way" needle at the holdout h=5 direction difference (near zero)."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 06_two_gauge_card: {VOL_JSON} not present")
        return None

    import numpy as np

    hold5 = data["holdout"]["AB"]["5"]
    ratio = hold5["A_vol_ratio"]
    ratio_max = 3.0  # dial ceiling; ratio values in this study run 1.7-2.9x
    ratio_frac = min(max(ratio / ratio_max, 0.0), 1.0)

    dir_diff_pct = 100 * hold5["B_ret_diff"]
    dir_span = 1.5  # +/-1.5% dial half-width, comfortably covers the holdout h=5 CI
    dir_frac = min(max((dir_diff_pct + dir_span) / (2 * dir_span), 0.0), 1.0)

    fig, (left, right) = S.new_figure(
        "One of these you can measure. One you can't.",
        f"Holdout period, {HOLD_LABEL} · next 5 days · stressed vs calm days",
        ncols=2,
    )

    def draw_dial(ax, frac, center_label, sub_label, needle_color, lo_text, hi_text):
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.15, 1.2)
        ax.set_aspect("equal")
        ax.axis("off")
        theta = np.linspace(np.pi, 0, 200)
        ax.plot(np.cos(theta), np.sin(theta), color=S.BORDER, linewidth=22, solid_capstyle="butt", zorder=1)
        theta_fill = np.linspace(np.pi, np.pi * (1 - frac), 120)
        ax.plot(np.cos(theta_fill), np.sin(theta_fill), color=needle_color, linewidth=22, solid_capstyle="butt", zorder=2)
        needle_theta = np.pi * (1 - frac)
        ax.plot([0, 0.62 * np.cos(needle_theta)], [0, 0.62 * np.sin(needle_theta)], color=S.TEXT, linewidth=5, zorder=4)
        ax.scatter([0], [0], color=S.TEXT, s=180, zorder=5)
        ax.text(-1.05, -0.05, lo_text, color=S.MUTED, fontsize=15, ha="center", va="top")
        ax.text(1.05, -0.05, hi_text, color=S.MUTED, fontsize=15, ha="center", va="top")
        y0, y1 = -1.15, 1.2
        to_frac = lambda y: (y - y0) / (y1 - y0)
        S.big_number(ax, 0.5, to_frac(-0.35), center_label, color=S.TEXT, size=56, ha="center", va="center")
        ax.text(0, -0.66, sub_label, color=S.MUTED, fontsize=19, fontweight="bold", ha="center", va="center",
                family=S.mono())

    draw_dial(left, ratio_frac, f"{ratio:.2f}×", "HOW MUCH", S.MEASURED, "1×", f"{ratio_max:.0f}×")
    draw_dial(right, dir_frac, f"{dir_diff_pct:+.2f}%".replace("-", "\u2212"), "WHICH WAY", S.BENCHMARK,
               f"−{dir_span:g}%", f"+{dir_span:g}%")

    S.footer(
        fig, SRC_VOL,
        "holdout.AB['5'] — A_vol_ratio (how much) and B_ret_diff (which way); interval on which-way includes zero",
    )
    return S.save(fig, CHART_DIR / "06_two_gauge_card.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_test_a_bars,
        chart_02_test_b_dots,
        chart_03_test_c_variance,
        chart_04_cost_pair,
        chart_05_sector_correlation,
        chart_06_two_gauge_card,
    )
    for chart in charts:
        result = chart()
        if result is not None:
            print("wrote", result.relative_to(ROOT))


if __name__ == "__main__":
    main()
