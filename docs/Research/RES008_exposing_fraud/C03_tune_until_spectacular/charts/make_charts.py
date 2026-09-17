"""
C03 chart pack -- the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json and out/grid_returns_BTC-USD.csv. Every
number on a chart is read from those files at run time; nothing is typed in.

Run from the RES008 root:
    .venv/bin/python C03_tune_until_spectacular/charts/make_charts.py
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

OUT_DIR = CLAIM_DIR / "out"
RESULTS = json.loads((OUT_DIR / "results.json").read_text())
SOURCE = "C03_tune_until_spectacular/out/results.json"
PER_INSTRUMENT = RESULTS["per_instrument"]
POOLED = RESULTS["pooled"]


def _sorted_instruments_by_t1():
    return sorted(PER_INSTRUMENT.items(), key=lambda kv: kv[1]["T1_holdout_percentile"])


def chart_01_winner_holdout_percentiles(partial: bool = False) -> Path:
    """Beat 5, Short. T1 per instrument, sorted, with the 50-line and the
    41.8-66.3 interval shaded around the 54.5 pooled mean. `partial=True`
    renders only the first half of instruments (dots dropping in) as a key
    frame for the animation the brief asks for."""
    items = _sorted_instruments_by_t1()
    n_total = len(items)
    n_show = max(1, n_total // 2) if partial else n_total
    shown = items[:n_show]

    mean = POOLED["mean_T1"]
    lo = POOLED["mean_T1_ci_lower"]
    hi = POOLED["mean_T1_ci_upper"]

    fig, ax = S.new_figure(
        "The best-of-420 winner, ranked again on years it never saw",
        f"{n_total} instruments · dot = one instrument's tuning-window winner",
    )
    y = np.arange(len(items))
    ax.axvspan(lo, hi, color=S.BENCHMARK, alpha=0.18, zorder=0)
    ax.axvline(50, color=S.MUTED, linestyle="--", linewidth=2.2, label="50 = selection told you nothing", zorder=1)
    ax.axvline(mean, color=S.CLAIM, linestyle="-", linewidth=2.2, label=f"Mean = {mean:.1f}", zorder=1)

    vals = [v["T1_holdout_percentile"] for _, v in shown]
    ax.scatter(vals, y[: len(shown)], s=170, color=S.MEASURED, zorder=3, edgecolor=S.BG, linewidth=1.2)

    ax.set_yticks(y)
    ax.set_yticklabels([k for k, _ in items], fontsize=14, family=S.mono())
    if partial:
        for i in range(len(shown), len(items)):
            ax.get_yticklabels()[i].set_alpha(0.25)
    ax.set_xlim(-2, 102)
    ax.set_xlabel("Holdout-window rank among the 420, as a percentile (50 = middle of the pack)", labelpad=14)
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(bottom=0.20)

    note = "shaded band = 95% interval on the mean (bootstrap over instruments)"
    S.footer(fig, SOURCE, note)
    suffix = "_partial" if partial else ""
    return S.save(fig, CHART_DIR / f"01_winner_holdout_percentiles{suffix}.png")


def chart_02_is_vs_oos_rank_btc() -> Path:
    """Beat 5. BTC-only: every one of the 420 configs' tuning-window rank vs
    holdout-window rank, star on the winner. Ranks are read back out of the
    grid CSV (1 = best return in that window)."""
    import csv

    rows = list(csv.DictReader((OUT_DIR / "grid_returns_BTC-USD.csv").open()))
    tune_ret = np.array([float(r["tune_return"]) for r in rows])
    hold_ret = np.array([float(r["holdout_return"]) for r in rows])
    # rank 1 = best (highest) return in that window
    tune_rank = len(tune_ret) - tune_ret.argsort().argsort()
    hold_rank = len(hold_ret) - hold_ret.argsort().argsort()

    winner_idx = RESULTS["per_instrument"]["BTC-USD"]["winner_config_index"]

    fig, ax = S.new_figure(
        "Bitcoin: 420 settings, ranked once while tuning and once afterward",
        "Every point is one setting; a good tuning-window rank does not predict a good holdout rank",
    )
    ax.scatter(tune_rank, hold_rank, s=55, color=S.MEASURED, alpha=0.55, label="420 settings", edgecolor="none")
    ax.scatter(
        tune_rank[winner_idx], hold_rank[winner_idx],
        s=420, marker="*", color=S.CLAIM, edgecolor=S.TEXT, linewidth=1.2,
        label="the chosen winner", zorder=5,
    )
    ax.set_xlabel("Rank when chosen (1 = best backtest during tuning)")
    ax.set_ylabel("Rank afterward\n(1 = best return in the holdout)")
    ax.legend(loc="upper left")
    S.footer(fig, "C03_tune_until_spectacular/out/grid_returns_BTC-USD.csv")
    return S.save(fig, CHART_DIR / "02_is_vs_oos_rank_BTC.png")


def chart_03_leverage_10x_btc_linear() -> Path:
    """Beat 5. Redraw of leverage_10x_BTC.png on a LINEAR axis (the shipped
    log version silently drops non-positive equity bars and hides the
    wipe-outs); liquidation dates marked."""
    p3 = RESULTS["part3_btc_leverage"]

    fig, axes = S.new_figure(
        "The tuned Bitcoin winner at 10× margin, on a linear axis",
        "Even the path that ignores liquidation goes through zero: one 10% adverse day loses more than the account",
        ncols=2,
    )
    fig.subplots_adjust(top=0.74, bottom=0.22, wspace=0.28)
    for ax, window, label in zip(axes, ("tuning", "holdout"), ("Tuning window", "Holdout window")):
        lev = p3[window]["leverage_10x"]
        dates = np.array(lev["dates"], dtype="datetime64[D]")
        as_shown = np.array(lev["as_shown_equity_curve"])
        n_events = lev["n_liquidation_events"]
        liq_dates = np.array(lev["liquidation_dates"], dtype="datetime64[D]")

        ax.plot(dates, np.clip(as_shown, 0, None), color=S.MEASURED, linewidth=2.2)
        ax.axhline(0, color=S.BAD, linewidth=1.6)
        for d in liq_dates:
            ax.axvline(d, color=S.BAD, alpha=0.35, linewidth=1.0, zorder=0)
        ax.set_title(f"{label} — {n_events} liquidation events", fontsize=18, color=S.TEXT, pad=12)
        ax.set_ylabel("Account equity,\nmultiple of start", fontsize=16)
        ax.tick_params(axis="x", labelrotation=30, labelsize=14)
        ax.tick_params(axis="y", labelsize=14)

    note = "blue = as-shown path, ignores liquidation · red vertical lines = a day the account would have been liquidated"
    S.footer(fig, SOURCE, note)
    return S.save(fig, CHART_DIR / "03_leverage_10x_BTC_linear.png")


def chart_04_btc_winner_curve() -> Path:
    """Beats 1, 4. The BTC winner's headline number, tuning window then the
    holdout appended, against buying and holding over the same holdout. Only
    the tuning-end and holdout-end totals exist in out/ (no daily equity
    series for the unlevered winner) -- drawn as three milestones, not a
    fabricated daily path."""
    b = PER_INSTRUMENT["BTC-USD"]
    tune_end = 1 + b["winner_tune_return"]
    hold_end_winner = tune_end * (1 + b["winner_holdout_return"])
    hold_end_bh = tune_end * (1 + b["holdout_buy_hold_return"])
    tune_start, tune_stop = b["tune_window"]
    hold_start, hold_stop = b["holdout_window"]

    fig, ax = S.new_figure(
        "The Bitcoin winner's tuning-window number, then the years it never saw",
        f"Tuned {tune_start} to {tune_stop} · measured {hold_start} to {hold_stop} · unlevered, costs included",
    )
    x = [0, 1, 2]
    xt = ["Start\n($1 in)", "End of tuning\nwindow", "End of\nholdout"]
    y_winner = [1, tune_end, hold_end_winner]
    y_bh = [1, tune_end, hold_end_bh]

    ax.plot(x, y_winner, color=S.MEASURED, marker="o", markersize=14, linewidth=3, label="Tuned winner", zorder=3)
    ax.plot(x[1:], y_bh[1:], color=S.BENCHMARK, marker="o", markersize=14, linewidth=3, linestyle="--", label="Buy and hold (holdout only)", zorder=2)

    ax.set_yscale("log")
    ax.set_xlim(-0.3, 2.85)
    ax.set_ylim(0.5, 10 ** (np.log10(hold_end_bh) + 0.9))
    ax.set_xticks(x)
    ax.set_xticklabels(xt, fontsize=17)
    ax.set_ylabel("Account value, $1 invested (log scale)")

    ax.annotate(f"+{100*b['winner_tune_return']:,.0f}%\nwhile being chosen", (1, tune_end),
                textcoords="offset points", xytext=(-100, 14), fontsize=16, color=S.CLAIM, fontweight="bold", ha="left")
    ax.annotate(f"buy and hold\n+{100*b['holdout_buy_hold_return']:,.0f}%", (2, hold_end_bh),
                textcoords="offset points", xytext=(14, 18), fontsize=16, color=S.MUTED, fontweight="bold", ha="left")
    ax.annotate(f"tuned winner\n+{100*b['winner_holdout_return']:,.0f}% afterward", (2, hold_end_winner),
                textcoords="offset points", xytext=(14, -46), fontsize=16, color=S.MEASURED, fontweight="bold", ha="left")

    ax.legend(loc="upper left")
    S.footer(fig, SOURCE, "milestones only: no daily equity series for the unlevered winner is in out/")
    return S.save(fig, CHART_DIR / "04_btc_winner_curve.png")


def chart_05_tuned_vs_random_bars() -> Path:
    """Beat 6. 23 pairs: the tuned winner's tuning-window return vs the best
    of 420 random long/flat placebos on the same window. Log axis (all
    values positive)."""
    items = sorted(
        PER_INSTRUMENT.items(),
        key=lambda kv: kv[1]["part2_random_placebo"]["best_random_tune_return"],
    )
    labels = [k for k, _ in items]
    tuned = [100 * v["winner_tune_return"] for _, v in items]
    rand = [100 * v["part2_random_placebo"]["best_random_tune_return"] for _, v in items]
    n_beat = sum(1 for t, r in zip(tuned, rand) if r > t)

    fig, ax = S.new_figure(
        "The best of 420 random strategies beat the tuned winner everywhere",
        f"Same tuning window, same market · best random beat the tuned winner on {n_beat} of {len(items)} instruments",
    )
    y = np.arange(len(items))
    h = 0.38
    ax.barh(y + h / 2, tuned, height=h, color=S.MEASURED, label="Tuned winner (best of 420 real settings)")
    ax.barh(y - h / 2, rand, height=h, color=S.CLAIM, label="Best of 420 random strategies")
    ax.set_xscale("log")
    ax.set_xlim(40, 6e4)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=13, family=S.mono())
    ax.set_xlabel("Tuning-window return, % (log scale)")
    ax.legend(loc="lower right", fontsize=15)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-0.8, len(items) - 0.2)

    S.footer(fig, SOURCE, "both sides picked as the single best of 420 on the same window — selection, not skill")
    return S.save(fig, CHART_DIR / "05_tuned_vs_random_bars.png")


def chart_06_leverage_5x_posthoc() -> Path:
    """Beat 7, post hoc. The 5x path over the tuning window: the curve a tester with
    no liquidation rule prints, and the day an exchange would have closed the account."""
    lev = RESULTS["part3_btc_leverage"]["tuning"]["leverage_5x_extra_not_preregistered"]
    dates = np.array(lev["dates"], dtype="datetime64[D]")
    as_shown = np.array(lev["as_shown_equity_curve"], dtype=float)
    liq_date = np.datetime64(lev["liquidation_dates"][0], "D")
    at_liq = float(as_shown[dates < liq_date][-1])  # the close before the liquidation bar
    final = lev["as_shown_final_equity_multiple"]

    fig, ax = S.new_figure(
        "At 5× margin the backtest prints millions. The account ended on one day in 2017.",
        f"Tuned Bitcoin winner, tuning window · a {100*lev['adverse_threshold']:.0f}% move against a 5× position takes the whole account",
    )
    before = dates < liq_date
    ax.plot(dates[~before], as_shown[~before], color=S.CLAIM, linewidth=2.4, alpha=0.55,
            label="A tester with no liquidation rule")
    ax.plot(dates[before], as_shown[before], color=S.MEASURED, linewidth=2.8, label="The account, until it is closed")
    ax.axvline(liq_date, color=S.BAD, linewidth=2.2)
    ax.scatter([dates[before][-1]], [at_liq], color=S.BAD, s=160, zorder=5)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}×" if v >= 1 else f"{v:g}×"))
    ax.set_ylabel("Account, multiple of start (log scale)")
    ax.annotate(f"liquidated {liq_date}\naccount stood at {at_liq:.1f}× its start → 0", (liq_date, at_liq),
                textcoords="offset points", xytext=(18, -84), fontsize=17, color=S.BAD, fontweight="bold", ha="left")
    ax.annotate(f"{final:,.0f}× on paper", (dates[-1], as_shown[-1]), textcoords="offset points", xytext=(-14, 4),
                fontsize=17, color=S.CLAIM, fontweight="bold", ha="right", va="bottom")
    ax.legend(loc="upper left")

    S.stamp(fig)
    S.footer(fig, SOURCE, "part3_btc_leverage.tuning.leverage_5x_extra_not_preregistered — daily bars; intraday data would move the date, not the point")
    return S.save(fig, CHART_DIR / "06_leverage_5x_posthoc.png")


def main() -> None:
    S.apply()
    charts = (
        lambda: chart_01_winner_holdout_percentiles(partial=True),
        lambda: chart_01_winner_holdout_percentiles(partial=False),
        chart_02_is_vs_oos_rank_btc,
        chart_03_leverage_10x_btc_linear,
        chart_04_btc_winner_curve,
        chart_05_tuned_vs_random_bars,
        chart_06_leverage_5x_posthoc,
    )
    for chart in charts:
        print("wrote", chart().relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
