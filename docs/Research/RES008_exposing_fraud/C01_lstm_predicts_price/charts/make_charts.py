"""
C01 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json (and, where noted, out/results_full.json).
Every number on a chart is read from those files at run time; nothing is typed in.

out/results_full.json is git-ignored (27 MB, per-cell daily return series) and may
not exist on every machine. Figures that need it degrade gracefully: if the file is
absent, the figure is skipped with a printed message and the script still exits 0.
Figures built from out/results.json alone (the committed, slim file) always run.

Two brief figures are intentionally NOT produced here because their source data is
not persisted anywhere in out/: the AAPL overlay restyle (needs the raw actual /
predicted / persistence price series from a freshly trained model — out/results.json
and out/results_full.json only carry per-cell summary metrics and, for M4, daily
*returns*, never price levels or predictions) and the lag animation / 30-day
recursive-forecast redraw (same reason; the brief itself marks these "(to draw)" /
"recompute before recording"). Re-running make_overlay_figure.py or run_c01.py to
manufacture that data is against this pack's hard rules. See charts/README.md.

Run from the RES008 root:
    .venv/bin/python C01_lstm_predicts_price/charts/make_charts.py
"""

from __future__ import annotations

import json
import statistics
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

RESULTS = json.loads((CLAIM_DIR / "out" / "results.json").read_text())
SOURCE = "C01_lstm_predicts_price/out/results.json"
FULL_PATH = CLAIM_DIR / "out" / "results_full.json"

PRICE_ARMS = ["A1", "A2", "B-price"]
ALL_ARMS = ["A1", "A2", "B-price", "B-return"]
ARM_LABEL = {
    "A1": "as taught, 100-day window",
    "A2": "as taught, 60-day window",
    "B-price": "fair scaler, same target",
    "B-return": "fair scaler, return target",
}
ARM_COLOR = {
    "A1": S.MEASURED,
    "A2": S.CYAN,
    "B-price": S.PURPLE,
    "B-return": S.PINK,
}


def _pct1(value_pct: float) -> str:
    """One decimal, rounded half up, so a chart label matches RESULTS.md (e.g. 84.25 -> 84.3)."""
    return f"{Decimal(repr(round(float(value_pct), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _pooled_always_up_rate(arm: str) -> float:
    """Pooled always-up base rate, weighted by each ticker-seed cell's n — matches
    RESULTS.md section 3's "Always-up, pooled" column (not stored as its own key;
    part1's max_base_rate is the max over tickers, a different number)."""
    cells = RESULTS[arm]["per_ticker_seed"]
    total_n = sum(c["M3"]["n"] for c in cells)
    weighted = sum(c["M3"]["always_up_base_rate"] * c["M3"]["n"] for c in cells)
    return 100 * weighted / total_n


def chart_01_error_ratio() -> Path:
    """Beat 5: M1 error ratio (network RMSE / "tomorrow = today" RMSE) per run,
    for the three price-forecasting arms, with the break-even line at 1.0."""
    fig, ax = S.new_figure(
        "On the error score these charts are sold on, every price forecast lost",
        "Network RMSE ÷ “tomorrow's price = today's” RMSE, one dot per ticker × seed run",
    )
    fig.subplots_adjust(left=0.24, right=0.78)
    y_positions = {}
    for i, arm in enumerate(PRICE_ARMS):
        ratios = RESULTS[arm]["pooled_M1"]["ratios"]
        y = np.full(len(ratios), i) + np.random.default_rng(0).uniform(-0.16, 0.16, len(ratios))
        ax.scatter(ratios, y, color=ARM_COLOR[arm], s=90, alpha=0.75, zorder=3, edgecolor=S.BG, linewidth=0.6)
        median = RESULTS[arm]["pooled_M1"]["median_ratio"]
        ax.plot([median, median], [i - 0.32, i + 0.32], color=S.TEXT, linewidth=3, zorder=4)
        y_positions[arm] = i

    ax.set_xscale("log")
    ax.axvline(1.0, color=S.BENCHMARK, linewidth=2.2, linestyle="--", zorder=2)
    xmax = max(max(RESULTS[a]["pooled_M1"]["ratios"]) for a in PRICE_ARMS)
    ax.set_xlim(0.9, xmax * 1.35)
    ax.xaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.text(1.04, -0.55, "1× = no better than\n“tomorrow = today”", color=S.BENCHMARK,
            fontsize=15, ha="left", va="bottom")

    for arm in PRICE_ARMS:
        median = RESULTS[arm]["pooled_M1"]["median_ratio"]
        n_below = round(RESULTS[arm]["pooled_M1"]["frac_below_1"] * RESULTS[arm]["pooled_M1"]["n"])
        n_total = RESULTS[arm]["pooled_M1"]["n"]
        ax.text(
            1.02, y_positions[arm], f"median {median:.2f}×\n{n_below} of {n_total} beat it",
            transform=ax.get_yaxis_transform(), color=S.TEXT, fontsize=15, va="center", family=S.mono(), ha="left",
        )

    ax.set_yticks([y_positions[a] for a in PRICE_ARMS])
    ax.set_yticklabels([ARM_LABEL[a] for a in PRICE_ARMS])
    ax.set_ylim(-1.0, len(PRICE_ARMS) - 0.4)
    ax.invert_yaxis()
    ax.set_xlabel("Error ratio, network ÷ “tomorrow = today” (log scale)")
    ax.grid(axis="y", visible=False)

    S.footer(fig, SOURCE, "dots = *.pooled_M1.ratios · line = *.pooled_M1.median_ratio, frac_below_1, n")
    return S.save(fig, CHART_DIR / "01_error_ratio.png")


def chart_02_direction_hit_rate() -> Path:
    """Beat 5/6: direction hit rate per arm against the pooled always-up base rate."""
    fig, ax = S.new_figure(
        "Every forecast called direction worse than just saying “up”",
        "Pooled hit rate on tomorrow's up/down call, with its 95% interval, against the always-up base rate",
    )
    x = np.arange(len(ALL_ARMS))
    hit = [100 * RESULTS[a]["pooled_M3"]["pooled_hit_rate"] for a in ALL_ARMS]
    lo = [100 * RESULTS[a]["pooled_M3"]["pooled_wilson_ci"]["lower"] for a in ALL_ARMS]
    hi = [100 * RESULTS[a]["pooled_M3"]["pooled_wilson_ci"]["upper"] for a in ALL_ARMS]
    base = [_pooled_always_up_rate(a) for a in ALL_ARMS]
    err = [[h - l for h, l in zip(hit, lo)], [hh - h for h, hh in zip(hit, hi)]]

    bars = ax.bar(x, hit, width=0.5, color=S.MEASURED, zorder=3, label="Measured hit rate")
    ax.errorbar(x, hit, yerr=err, fmt="none", ecolor=S.TEXT, elinewidth=2.5, capsize=8, capthick=2.5, zorder=4)
    for xi, b in zip(x, base):
        ax.plot([xi - 0.32, xi + 0.32], [b, b], color=S.CLAIM, linewidth=3.2, zorder=5)
    ax.axhline(50.0, color=S.BENCHMARK, linewidth=1.8, linestyle="--", zorder=2)
    ax.text(-0.62, 50.4, "coin flip", color=S.BENCHMARK, fontsize=14, va="bottom", ha="left")
    ax.set_xlim(-0.65, len(ALL_ARMS) - 0.5)

    for xi, value in zip(x, hit):
        ax.text(xi, value - 2.2, _pct1(value), ha="center", va="top", fontsize=18, fontweight="bold",
                 color=S.BG, family=S.mono())
    for xi, b in zip(x, base):
        ax.text(xi, b + 1.0, f"always-up {_pct1(b)}", ha="center", va="bottom", fontsize=13, color=S.CLAIM)

    ax.set_xticks(list(x))
    ax.set_xticklabels([ARM_LABEL[a] for a in ALL_ARMS], fontsize=15)
    ax.set_ylabel("Direction hit rate, %")
    ax.set_ylim(0, max(base) + 8)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "bars = *.pooled_M3.pooled_hit_rate, pooled_wilson_ci · amber = always-up base rate, weighted by *.M3.n")
    return S.save(fig, CHART_DIR / "02_direction_hit_rate.png")


def chart_03_traded_vs_holding() -> Path:
    """Beat 5: median total return of the traded rule vs buy-and-hold, next-open fills,
    per arm, plus the count of runs that beat buy-and-hold."""
    fig, ax = S.new_figure(
        "Trading the forecast made less money than not trading at all",
        "Median total return over the test segment, next-open fills, one run per ticker × seed",
    )
    x = np.arange(len(ALL_ARMS))
    width = 0.32
    model_med, bh_med, beat_counts, run_counts = [], [], [], []
    for arm in ALL_ARMS:
        cells = RESULTS[arm]["per_ticker_seed"]
        model = [c["M4"]["next_open"]["model_total_return"] for c in cells]
        bh = [c["M4"]["next_open"]["bh_total_return"] for c in cells]
        model_med.append(100 * statistics.median(model))
        bh_med.append(100 * statistics.median(bh))
        beat_counts.append(sum(1 for m, b in zip(model, bh) if m > b))
        run_counts.append(len(cells))

    ax.bar(x - width / 2, model_med, width=width, color=S.MEASURED, label="Traded the forecast", zorder=3)
    ax.bar(x + width / 2, bh_med, width=width, color=S.BENCHMARK, label="Bought and held", zorder=3)
    for xi, v in zip(x - width / 2, model_med):
        ax.text(xi, v + 2, f"+{v:.0f}%", ha="center", va="bottom", fontsize=16, fontweight="bold",
                 color=S.TEXT, family=S.mono())
    for xi, v in zip(x + width / 2, bh_med):
        ax.text(xi, v + 2, f"+{v:.0f}%", ha="center", va="bottom", fontsize=16, fontweight="bold",
                 color=S.TEXT, family=S.mono())
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [f"{ARM_LABEL[a]}\n{n} of {total} runs beat holding" for a, n, total in zip(ALL_ARMS, beat_counts, run_counts)],
        fontsize=15,
    )
    ax.set_ylabel("Median total return, %")
    ax.set_ylim(0, max(bh_med) * 1.4)
    ax.legend(loc="upper left", ncols=2)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "median of *.per_ticker_seed[].M4.next_open.{model_total_return,bh_total_return}; beat-count computed the same way")
    return S.save(fig, CHART_DIR / "03_traded_vs_holding.png")


def chart_04_tracks_tomorrow() -> Path:
    """Beat 6/7: correlation of the forecast with tomorrow's move (tiny, one interval
    excludes zero) beside its correlation with yesterday's move (large, an echo)."""
    fig, (left, right) = S.new_figure(
        "The forecast moves with yesterday, barely with tomorrow",
        "Pooled correlation, 95% interval · corr(forecast, tomorrow's move) vs corr(forecast, yesterday's move)",
        ncols=2,
    )
    fig.subplots_adjust(left=0.24, right=0.95, wspace=0.12, top=0.76)
    y = np.arange(len(ALL_ARMS))

    for ax, key, title in (
        (left, "pooled_corr_tracks_tomorrow", "Tracks tomorrow"),
        (right, "pooled_corr_echoes_yesterday", "Echoes yesterday"),
    ):
        est = [RESULTS[a]["pooled_M2"][key]["estimate"] for a in ALL_ARMS]
        lo = [RESULTS[a]["pooled_M2"][key]["lower"] for a in ALL_ARMS]
        hi = [RESULTS[a]["pooled_M2"][key]["upper"] for a in ALL_ARMS]
        colors = [S.BAD if (key == "pooled_corr_tracks_tomorrow" and l > 0) else S.MEASURED for l in lo]
        ax.axvline(0, color=S.TEXT, linewidth=1.6, zorder=2)
        for yi, e, l, h, c in zip(y, est, lo, hi, colors):
            flagged = c == S.BAD
            ax.plot([l, h], [yi, yi], color=c, linewidth=7, solid_capstyle="round", zorder=3)
            ax.scatter([e], [yi], color=S.BAD if flagged else S.TEXT, s=130, zorder=4)
            label = f"{e:.3f}".replace("-", "\u2212")
            if h > 0.7 or e < 0:
                ax.text(l - 0.03, yi, label, color=S.TEXT, fontsize=15, va="center", ha="right", family=S.mono())
            else:
                ax.text(h + 0.03, yi, label, color=S.BAD if flagged else S.TEXT, fontsize=15, va="center",
                        ha="left", family=S.mono(), fontweight="bold" if flagged else "normal")
        ax.set_title(title, fontsize=22, color=S.TEXT, pad=6)
        ax.set_yticks(list(y))
        ax.set_yticklabels([ARM_LABEL[a] for a in ALL_ARMS] if ax is left else [])
        ax.set_xlim(-0.3, 1.0)
        ax.set_ylim(-0.5, len(ALL_ARMS) - 0.5)
        ax.set_xlabel("Correlation")
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)

    left.text(
        0.97, 0.80,
        "red = small, but the interval\nexcludes zero — why the verdict is\nNOT SUPPORTED, not DISPROVED",
        transform=left.transAxes, color=S.BAD, fontsize=13, ha="right", va="top",
    )

    S.footer(fig, SOURCE, "*.pooled_M2.pooled_corr_tracks_tomorrow / pooled_corr_echoes_yesterday .{estimate,lower,upper}")
    return S.save(fig, CHART_DIR / "04_tracks_tomorrow_vs_echo.png")


def chart_05_equity_curves() -> Path | None:
    """Beat 5: pooled equity curve, traded rule vs buy-and-hold, seed 0. Needs
    out/results_full.json (per-day return series, git-ignored) — degrades
    gracefully if that file is not present.

    A2 is excluded here: its test segment is 2023-09-21..2026-08-28 (80/20 split),
    a different and shorter window than A1 / B-price's 2021-07-12..2026-08-28
    (65/35 split), so its curve is not comparable on a shared trading-day x-axis
    or against the same buy-and-hold line. A2's own numbers are in charts
    01-04 and RESULTS.md; only A1 and B-price share one test window here."""
    if not FULL_PATH.exists():
        print(f"skipped 05_equity_curves.png: {FULL_PATH.name} not present")
        return None

    full = json.loads(FULL_PATH.read_text())
    same_window_arms = ["A1", "B-price"]
    fig, ax = S.new_figure(
        "A dollar traded on the forecast grew less than a dollar left alone",
        f"Middle ticker of {len([c for c in full['A1']['per_ticker_seed'] if c['seed'] == 0])} on each day (median growth of $1), seed 0, next-open fills",
    )
    for arm in same_window_arms:
        cells = [c for c in full[arm]["per_ticker_seed"] if c["seed"] == 0]
        cells.sort(key=lambda c: c["ticker"])
        n = len(cells[0]["M4"]["next_open"]["dates"])
        model_matrix = np.array([c["M4"]["next_open"]["model_daily_returns"] for c in cells])
        model_curve = np.median(np.cumprod(1 + model_matrix, axis=1), axis=0)
        first_day, last_day = cells[0]["M4"]["next_open"]["dates"][0][:10], cells[0]["M4"]["next_open"]["dates"][-1][:10]
        ax.plot(np.arange(n), model_curve, color=ARM_COLOR[arm], linewidth=2.6, label=ARM_LABEL[arm], zorder=3)

    bh_matrix = np.array([
        c["M4"]["next_open"]["bh_daily_returns"]
        for c in sorted((c for c in full["A1"]["per_ticker_seed"] if c["seed"] == 0), key=lambda c: c["ticker"])
    ])
    bh_curve = np.median(np.cumprod(1 + bh_matrix, axis=1), axis=0)
    ax.plot(np.arange(len(bh_curve)), bh_curve, color=S.BENCHMARK, linewidth=2.6, linestyle="--",
            label="Bought and held", zorder=3)

    ax.set_xlabel(f"Trading day in test segment, {first_day} → {last_day}")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    S.stamp(fig, "SEED 0 OF 3 — ONE RUN PER ARM")

    S.footer(
        fig,
        "C01_lstm_predicts_price/out/results_full.json",
        "per-day median across tickers of cumprod(1 + M4.next_open daily returns) · median, because one ticker's hold return is far above the rest",
    )
    return S.save(fig, CHART_DIR / "05_equity_curves.png")


def main() -> None:
    S.apply()
    required = (
        chart_01_error_ratio,
        chart_02_direction_hit_rate,
        chart_03_traded_vs_holding,
        chart_04_tracks_tomorrow,
    )
    for chart in required:
        print("wrote", chart().relative_to(CLAIM_DIR.parent))

    optional_path = chart_05_equity_curves()
    if optional_path is not None:
        print("wrote", optional_path.relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
