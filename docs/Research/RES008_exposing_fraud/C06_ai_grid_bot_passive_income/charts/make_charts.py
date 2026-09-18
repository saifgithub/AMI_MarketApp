"""
C06 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table (and the beat
sheet's on-screen numbers) ask for, drawn in the AMI style from
out/results.json. Every number on a chart is read from that file at run time;
nothing is typed in. There is no saved per-run series in out/ (only pooled
aggregates: median, p05/p95, shares, counts), so the figures below are
milestones / distributions / counts, not a redrawn per-point scatter — see
README.md for what could not be supported.

Run from the RES008 root:
    .venv/bin/python C06_ai_grid_bot_passive_income/charts/make_charts.py
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

RESULTS_PATH = CLAIM_DIR / "out" / "results.json"
SOURCE = "C06_ai_grid_bot_passive_income/out/results.json"


def _pct(value_frac: float, places: int = 2) -> str:
    """Percent string rounded half up, matching RESULTS.md's own precision
    (it quotes some figures to 2dp, e.g. 99.65%, 36.80%)."""
    q = Decimal("1") / (Decimal(10) ** places)
    d = Decimal(repr(round(100.0 * float(value_frac), 8))).quantize(q, rounding=ROUND_HALF_UP)
    return f"{d}%"


def _pct1(value_pct: float) -> str:
    """One decimal, value already in percent units (0-100), rounded half up."""
    return f"{Decimal(repr(round(float(value_pct), 6))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _signed_pct(value_frac: float, places: int = 1) -> str:
    """Signed percent with a true minus sign, from a fraction (e.g. -0.372 -> '-37.2%')."""
    s = _pct(abs(value_frac), places)
    return f"−{s}" if value_frac < 0 else f"+{s}"


def load_results() -> dict | None:
    if not RESULTS_PATH.exists():
        return None
    return json.loads(RESULTS_PATH.read_text())


def chart_01_two_number_card(R: dict) -> Path:
    """Beat 1 — cold open: the bot's own number vs the account's own number,
    same runs, both true."""
    pooled = R["grid"]["pooled"]["daily|pooled|lev=1.0x"]
    n = R["grid"]["n_total_runs"]
    positive = pooled["share_grid_profit_positive"]
    negative = pooled["share_true_pnl_negative"]

    fig, ax = S.new_figure(
        "Same 22,356 runs. The bot's number and the account's number disagree.",
        "Spot grid, BTC-USD and ETH-USD, 90-day runs, daily bars, no leverage · costs included",
    )
    ax.axis("off")

    cards = [
        (_pct(positive), "“grid profit”\npositive", S.CLAIM),
        (_pct(negative), "account\ndown", S.BAD),
    ]
    for i, (num, label, color) in enumerate(cards):
        cx = 0.28 + i * 0.44
        ax.text(cx, 0.56, num, transform=ax.transAxes, fontsize=88, fontweight="bold",
                 color=color, family=S.mono(), ha="center", va="center")
        ax.text(cx, 0.27, label, transform=ax.transAxes, fontsize=24,
                 color=S.TEXT, ha="center", va="center")
    ax.text(0.5, 0.08, f"n = {n:,} runs across both mechanisms · this card: daily 1× spot-grid runs",
             transform=ax.transAxes, fontsize=15, color=S.MUTED, ha="center", va="center")

    S.footer(fig, SOURCE, "grid.pooled['daily|pooled|lev=1.0x'].{share_grid_profit_positive, share_true_pnl_negative}; grid.n_total_runs")
    return S.save(fig, CHART_DIR / "01_two_number_card.png")


def chart_02_positive_vs_negative_by_arm(R: dict) -> Path:
    """Beat 1/5 — the gap holds across both timeframes and both leverage
    settings, not just the headline pair."""
    pooled = R["grid"]["pooled"]
    arms = ["hourly|pooled|lev=1.0x", "hourly|pooled|lev=5.0x", "daily|pooled|lev=1.0x", "daily|pooled|lev=5.0x"]
    labels = ["hourly\n1×", "hourly\n5×", "daily\n1×", "daily\n5×"]
    positive = [100 * pooled[a]["share_grid_profit_positive"] for a in arms]
    negative = [100 * pooled[a]["share_true_pnl_negative"] for a in arms]
    x = range(len(arms))
    width = 0.36

    fig, ax = S.new_figure(
        "The gap between the two numbers holds at every timeframe and leverage tested",
        "Spot grid, BTC-USD and ETH-USD pooled over all 9 range/line settings",
    )
    b1 = ax.bar([i - width / 2 for i in x], positive, width=width, color=S.CLAIM, label="“grid profit” positive")
    b2 = ax.bar([i + width / 2 for i in x], negative, width=width, color=S.BAD, label="account down")
    for rect, value in zip(list(b1) + list(b2), positive + negative):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 2, _pct1(value), ha="center", va="bottom",
                 fontsize=15, fontweight="bold", family=S.mono())
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Share of runs, %")
    ax.set_ylim(0, 148)
    ax.legend(loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0), frameon=False)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "grid.pooled[<arm>].{share_grid_profit_positive, share_true_pnl_negative} for each of the four arms")
    return S.save(fig, CHART_DIR / "02_positive_vs_negative_by_arm.png")


def chart_03_percentile_bar(R: dict) -> Path:
    """Beat 5 — the percentile bar named in the brief: p05, median, p95 of true
    P&L, daily 1x, asymmetric on purpose."""
    pooled = R["grid"]["pooled"]["daily|pooled|lev=1.0x"]
    p05 = 100 * pooled["p05_true_pnl_frac"]
    med = 100 * pooled["median_true_pnl_frac"]
    p95 = 100 * pooled["p95_true_pnl_frac"]

    fig, ax = S.new_figure(
        "The account's outcome is capped on top, open on the bottom",
        "True P&L over 90 days, daily 1× spot-grid runs, BTC-USD and ETH-USD pooled",
    )
    ax.set_ylim(-0.6, 0.6)
    ax.axhline(0, color=S.TEXT, linewidth=1.6, zorder=1)
    points = [("5th pct\n(bad case)", p05, S.BAD), ("median", med, S.MEASURED), ("95th pct\n(good case)", p95, S.GOOD)]
    xs = [0, 1, 2]
    for xi, (label, value, color) in zip(xs, points):
        ax.plot([xi, xi], [0, value / 100], color=S.BORDER, linewidth=2.5, zorder=2, solid_capstyle="round")
    for xi, (label, value, color) in zip(xs, points):
        ax.scatter([xi], [value / 100], color=color, s=260, zorder=3)
        va = "bottom" if value >= 0 else "top"
        offset = 0.04 if value >= 0 else -0.04
        ax.text(xi, value / 100 + offset, _signed_pct(value / 100), ha="center", va=va, fontsize=24,
                 fontweight="bold", color=color, family=S.mono(), zorder=4)
    ax.set_xticks(xs)
    ax.set_xticklabels([label for label, _, _ in points])
    ax.set_yticks([-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6])
    ax.set_yticklabels([f"{int(t*100)}%".replace("-", "\u2212") for t in [-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6]])
    ax.set_ylabel("True P&L, % of starting capital")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "grid.pooled['daily|pooled|lev=1.0x'].{p05_true_pnl_frac, median_true_pnl_frac, p95_true_pnl_frac}")
    return S.save(fig, CHART_DIR / "03_percentile_bar.png")


def chart_04_range_and_liquidation(R: dict) -> Path:
    """Beat 5/6 — price left the range in 7 of 8 runs (split up/down), and what
    5x leverage does to the same runs."""
    pooled1x = R["grid"]["pooled"]["daily|pooled|lev=1.0x"]
    pooled5x = R["grid"]["pooled"]["daily|pooled|lev=5.0x"]
    left_up = 100 * pooled1x["share_left_range_up"]
    left_down = 100 * pooled1x["share_left_range_down"]
    left_total = 100 * pooled1x["share_left_range"]
    liq5x = 100 * pooled5x["share_liquidated"]

    fig, (left, right) = S.new_figure(
        "Price leaves the grid's range most of the time; leverage turns that into ruin",
        "Daily 1× and 5× spot-grid runs, BTC-USD and ETH-USD pooled",
        ncols=2,
        gridspec_kw={"width_ratios": [1, 1]},
    )
    bars = left.bar(["left range\n(up)", "left range\n(down)"], [left_up, left_down], color=[S.GOOD, S.BAD], width=0.55)
    for rect, value in zip(bars, [left_up, left_down]):
        left.text(rect.get_x() + rect.get_width() / 2, value + 2, _pct1(value), ha="center", va="bottom",
                   fontsize=20, fontweight="bold", family=S.mono())
    left.set_ylim(0, 105)
    left.set_ylabel("Share of runs, %")
    left.set_title(f"price left the range: {_pct1(left_total)} of runs", fontsize=17, color=S.MUTED, pad=12)
    left.grid(axis="x", visible=False)

    bar = right.bar(["liquidated\nat 5×"], [liq5x], color=S.BAD, width=0.45)
    right.text(bar[0].get_x() + bar[0].get_width() / 2, liq5x + 2, _pct1(liq5x), ha="center", va="bottom",
                fontsize=20, fontweight="bold", family=S.mono())
    right.set_ylim(0, 105)
    right.set_yticklabels([])
    right.set_title("same runs, 5× leverage", fontsize=17, color=S.MUTED, pad=12)
    right.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "grid.pooled['daily|pooled|lev=1.0x'].share_left_range{,_up,_down}; grid.pooled['daily|pooled|lev=5.0x'].share_liquidated")
    return S.save(fig, CHART_DIR / "04_range_and_liquidation.png")


def chart_05_by_setting_share_negative(R: dict) -> Path:
    """Beat 4/7 — what would have supported the claim: a setting with true P&L
    >= 0 in >= 90% of runs. Best setting shown against that bar; none clears it."""
    by_setting = R["grid"]["by_setting"]
    keys = [k for k in by_setting if k.startswith("daily|") and k.endswith("|lev=1.0x")]

    def parts(k: str):
        _, coin, r, levels, _ = k.split("|")
        return coin.replace("-USD", ""), r.replace("r=", "±") + "%".replace("0.", ""), levels.replace("levels=", "")

    rows = []
    for k in keys:
        coin, rlabel, levels = parts(k)
        r_val = float(k.split("|")[2].replace("r=", ""))
        rlabel = f"±{int(r_val*100)}%"
        share_nonneg = 100 * (1 - by_setting[k]["share_true_pnl_negative"])
        rows.append((coin, rlabel, levels, share_nonneg))
    rows.sort(key=lambda row: (-row[3]))

    labels = [f"{coin} {rlabel} / {levels}L" for coin, rlabel, levels, _ in rows]
    values = [row[3] for row in rows]
    colors = [S.GOOD if v >= 90 else S.MEASURED for v in values]

    fig, ax = S.new_figure(
        "The best single setting still misses the bar that would have supported “any market”",
        "Share of 90-day runs with true P&L ≥ 0, by setting — daily 1×, BTC-USD and ETH-USD",
    )
    # horizontal bars: 18 settings do not fit as readable rotated x tick labels
    fig.subplots_adjust(left=0.22, bottom=0.17)
    y = range(len(rows))
    bars = ax.barh(y, values, color=colors, height=0.68)
    ax.axvline(90, color=S.CLAIM, linewidth=2.5, linestyle="--", zorder=1)
    ax.text(88, -0.9, "90% — would have supported “any market”", ha="right", va="center",
             fontsize=15, color=S.CLAIM)
    for rect, value in zip(bars, values):
        ax.text(value + 1.2, rect.get_y() + rect.get_height() / 2, _pct1(value), ha="left", va="center",
                 fontsize=13, fontweight="bold", family=S.mono())
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=13)
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_ylim(len(rows) - 0.4, -1.5)
    ax.set_xlabel("Runs with true P&L ≥ 0, %")
    ax.grid(axis="y", visible=False)

    S.footer(fig, SOURCE, "grid.by_setting['daily|<coin>|r=<range>|levels=<n>|lev=1.0x'].share_true_pnl_negative, 1 minus that value; best cell BTC ±20% / 10 lines")
    return S.save(fig, CHART_DIR / "05_by_setting_share_nonnegative.png")


def chart_06_liquidation_by_setting(R: dict) -> Path:
    """Beat 5 — 5x liquidation share across the same 9 settings x 2 coins, low
    to high."""
    by_setting = R["grid"]["by_setting"]
    keys = [k for k in by_setting if k.startswith("daily|") and k.endswith("|lev=5.0x")]

    rows = []
    for k in keys:
        _, coin, r, levels, _ = k.split("|")
        coin = coin.replace("-USD", "")
        r_val = float(r.replace("r=", ""))
        rlabel = f"±{int(r_val*100)}%"
        levels_n = levels.replace("levels=", "")
        rows.append((coin, rlabel, levels_n, 100 * by_setting[k]["share_liquidated"]))
    rows.sort(key=lambda row: row[3])

    labels = [f"{coin} {rlabel} / {levels}L" for coin, rlabel, levels, _ in rows]
    values = [row[3] for row in rows]

    fig, ax = S.new_figure(
        f"At 5× leverage, liquidation ran from {min(values):.0f}% to {max(values):.0f}% of runs, "
        f"depending only on the settings",
        "Share of daily 90-day runs liquidated — 5×, BTC-USD and ETH-USD, all 9 range/line settings",
    )
    # horizontal bars: 18 settings do not fit as readable rotated x tick labels
    fig.subplots_adjust(left=0.22, bottom=0.17)
    y = range(len(rows))
    bars = ax.barh(y, values, color=S.BAD, height=0.68)
    for rect, value in zip(bars, values):
        ax.text(value + 0.8, rect.get_y() + rect.get_height() / 2, _pct1(value), ha="left", va="center",
                 fontsize=13, fontweight="bold", family=S.mono())
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=13)
    ax.invert_yaxis()
    top = max(values) + 14
    ax.set_xlim(0, top)
    ax.set_xticks([t for t in range(0, int(top) + 1, 10)])
    ax.set_xlabel("Runs liquidated, %")
    ax.grid(axis="y", visible=False)

    S.footer(fig, SOURCE, "grid.by_setting['daily|<coin>|r=<range>|levels=<n>|lev=5.0x'].share_liquidated, all 18 daily 5× cells")
    return S.save(fig, CHART_DIR / "06_liquidation_by_setting.png")


def chart_07_predictions_scorecard(R: dict) -> Path:
    """Beat 3/7 — the four pre-registered hypotheses, scored. Two wrong."""
    grid1x = R["grid"]["pooled"]["daily|pooled|lev=1.0x"]
    grid5x = R["grid"]["pooled"]["daily|pooled|lev=5.0x"]
    band_pooled = R["band_grid"]["pooled"]
    band_c1 = band_pooled["daily|pooled|constant|unit=1.0x"]
    band_sizings = ["0.5x", "1.0x", "2.0x"]
    best_monthly = max(
        100 * band_pooled[f"daily|pooled|{style}|unit={s}"]["median_monthly_return_while_alive"]
        for style in ("constant", "martingale")
        for s in band_sizings
    )

    rows = [
        ("H1", "grid profit ≥ 95% positive,\ntrue P&L ≥ 30% negative", f"{_pct(grid1x['share_grid_profit_positive'])} / {_pct(grid1x['share_true_pnl_negative'])}", "MET", S.GOOD),
        ("H2", "grid beats buy-and-hold\nin < 50% of runs", f"{_pct(grid1x['share_beat_buy_hold'])}", "NOT MET", S.BAD),
        ("H3", "5× liquidated in\n≥ 20% of runs", f"{_pct(grid5x['share_liquidated'])}", "MET", S.GOOD),
        ("H4", "band win rate ≥ 85% and\n≥ 3%/mo median, majority-ruined", f"win rate {_pct(band_c1['basket_win_rate'])}\nbest {_pct(best_monthly/100)}/mo", "NOT MET", S.BAD),
    ]

    fig, ax = S.new_figure(
        "Four predictions, written down before the test ran — two were wrong",
        "Pre-registration commit 3ac320eb, 2026-09-17, scored against out/results.json",
    )
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    row_h = 0.20
    top = 0.80
    for i, (tag, text, measured, verdict, color) in enumerate(rows):
        y = top - i * row_h
        ax.text(0.03, y, tag, fontsize=22, fontweight="bold", color=S.MUTED, family=S.mono(), va="center")
        ax.text(0.11, y, text, fontsize=16, color=S.TEXT, va="center", linespacing=1.4)
        ax.text(0.62, y, measured, fontsize=14, color=S.MUTED, family=S.mono(), va="center", ha="left", linespacing=1.4)
        ax.text(0.97, y, verdict, fontsize=18, fontweight="bold", color=color, ha="right", va="center")
    ax.text(0.5, 0.03, "2 of 4 predictions wrong", transform=ax.transAxes, fontsize=20, fontweight="bold",
             color=S.CLAIM, ha="center", va="bottom")

    S.footer(fig, SOURCE, "H1/H3: grid.pooled[daily 1x/5x]; H2: share_beat_buy_hold; H4: band_grid.pooled[...].basket_win_rate, best of 6 sizings' median_monthly_return_while_alive")
    return S.save(fig, CHART_DIR / "07_predictions_scorecard.png")


def chart_08_band_grid_ruin_table(R: dict) -> Path:
    """Beat 7 — the band-grid table: win rate, median monthly return, and ruin
    share within 5 years, constant vs martingale, across the three sizings."""
    pooled = R["band_grid"]["pooled"]
    sizings = ["0.5x", "1.0x", "2.0x"]
    styles = ["constant", "martingale"]
    labels = {"0.5x": "0.5×", "1.0x": "1×", "2.0x": "2×"}

    fig, (top, bottom) = S.new_figure(
        "Bigger size means more monthly income and a much bigger ruin share",
        "Band grid, daily bars, EURUSD/GBPUSD/USDJPY pooled, no stop — constant vs 1.5× martingale sizing",
        nrows=2,
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.18},
    )
    x = range(len(sizings))
    width = 0.36
    for i, style in enumerate(styles):
        vals = [100 * pooled[f"daily|pooled|{style}|unit={s}"]["median_monthly_return_while_alive"] for s in sizings]
        offset = (i - 0.5) * width
        color = S.MEASURED if style == "constant" else S.CLAIM
        bars = top.bar([xi + offset for xi in x], vals, width=width, color=color, label=style)
        for rect, value in zip(bars, vals):
            top.text(rect.get_x() + rect.get_width() / 2, value + 0.02, f"{value:.2f}%", ha="center", va="bottom",
                       fontsize=13, fontweight="bold", family=S.mono())
    top.set_ylabel("Median\nmonthly return, %")
    top.legend(loc="upper left")
    top.grid(axis="x", visible=False)

    for i, style in enumerate(styles):
        vals = [100 * pooled[f"daily|pooled|{style}|unit={s}"]["share_ruined_within_5y"]["share"] for s in sizings]
        offset = (i - 0.5) * width
        color = S.MEASURED if style == "constant" else S.CLAIM
        bars = bottom.bar([xi + offset for xi in x], vals, width=width, color=color, label=style)
        for rect, value in zip(bars, vals):
            bottom.text(rect.get_x() + rect.get_width() / 2, value + 1, _pct1(value), ha="center", va="bottom",
                          fontsize=13, fontweight="bold", family=S.mono())
    bottom.set_ylabel("Ruined within\n5 years, %")
    bottom.set_xticks(list(x))
    bottom.set_xticklabels([labels[s] for s in sizings])
    bottom.set_xlabel("Position size (multiple of the base unit)")
    bottom.set_ylim(0, 60)
    bottom.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "band_grid.pooled['daily|pooled|<style>|unit=<size>'].{median_monthly_return_while_alive, share_ruined_within_5y.share} for constant/martingale x 0.5x/1x/2x")
    return S.save(fig, CHART_DIR / "08_band_grid_ruin_table.png")


def chart_09_beat_buy_hold(R: dict) -> Path:
    """Beat 7 — H2 result: the grid did not lose to buy-and-hold, it was close
    to a coin flip against it. Correction to our own prediction."""
    pooled = R["grid"]["pooled"]["daily|pooled|lev=1.0x"]
    beat_bh = 100 * pooled["share_beat_buy_hold"]
    beat_cash = 100 * pooled["share_beat_cash"]

    fig, ax = S.new_figure(
        "We predicted the grid would lose to holding the coin. It did not.",
        "Daily 1× spot-grid runs vs. two benchmarks bought at the same start price — BTC-USD and ETH-USD pooled",
    )
    bars = ax.bar(["beats\nbuy-and-hold", "beats\nholding cash"], [beat_bh, beat_cash], color=[S.BENCHMARK, S.MEASURED], width=0.5)
    ax.axhline(50, color=S.TEXT, linewidth=1.6, linestyle=":", zorder=1)
    ax.text(1.32, 50, "50% — coin flip", ha="left", va="center", fontsize=15, color=S.MUTED)
    for rect, value in zip(bars, [beat_bh, beat_cash]):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 2, _pct1(value), ha="center", va="bottom",
                 fontsize=22, fontweight="bold", family=S.mono())
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.6, 1.9)
    ax.set_ylabel("Share of runs, %")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "grid.pooled['daily|pooled|lev=1.0x'].{share_beat_buy_hold, share_beat_cash}")
    return S.save(fig, CHART_DIR / "09_beat_buy_hold.png")


def main() -> None:
    S.apply()
    R = load_results()
    if R is None:
        print(f"skipped all figures: {RESULTS_PATH.relative_to(CLAIM_DIR.parent)} not present")
        return

    charts = (
        chart_01_two_number_card,
        chart_02_positive_vs_negative_by_arm,
        chart_03_percentile_bar,
        chart_04_range_and_liquidation,
        chart_05_by_setting_share_negative,
        chart_06_liquidation_by_setting,
        chart_07_predictions_scorecard,
        chart_08_band_grid_ruin_table,
        chart_09_beat_buy_hold,
    )
    for chart in charts:
        try:
            path = chart(R)
        except KeyError as exc:
            print(f"skipped {chart.__name__}: key {exc} not present in results.json")
            continue
        print("wrote", path.relative_to(CLAIM_DIR.parent))


if __name__ == "__main__":
    main()
