"""
P06 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from the source study's out/results.json. Every number on a
chart is read from that file at run time; nothing is typed in.

Source study (read-only, never modified):
    RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json — section "E"

Run from the RES008 root:
    .venv/bin/python P_prior_work/P06_contest_win_proves_skill/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

CHART_DIR = Path(__file__).resolve().parent
ROOT = CHART_DIR.parents[2]  # RES008_exposing_fraud
sys.path.insert(0, str(ROOT))

from common import ami_style as S  # noqa: E402

SRC_ROOT = ROOT.parent / "RES001_finding_the_edge"
VOL_JSON = SRC_ROOT / "03_volatility_regime_sizing" / "out" / "results.json"
SRC_VOL = "RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json"

RNG_SEED = 20260830  # matches meta.seed in the source study; illustration only


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _pct1(value_frac: float) -> str:
    """One decimal, rounded half up, so a chart label matches RESULTS.md
    (e.g. 0.3265 -> 32.7, not the binary-float .1f result of 32.6)."""
    from decimal import ROUND_HALF_UP, Decimal
    return f"{Decimal(repr(round(100 * float(value_frac), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def chart_01_crowd_of_dots() -> Path | None:
    """Beats 1, 4, 6: illustrative mechanism — a crowd of zero-skill entrants,
    one month's random return each, the maximum picked out. No claim-specific
    numbers are needed for the mechanism itself (per the brief), but the
    entrant count and the +100% marker both come from the source's own E
    section so the picture matches the test that follows."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 01_crowd_of_dots: {VOL_JSON} not present")
        return None

    n = 300  # one of the source's own by_n cells (300 entrants)
    vol = data["E"]["by_n"]["300"]["required_monthly_vol"]

    rng = np.random.default_rng(RNG_SEED)
    returns = rng.normal(loc=0.0, scale=vol, size=n)
    winner = int(np.argmax(returns))

    fig, ax = S.new_figure(
        "Zero-skill entrants, one month each — someone is always the maximum",
        f"{n:,} illustrative random draws at this test's own required volatility for {n} entrants — no trading skill in the model",
    )
    x = rng.uniform(0, 1, size=n)
    y = 100 * returns
    ymax = float(y.max())
    ymin = float(y.min())
    headroom = ymax + 0.30 * (ymax - ymin)

    ax.scatter(x, y, s=42, color=S.BENCHMARK, alpha=0.55, zorder=2, label="Zero-skill entrant")
    ax.scatter([x[winner]], [y[winner]], s=260, color=S.CLAIM, zorder=4, edgecolors=S.TEXT, linewidths=1.5,
               label="The eventual “winner”")
    ax.axhline(0, color=S.BORDER, linewidth=1.4, zorder=1)
    ax.annotate(
        f"{y[winner]:+.0f}% this draw",
        xy=(x[winner], y[winner]),
        xytext=(min(max(x[winner], 0.18), 0.82), headroom * 0.92),
        ha="center", fontsize=18, fontweight="bold", color=S.TEXT, family=S.mono(),
        arrowprops={"arrowstyle": "-", "color": S.CLAIM, "linewidth": 1.6},
    )
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(ymin - 0.08 * (ymax - ymin), headroom)
    ax.set_xticks([])
    ax.set_ylabel("One month's return, %")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)

    S.stamp(fig, "ILLUSTRATIVE DRAW — MECHANISM ONLY, NOT A MEASURED RESULT")
    S.footer(
        fig, SRC_VOL,
        f"E.by_n[\"300\"].required_monthly_vol = {_pct1(vol)} sets the draw's spread; one random seed, for illustration of the mechanism only",
    )
    return S.save(fig, CHART_DIR / "01_crowd_of_dots.png")


def chart_02_entrant_count_vs_volatility() -> Path | None:
    """Beat 5: the reveal table — entrant count vs the monthly volatility at
    which +100% becomes the expected maximum, as a multiple of SPY's own."""
    data = _load(VOL_JSON)
    if data is None:
        print(f"skipped 02_entrant_count_vs_volatility: {VOL_JSON} not present")
        return None

    e = data["E"]
    spy_vol = e["spy_monthly_vol"]
    ns = ["50", "100", "300", "500"]
    vols = [100 * e["by_n"][n]["required_monthly_vol"] for n in ns]
    mults = [e["by_n"][n]["leverage_vs_spy"] for n in ns]
    x = range(len(ns))

    fig, ax = S.new_figure(
        "Bigger contest, less volatility needed for a +100% “winner”",
        f"Monthly volatility at which +100% is the expected maximum return, zero skill in every entrant · SPY's own monthly volatility: {_pct1(spy_vol)}",
    )
    bars = ax.bar(x, vols, width=0.56, color=S.CLAIM, zorder=3)
    for xi, v, m in zip(x, vols, mults):
        ax.text(xi, v + 1.3, _pct1(v / 100), ha="center", va="bottom", fontsize=20, fontweight="bold",
                 color=S.TEXT, family=S.mono())
        ax.text(xi, v / 2, f"{m:.2f}× SPY", ha="center", va="center", fontsize=16, fontweight="bold",
                 color=S.BG, family=S.mono())
    ax.axhline(100 * spy_vol, color=S.BENCHMARK, linewidth=2.0, linestyle="--", zorder=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{n} entrants" for n in ns])
    ax.set_xlim(-0.6, len(ns) - 0.4)
    ax.set_ylabel("Required monthly\nvolatility, %")
    ax.set_ylim(0, max(vols) * 1.28)
    ax.grid(axis="x", visible=False)
    ax.text(-0.55, 100 * spy_vol + 0.9, "SPY's own volatility", color=S.MUTED, fontsize=14, ha="left",
             va="bottom")

    S.footer(fig, SRC_VOL, "E.spy_monthly_vol; E.by_n[N].required_monthly_vol and .leverage_vs_spy for N in 50/100/300/500")
    return S.save(fig, CHART_DIR / "02_entrant_count_vs_volatility.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_crowd_of_dots,
        chart_02_entrant_count_vs_volatility,
    )
    for chart in charts:
        result = chart()
        if result is not None:
            print("wrote", result.relative_to(ROOT))


if __name__ == "__main__":
    main()
