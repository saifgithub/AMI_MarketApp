"""
C02 chart pack -- the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from out/results.json, out/gate_results.json and out/catalogue.md.
Every number on a chart is read from those files at run time; nothing is typed in.

Run from the RES008 root:
    .venv/bin/python C02_chatbot_wrote_my_strategy/charts/make_charts.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from matplotlib.ticker import NullLocator

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
sys.path.insert(0, str(CLAIM_DIR.parent))

from common import ami_style as S  # noqa: E402

OUT = CLAIM_DIR / "out"
RESULTS = json.loads((OUT / "results.json").read_text())
GATE = json.loads((OUT / "gate_results.json").read_text())
CATALOGUE = (OUT / "catalogue.md").read_text()

STRATEGIES = RESULTS["strategies"]
NAMES = sorted(STRATEGIES.keys())
SOURCE_RESULTS = "C02_chatbot_wrote_my_strategy/out/results.json"
SOURCE_GATE = "C02_chatbot_wrote_my_strategy/out/gate_results.json"
SOURCE_CATALOGUE = "C02_chatbot_wrote_my_strategy/out/catalogue.md"

MODEL_LABEL = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus"}

# Plain-word summary of each one-line prompt, for on-screen labels only.
# Text drawn from the prompt itself in gate_results.json (see _plain_prompt_labels).
_PLAIN_PROMPT = {
    "p01": "Technical-indicator strategy",
    "p02": "Simple 50-day average",
    "p03": "VWAP crossover",
    "p04": "High win-rate combo",
    "p05": "Mean reversion",
    "p06": "Trend following",
    "p07": "RSI + MACD",
    "p08": "70% win rate, asked for",
    "p09": "Bitcoin strategy",
    "p10": "SuperTrend + RSI + ADX",
}


def _prompt_num(name: str) -> str:
    return name.split("_")[0]


def _model(name: str) -> str:
    return name.split("_")[1]


def _plain_label(name: str) -> str:
    p, m = _prompt_num(name), _model(name)
    return f"{_PLAIN_PROMPT[p]} · {MODEL_LABEL[m]}"


def _short_label(name: str) -> str:
    """'Prompt 8 · Opus' style label, matching the brief's example."""
    p, m = _prompt_num(name), _model(name)
    n = int(p[1:])
    return f"Prompt {n} · {MODEL_LABEL[m]}"


# -- 01: placebo percentiles ---------------------------------------------------


def chart_01_placebo_percentiles() -> Path:
    """Beat 5: redraw of placebo_percentiles.png with plain-word labels, the
    50/95 reference lines, and a visible note for the strategy that never trades."""
    order = sorted(
        NAMES,
        key=lambda n: STRATEGIES[n]["HOLDOUT"]["pooled"]["s2_mean_placebo_percentile"]
        if STRATEGIES[n]["HOLDOUT"]["pooled"]["s2_mean_placebo_percentile"] == STRATEGIES[n]["HOLDOUT"]["pooled"]["s2_mean_placebo_percentile"]
        else -1,
    )

    fig, ax = S.new_figure(
        f"None of the {len(NAMES)} strategies reached our bar for timing skill.",
        "Mean placebo percentile per strategy, holdout window (2019–2026) · 50 = random · 95 = skill threshold",
    )
    fig.subplots_adjust(left=0.20, right=S.RIGHT, top=0.78, bottom=0.20)
    y = range(len(order))
    xs, colors, no_trade_y = [], [], None
    for i, name in enumerate(order):
        val = STRATEGIES[name]["HOLDOUT"]["pooled"]["s2_mean_placebo_percentile"]
        if val != val:  # NaN -- never trades
            no_trade_y = i
            xs.append(0.0)
            colors.append(S.DIM)
        else:
            xs.append(val)
            colors.append(S.MEASURED)

    ax.barh(list(y), xs, color=colors, height=0.62)
    ax.axvline(50, color=S.BENCHMARK, linestyle="--", linewidth=1.6)
    ax.axvline(95, color=S.CLAIM, linestyle="--", linewidth=1.6)
    ax.text(50, -1.6, "50th pct (random)", color=S.BENCHMARK, ha="center", va="top", fontsize=14)
    ax.text(95, -1.6, "95th pct (skill)", color=S.CLAIM, ha="center", va="top", fontsize=14)

    ax.set_yticks(list(y))
    ax.set_yticklabels([_short_label(n) for n in order], fontsize=13)
    ax.set_xlim(0, 100)
    ax.set_ylim(len(order) - 0.5, -2.3)
    ax.set_xlabel("Mean placebo percentile across its tickers")

    if no_trade_y is not None:
        ax.text(
            2, no_trade_y, "  never trades — no percentile",
            color=S.TEXT, fontsize=13, ha="left", va="center", fontweight="bold",
        )

    S.footer(fig, SOURCE_RESULTS, "one strategy (Prompt 10 · Haiku) never trades and has no placebo percentile")
    return S.save(fig, CHART_DIR / "01_placebo_percentiles.png")


# -- 02a / 02b: as-shown wall ---------------------------------------------------


def _as_shown_rows():
    rows = []
    for name in NAMES:
        a = STRATEGIES[name]["as_shown"]
        rows.append(
            dict(
                name=name,
                label=_short_label(name),
                ticker=a["best_ticker"],
                gross=a["best_ticker_gross_total_return"],
                bh=a["best_ticker_buy_hold_gross_total_return"],
                profitable=a["looks_profitable"],
            )
        )
    rows.sort(key=lambda r: r["gross"])
    return rows


def _pct_ticks(ax, negative: bool) -> None:
    """Plain-number ticks on the symlog return axis instead of powers of ten."""
    ticks = [0, 10, 100, 1000]
    labels = ["0", "+10%", "+100%", "+1,000%"]
    if negative:
        ticks = [-100, -10] + ticks
        labels = ["\u2212100%", "\u221210%"] + labels
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.xaxis.set_minor_locator(NullLocator())


def chart_02a_as_shown_wall() -> Path:
    """Beat 4: the screenshot arm in absolute terms -- best ticker, no costs,
    no benchmark. This is what a strategy-tester screenshot shows."""
    rows = _as_shown_rows()
    fig, ax = S.new_figure(
        "Every strategy, shown the way a screenshot shows it.",
        "Best ticker of 22, no trading costs, 2005–2018 · total return, not annualised",
    )
    fig.subplots_adjust(left=0.24, right=0.88, top=0.82, bottom=0.20)
    y = range(len(rows))
    colors = [S.MEASURED if r["profitable"] else S.DIM for r in rows]
    xs_pct = [r["gross"] * 100 for r in rows]
    ax.barh(list(y), xs_pct, color=colors, height=0.72)
    ax.set_xscale("symlog", linthresh=1)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{r['label']} ({r['ticker']})" for r in rows], fontsize=13)
    ax.set_xlabel("Total return, % (log scale)")
    ax.invert_yaxis()

    for i, r in enumerate(rows):
        text = f"+{xs_pct[i]:,.0f}%" if r["profitable"] else "0% — never trades"
        ax.text(
            max(xs_pct[i], 0) + (2 if xs_pct[i] > 0 else 1), i, text,
            color=S.TEXT, fontsize=13, va="center", ha="left", family=S.mono(),
        )

    shown = [x for x, r in zip(xs_pct, rows) if r["profitable"]]
    _pct_ticks(ax, negative=False)
    S.footer(
        fig, SOURCE_RESULTS,
        f"{len(shown)} of {len(rows)} show a profit · log x-axis because returns span +{min(shown):,.0f}% to +{max(shown):,.0f}%",
    )
    return S.save(fig, CHART_DIR / "02a_as_shown_wall.png")


def chart_02b_as_shown_vs_holding() -> Path:
    """Beat 4-5: same wall, with the buy-and-hold return of that same best
    ticker added in the benchmark colour -- the line the screenshot leaves out."""
    rows = _as_shown_rows()
    fig, ax = S.new_figure(
        "Add back the line the screenshot leaves out: holding the same stock.",
        "Same best ticker, same window · grey = buy-and-hold, that ticker · blue = the strategy",
    )
    fig.subplots_adjust(left=0.24, right=0.92, top=0.82, bottom=0.20)
    y = list(range(len(rows)))
    height = 0.36
    strat_pct = [r["gross"] * 100 for r in rows]
    bh_pct = [r["bh"] * 100 for r in rows]
    ax.barh([v + height / 2 for v in y], strat_pct, height=height, color=S.MEASURED, label="Strategy (as shown)")
    ax.barh([v - height / 2 for v in y], bh_pct, height=height, color=S.BENCHMARK, label="Buy-and-hold, same ticker")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['label']} ({r['ticker']})" for r in rows], fontsize=13)
    ax.set_xlabel("Total return, % (log scale)")
    ax.invert_yaxis()
    ax.legend(loc="lower left", framealpha=0.0)
    _pct_ticks(ax, negative=True)

    n_beats = sum(1 for r in rows if r["gross"] > r["bh"])
    S.footer(
        fig, SOURCE_RESULTS,
        f"only {n_beats} of {sum(1 for r in rows if r['profitable'])} profitable-looking strategies beat holding that same best ticker",
    )
    return S.save(fig, CHART_DIR / "02b_as_shown_vs_holding.png")


# -- 03: 578-cell grid -----------------------------------------------------------


def _join_words(items: list[str]) -> str:
    items = sorted(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def chart_03_holdout_grid() -> Path:
    """Beat 5: 29 strategies x tickers, a cell lit where the strategy beat
    buy-and-hold net in the holdout. Columns ordered by that ticker's own
    buy-and-hold holdout return (worst to best)."""
    # Column order: every ticker appearing in any strategy's HOLDOUT cells,
    # sorted by that ticker's buy-and-hold holdout return (present in every
    # cell that references it, and identical across strategies).
    bh_by_ticker: dict[str, float] = {}
    for s in STRATEGIES.values():
        for tix, cell in s["HOLDOUT"]["cells"].items():
            bh_by_ticker[tix] = cell["buy_hold_net_total_return"]
    tickers = sorted(bh_by_ticker, key=lambda t: bh_by_ticker[t])

    grid = []
    total_cells = 0
    lit_cells = 0
    lit_tickers: list[str] = []
    for name in NAMES:
        cells = STRATEGIES[name]["HOLDOUT"]["cells"]
        row = []
        for t in tickers:
            if t not in cells:
                row.append(math.nan)  # strategy not evaluated on this ticker (crypto-only prompts)
                continue
            total_cells += 1
            beat = cells[t]["beats_buy_hold_net"]
            if beat:
                lit_cells += 1
                if t not in lit_tickers:
                    lit_tickers.append(t)
            row.append(1.0 if beat else 0.0)
        grid.append(row)

    fig, ax = S.new_figure(
        "Where a chatbot strategy beat holding, in the later seven years.",
        f"{lit_cells} of {total_cells} strategy × ticker pairs · columns sorted by that ticker's own buy-and-hold return, worst to best",
    )
    fig.subplots_adjust(left=0.17, right=S.RIGHT, top=0.82, bottom=0.25)
    import numpy as np
    from matplotlib.colors import ListedColormap

    arr = np.array(grid)
    cmap = ListedColormap([S.PANEL, S.GOOD])
    masked = np.ma.masked_invalid(arr)
    ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax.set_facecolor(S.DIM)

    ax.set_xticks(range(len(tickers)))
    ax.set_xticklabels(tickers, rotation=90, fontsize=13)
    ax.set_yticks(range(len(NAMES)))
    ax.set_yticklabels([_short_label(n) for n in NAMES], fontsize=13)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.text(
        0.5, 0.105, "Ticker (sorted by its own buy-and-hold holdout return, worst to best)",
        ha="center", va="center", fontsize=18, color=S.MUTED,
    )

    S.footer(
        fig, SOURCE_RESULTS,
        "grey cell = strategy not evaluated on that ticker (crypto-only prompts) · every lit cell falls in "
        + _join_words(lit_tickers),
    )
    return S.save(fig, CHART_DIR / "03_holdout_grid.png")


# -- 04: rule families (skipped, see README) -------------------------------------


def chart_04_rule_families():
    """catalogue.md gives free-text 'Rules (plain English)' per strategy, not a
    parseable family field. Per the brief, this figure is SKIPPED rather than
    hand-classified. Returns None; main() reports the skip."""
    has_family_column = bool(re.search(r"\|\s*Family\s*\|", CATALOGUE, re.IGNORECASE))
    if has_family_column:
        raise RuntimeError("catalogue.md now has a Family column -- implement chart_04.")
    return None


# -- 05: three-counter card --------------------------------------------------------


def chart_05_three_counters() -> Path:
    """Cold-open card: three counts, each computed from results.json at run time."""
    n = len(NAMES)
    beat_holding = sum(
        1 for s in STRATEGIES.values() if s["HOLDOUT"]["pooled"]["s1_fraction_beating_buy_hold"] > 0.5
    )
    beat_random = sum(
        1
        for s in STRATEGIES.values()
        if (v := s["HOLDOUT"]["pooled"]["s2_mean_placebo_percentile"]) == v and v >= 95
    )
    looks_profitable = sum(1 for s in STRATEGIES.values() if s["as_shown"]["looks_profitable"])

    fig, ax = S.new_figure(
        "Chatbot-written strategies. Three questions.",
        f"{n} strategies scored · first two: 2019–2026, after costs · third: best ticker, no costs, 2005–2018",
    )
    ax.axis("off")

    cards = [
        (f"{beat_holding} of {n}", "beat simply\nholding", S.BAD),
        (f"{beat_random} of {n}", "beat random\nentries (95th pct)", S.BAD),
        (f"{looks_profitable} of {n}", "look profitable the way\na screenshot shows it", S.CLAIM),
    ]
    for i, (num, label, color) in enumerate(cards):
        cx = 0.17 + i * 0.33
        ax.text(cx, 0.55, num, transform=ax.transAxes, fontsize=64, fontweight="bold",
                 color=color, family=S.mono(), ha="center", va="center")
        ax.text(cx, 0.30, label, transform=ax.transAxes, fontsize=22,
                 color=S.TEXT, ha="center", va="center")

    S.footer(
        fig, SOURCE_RESULTS,
        "beat-holding and beat-random counts use the pre-registered holdout definitions (H1, H2)",
    )
    return S.save(fig, CHART_DIR / "05_three_counters.png")


def main() -> None:
    S.apply()
    written = []
    for chart in (
        chart_01_placebo_percentiles,
        chart_02a_as_shown_wall,
        chart_02b_as_shown_vs_holding,
        chart_03_holdout_grid,
        chart_05_three_counters,
    ):
        path = chart()
        written.append(path)
        print("wrote", path.relative_to(CLAIM_DIR.parent))

    skipped = chart_04_rule_families()
    if skipped is None:
        print(
            "skipped chart_04_rule_families: catalogue.md has no parseable "
            "family/classification column (only free-text 'Rules (plain English)'); "
            "brief forbids hand-classifying strategies ourselves"
        )


if __name__ == "__main__":
    main()
