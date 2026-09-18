"""
P04 chart pack -- the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from the source study's out/results.json. Every measured number
on a chart is read from that file at run time; nothing is typed in.

Source study (read-only, never modified):
    RES001_finding_the_edge/06_absorption_and_elimination/out/results.json

Run from the RES008 root:
    .venv/bin/python P_prior_work/P04_stop_after_k_losses/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CHART_DIR = Path(__file__).resolve().parent
ROOT = CHART_DIR.parents[2]  # RES008_exposing_fraud
sys.path.insert(0, str(ROOT))

from common import ami_style as S  # noqa: E402

SRC_ROOT = ROOT.parent / "RES001_finding_the_edge"
H3_JSON = SRC_ROOT / "06_absorption_and_elimination" / "out" / "results.json"
SRC_H3 = "RES001_finding_the_edge/06_absorption_and_elimination/out/results.json"

WINDOW_LABEL = {"definition": "2005–2018", "holdout": "2019–2026"}
HORIZON_LABEL = {"1": "1 day", "3": "3 days", "5": "5 days"}


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _fmt_pct(value: float, digits: int = 3) -> str:
    """Percent string with a true minus sign, matching RESULTS.md rounding."""
    s = f"{value:.{digits}f}"
    return s.replace("-", "−") + "%"


def _all_h3_cells(data: dict) -> list[dict]:
    """Flatten every window x horizon x k cell in filters.*.H3 into one list,
    each entry carrying its own window/horizon/k labels so nothing is typed in."""
    cells = []
    for window in ("definition", "holdout"):
        for h, h_block in data[window]["filters"].items():
            h3 = h_block.get("H3", {})
            for k, cell in h3.items():
                cells.append(
                    {
                        "window": window,
                        "h": h,
                        "k": k,
                        "diff": cell["rule_minus_placebo"],
                        "ci": cell["ci"],
                        "n_trades": cell["n_trades"],
                        "n_skipped": cell["n_skipped"],
                    }
                )
    return cells


def chart_01_loss_streak_mechanism() -> Path | None:
    """Beat 4: the rule exactly as taught -- a loss-streak counter ticking to k,
    then "skip next trade". Illustrative mechanism only; the k values shown are
    the two k's actually tested (read from the JSON's own H3 keys), not a
    measured statistic."""
    data = _load(H3_JSON)
    if data is None:
        print(f"skipped 01_loss_streak_mechanism: {H3_JSON} not present")
        return None

    ks = sorted({k for h_block in data["definition"]["filters"].values() for k in h_block.get("H3", {})})

    fig, axes = S.new_figure(
        "The rule, exactly as taught",
        "After k losing trades in a row, skip the next trade — tested for k = " + " and ".join(ks),
        ncols=len(ks),
    )
    if len(ks) == 1:
        axes = [axes]

    for ax, k in zip(axes, ks):
        k_int = int(k)
        ax.set_xlim(-0.6, k_int + 1.6)
        ax.set_ylim(-1.0, 1.3)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"k = {k}", fontsize=24, color=S.MUTED, pad=14)

        for i in range(k_int):
            ax.add_patch(
                __import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                    (i, 0), 0.8, 0.8, facecolor=S.BAD, edgecolor="none", zorder=3
                )
            )
            ax.text(i + 0.4, 0.4, "L", ha="center", va="center", fontsize=22, fontweight="bold",
                     color=S.TEXT, zorder=4)
            ax.text(i + 0.4, -0.35, f"loss {i + 1}", ha="center", va="center", fontsize=13, color=S.MUTED)

        skip_x = k_int
        ax.add_patch(
            __import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                (skip_x, 0), 0.8, 0.8, facecolor=S.CARD, edgecolor=S.CLAIM, linewidth=2.5, zorder=3
            )
        )
        ax.text(skip_x + 0.4, 0.4, "SKIP", ha="center", va="center", fontsize=15, fontweight="bold",
                 color=S.CLAIM, zorder=4)
        ax.text(skip_x + 0.4, -0.35, "next trade", ha="center", va="center", fontsize=13, color=S.MUTED)

        for i in range(k_int):
            ax.annotate(
                "", xy=(i + 0.82, 0.4), xytext=(i + 1.0, 0.4) if i + 1 < k_int else (skip_x, 0.4),
                arrowprops={"arrowstyle": "-", "color": "none"},
            )

    S.footer(
        fig, SRC_H3,
        "illustrative mechanism only, no measured value on this chart — k values are the H3 keys tested",
    )
    return S.save(fig, CHART_DIR / "01_loss_streak_mechanism.png")


def chart_02_four_cell_reveal() -> Path | None:
    """Beat 5: the four-cell rule-vs-placebo table the brief calls out by name,
    plus the 10-of-12 and 3-of-12 summary computed here from every H3 cell in
    the source file (not just the four highlighted)."""
    data = _load(H3_JSON)
    if data is None:
        print(f"skipped 02_four_cell_reveal: {H3_JSON} not present")
        return None

    all_cells = _all_h3_cells(data)
    below_placebo = sum(1 for c in all_cells if c["diff"] < 0)
    excludes_zero = sum(1 for c in all_cells if c["ci"][0] > 0 or c["ci"][1] < 0)
    total = len(all_cells)

    # The brief's four highlighted cells: Def h1 k2, Def h3 k2, Hold h1 k3, Hold h5 k3.
    picks = [
        ("definition", "1", "2"),
        ("definition", "3", "2"),
        ("holdout", "1", "3"),
        ("holdout", "5", "3"),
    ]
    cells = []
    for window, h, k in picks:
        c = data[window]["filters"][h]["H3"][k]
        cells.append(
            {
                "label": f"{WINDOW_LABEL[window]}\n{HORIZON_LABEL[h]} · k={k}",
                "diff": 100 * c["rule_minus_placebo"],
                "lo": 100 * c["ci"][0],
                "hi": 100 * c["ci"][1],
            }
        )

    fig, ax = S.new_figure(
        f"The rule underperformed random skipping in {below_placebo} of {total} test cells",
        "Rule mean minus placebo mean, forward return — 95% interval — reference line at zero (no difference)",
    )
    fig.subplots_adjust(left=0.24)

    y = list(range(len(cells)))
    for yi, c in zip(y, cells):
        excl = c["lo"] > 0 or c["hi"] < 0
        color = S.BAD if excl else S.MEASURED
        ax.plot([c["lo"], c["hi"]], [yi, yi], color=color, linewidth=7, solid_capstyle="round", zorder=2)
        ax.scatter([c["diff"]], [yi], color=S.TEXT, s=160, zorder=3)
        label = f"{c['diff']:+.3f}%".replace("-", "−")
        ax.text(c["hi"] + 0.006, yi, label, color=S.TEXT, fontsize=17, va="center", family=S.mono())
    ax.axvline(0, color=S.BENCHMARK, linewidth=2.2, linestyle="--", zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels([c["label"] for c in cells], fontsize=16)
    ax.set_ylim(-1.55, len(cells) - 1 + 0.6)
    ax.invert_yaxis()
    ax.set_xlabel("Rule − placebo, forward return, %")
    xs = [c["lo"] for c in cells] + [c["hi"] for c in cells]
    span = max(xs) - min(xs)
    lo_lim, hi_lim = min(xs) - 0.12 * span, max(xs) + 0.34 * span
    ax.set_xlim(lo_lim, hi_lim)
    ax.set_xticks([t for t in (-0.20, -0.15, -0.10, -0.05, 0.0, 0.05) if lo_lim <= t <= hi_lim])
    ax.grid(axis="y", visible=False)

    from matplotlib.lines import Line2D

    handles = [
        Line2D([0], [0], color=S.BAD, linewidth=7, label="95% interval excludes zero (harmful side)"),
        Line2D([0], [0], color=S.MEASURED, linewidth=7, label="95% interval includes zero"),
        Line2D([0], [0], color=S.BENCHMARK, linewidth=2.2, linestyle="--", label="0 = no difference from random skip"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=14)

    S.footer(
        fig, SRC_H3,
        f"filters.*.H3 (all {total} window×horizon×k cells) — four cells shown are Def h1 k2, Def h3 k2, "
        f"Hold h1 k3, Hold h5 k3; {excludes_zero} of {total} intervals exclude zero, all on the harmful side",
    )
    return S.save(fig, CHART_DIR / "02_four_cell_reveal.png")


def chart_03_mean_reversion_sketch() -> Path | None:
    """Beat 6: illustrative mean-reversion diagram -- a dip, a rebound, and the
    trade the rule skips sitting out part of it. No numeric claim on this
    chart; the brief says the beat-5 table already carries the numbers."""
    if not H3_JSON.exists():
        print(f"skipped 03_mean_reversion_sketch: {H3_JSON} not present")
        return None

    import numpy as np

    fig, ax = S.new_figure(
        "Why: sitting out after a loss can mean sitting out the rebound",
        "Illustrative sketch of mild mean reversion — not a real price path",
    )
    x = np.linspace(0, 10, 400)
    y = -np.exp(-((x - 3.2) ** 2) / 1.1) * 1.6 + np.exp(-((x - 5.6) ** 2) / 2.2) * 1.15
    ax.plot(x, y, color=S.MUTED, linewidth=3.2, zorder=2)
    ax.axhline(0, color=S.BORDER, linewidth=1.4, zorder=1)

    loss_x = 3.2
    ax.scatter([loss_x], [float(np.interp(loss_x, x, y))], color=S.BAD, s=170, zorder=4)
    ax.annotate("losing streak\ntriggers the rule", xy=(loss_x, float(np.interp(loss_x, x, y))),
                xytext=(loss_x - 1.6, -2.1), color=S.BAD, fontsize=15, ha="center",
                arrowprops={"arrowstyle": "-", "color": S.BAD, "lw": 1.4})

    skip_lo, skip_hi = 3.4, 5.0
    mask = (x >= skip_lo) & (x <= skip_hi)
    ax.fill_between(x[mask], 0, y[mask], color=S.CLAIM, alpha=0.28, zorder=1)
    mid = (skip_lo + skip_hi) / 2
    ax.annotate("trade skipped here", xy=(mid, float(np.interp(mid, x, y)) / 2),
                xytext=(mid, 1.5), color=S.CLAIM, fontsize=16, fontweight="bold", ha="center",
                arrowprops={"arrowstyle": "-", "color": S.CLAIM, "lw": 1.6})

    rebound_x = 5.6
    ax.scatter([rebound_x], [float(np.interp(rebound_x, x, y))], color=S.GOOD, s=140, zorder=4)
    ax.annotate("part of the rebound\nis inside the skip", xy=(rebound_x, float(np.interp(rebound_x, x, y))),
                xytext=(rebound_x + 1.6, 1.6), color=S.GOOD, fontsize=15, ha="center",
                arrowprops={"arrowstyle": "-", "color": S.GOOD, "lw": 1.4})

    ax.set_xlim(0, 10)
    ax.set_ylim(-2.6, 2.3)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(False)

    S.footer(
        fig, SRC_H3,
        "illustrative only, no numeric overlay — measured cells are on chart 02",
    )
    S.stamp(fig, "ILLUSTRATIVE SKETCH — NOT A MEASURED PRICE PATH")
    return S.save(fig, CHART_DIR / "03_mean_reversion_sketch.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_loss_streak_mechanism,
        chart_02_four_cell_reveal,
        chart_03_mean_reversion_sketch,
    )
    for chart in charts:
        result = chart()
        if result is not None:
            print("wrote", result.relative_to(ROOT))


if __name__ == "__main__":
    main()
