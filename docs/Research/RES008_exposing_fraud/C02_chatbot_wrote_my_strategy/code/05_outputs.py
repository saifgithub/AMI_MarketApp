"""C02 step 4 — aggregate H1/H2/H3, write out/summary.txt, and render the two figures.

Reads out/results.json (written by 03_score.py) and out/gate_results.json, computes the
pre-registered aggregates exactly as PREREGISTRATION.md defines them, and writes:
  - out/summary.txt: H1-H3 + the two "what would support the claim" conditions, plus a 30-row table
  - out/placebo_percentiles.png: dot plot of each strategy's mean HOLDOUT placebo percentile
  - out/as_shown_vs_holdout.png: as-shown best-ticker gross return vs HOLDOUT net return, both
    relative to buy-and-hold, per strategy
Every number here traces back to out/results.json; nothing is computed independently of it.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

C02 = Path(__file__).resolve().parents[1]
RESULTS = json.loads((C02 / "out" / "results.json").read_text())
GATE = json.loads((C02 / "out" / "gate_results.json").read_text())

STRATS = RESULTS["strategies"]
NAMES = sorted(STRATS)


def s1_beats_majority(name: str, window: str) -> bool:
    pooled = STRATS[name][window]["pooled"]
    frac = pooled["s1_fraction_beating_buy_hold"]
    return frac is not None and not np.isnan(frac) and frac > 0.5


def mean_s2(name: str, window: str) -> float:
    return STRATS[name][window]["pooled"]["s2_mean_placebo_percentile"]


def as_shown_looks_profitable(name: str) -> bool | None:
    as_shown = STRATS[name]["as_shown"]
    if as_shown.get("best_ticker") is None:
        return None
    return as_shown["best_ticker_gross_total_return"] > 0.0


def main():
    n_total = len(NAMES)

    h1_count = sum(1 for n in NAMES if s1_beats_majority(n, "HOLDOUT"))
    h1_fraction = h1_count / n_total

    s2_values_holdout = [mean_s2(n, "HOLDOUT") for n in NAMES if not np.isnan(mean_s2(n, "HOLDOUT"))]
    h2_median_s2 = float(np.median(s2_values_holdout)) if s2_values_holdout else float("nan")
    h2_ge95_holdout = [n for n in NAMES if not np.isnan(mean_s2(n, "HOLDOUT")) and mean_s2(n, "HOLDOUT") >= 95.0]
    h2_ge95_holdout_alt_frac = {
        n: STRATS[n]["HOLDOUT"]["pooled"]["s2_fraction_tickers_ge_95th_percentile"] for n in NAMES
    }

    as_shown_flags = [as_shown_looks_profitable(n) for n in NAMES]
    as_shown_valid = [f for f in as_shown_flags if f is not None]
    h3_count = sum(1 for f in as_shown_valid if f)
    h3_fraction = h3_count / len(as_shown_valid) if as_shown_valid else float("nan")

    support_a_count = sum(1 for n in NAMES if s1_beats_majority(n, "HOLDOUT"))
    ge95_define = [n for n in NAMES if not np.isnan(mean_s2(n, "DEFINE")) and mean_s2(n, "DEFINE") >= 95.0]
    both_windows_ge95 = sorted(set(ge95_define) & set(h2_ge95_holdout))
    support_b_count = len(both_windows_ge95)

    h1_met = h1_count <= 6
    h2_median_met = 35.0 <= h2_median_s2 <= 65.0
    h2_count_met = len(h2_ge95_holdout) <= 3
    h3_met = h3_fraction >= 0.80

    support_a_met = support_a_count >= 15
    support_b_met = support_b_count >= 8
    verdict_supported = support_a_met or support_b_met

    lines = []
    lines.append("C02 -- 'A chatbot wrote me a profitable trading strategy' -- results summary")
    lines.append("")
    lines.append(f"Strategies scored: {n_total} of 30 generated (excluded at gate: "
                 f"{sum(1 for e in GATE['strategies'].values() if e['status'] == 'excluded')})")
    lines.append("")
    lines.append("=== H1 (worth doing?) ===")
    lines.append(f"H1 predicted: at most 6/30 (20%) strategies beat buy-and-hold net on HOLDOUT in "
                 f"more than half their tickers.")
    lines.append(f"Measured: {h1_count}/{n_total} ({h1_fraction:.1%}) beat buy-and-hold net on HOLDOUT "
                 f"in more than half their tickers.")
    lines.append(f"H1 met: {h1_met}")
    lines.append("")
    lines.append("=== H2 (any skill?) ===")
    lines.append(f"H2 predicted: median S2 (mean placebo percentile) across strategies in [35, 65] on "
                 f"HOLDOUT, and at most 3/30 strategies at/above the 95th placebo percentile "
                 f"(mean-percentile reading, pre-registered).")
    lines.append(f"Measured median S2 on HOLDOUT: {h2_median_s2:.1f}")
    lines.append(f"Measured count at/above 95th percentile (mean-percentile reading, PRE-REGISTERED) "
                 f"on HOLDOUT: {len(h2_ge95_holdout)}/{n_total} -- {h2_ge95_holdout}")
    lines.append(f"Alternative (looser/stricter) reading -- fraction of a strategy's OWN tickers at/above "
                 f"the 95th percentile, per strategy, on HOLDOUT: "
                 f"{ {n: round(f, 3) for n, f in h2_ge95_holdout_alt_frac.items() if f is not None} }")
    lines.append(f"H2 median-in-range met: {h2_median_met}; H2 count<=3 met (pre-registered mean reading): "
                 f"{h2_count_met}")
    lines.append("")
    lines.append("=== H3 (as-shown arm) ===")
    lines.append(f"H3 predicted: the as-shown arm looks profitable (best-ticker DEFINE gross total "
                 f"return > 0) for >= 80% of strategies.")
    lines.append(f"Measured: {h3_count}/{len(as_shown_valid)} ({h3_fraction:.1%}) look profitable "
                 f"as-shown.")
    n_beat_bh_best_ticker = sum(
        1 for n in NAMES
        if STRATS[n]["as_shown"].get("best_ticker") is not None
        and STRATS[n]["as_shown"]["beats_buy_hold_on_best_ticker"]
    )
    lines.append(f"Of those, {n_beat_bh_best_ticker}/{len(as_shown_valid)} also beat buy-and-hold on "
                 f"that same best ticker (DEFINE, gross, same_close).")
    lines.append(f"H3 met: {h3_met}")
    lines.append("")
    lines.append("=== What would support the claim instead ===")
    lines.append(f"Condition A: >= 15/30 strategies beat buy-and-hold net on HOLDOUT in more than half "
                 f"their tickers. Measured: {support_a_count}/{n_total}. Met: {support_a_met}")
    lines.append(f"Condition B: >= 8/30 strategies at/above the 95th placebo percentile in BOTH windows "
                 f"(mean-percentile reading). Measured: {support_b_count}/{n_total} -- {both_windows_ge95}. "
                 f"Met: {support_b_met}")
    lines.append(f"Verdict trigger (A or B): {verdict_supported}")
    lines.append("")
    lines.append("=== Strategies at/above 95th placebo percentile in BOTH windows (follow-up candidates) ===")
    lines.append(f"{both_windows_ge95 if both_windows_ge95 else 'none'}")
    lines.append("")

    lines.append("=== 30-row table: strategy / window / tickers beating B&H / pooled diff vs B&H [CI] "
                 "/ mean placebo percentile / n trades median / exposure median ===")
    header = (f"{'strategy':<14}{'window':<9}{'n_tick_beat_bh':<15}{'pooled_diff_daily[95% CI]':<38}"
             f"{'mean_S2_pct':<13}{'trades_med':<12}{'exposure_med':<13}")
    lines.append(header)
    for n in NAMES:
        for window in ("DEFINE", "HOLDOUT"):
            pooled = STRATS[n][window]["pooled"]
            diff = pooled["pooled_diff_vs_buy_hold_mean_daily_net"]
            diff_str = f"{diff['estimate']:.6f} [{diff['lower']:.6f}, {diff['upper']:.6f}]"
            s2 = pooled["s2_mean_placebo_percentile"]
            s2_str = f"{s2:.1f}" if not np.isnan(s2) else "nan"
            n_beat = pooled["n_tickers_beating_buy_hold_net"]
            n_tot = pooled["n_tickers"]
            lines.append(f"{n:<14}{window:<9}{f'{n_beat}/{n_tot}':<15}{diff_str:<38}{s2_str:<13}"
                         f"{pooled['n_trades_median']:<12.1f}{pooled['exposure_median']:<13.3f}")
    lines.append("")

    lines.append("=== As-shown arm (H3 detail) ===")
    for n in NAMES:
        as_shown = STRATS[n]["as_shown"]
        if as_shown.get("best_ticker") is None:
            lines.append(f"{n}: no valid ticker")
            continue
        holdout_pooled = STRATS[n]["HOLDOUT"]["pooled"]
        lines.append(
            f"{n}: best_ticker={as_shown['best_ticker']} gross_DEFINE={as_shown['best_ticker_gross_total_return']:.3f} "
            f"(>0: {as_shown['best_ticker_gross_total_return'] > 0}, beats B&H: {as_shown['beats_buy_hold_on_best_ticker']}) "
            f"| HOLDOUT net pooled beat-B&H fraction={holdout_pooled['s1_fraction_beating_buy_hold']:.2f}"
        )
    lines.append("")

    slow = RESULTS.get("slow_strategies", [])
    lines.append(f"=== Strategies exceeding 20-minute wall time ===\n{slow if slow else 'none'}")
    lines.append("")
    lines.append(f"Total scoring wall time: {RESULTS.get('wall_time_seconds')}s")

    (C02 / "out" / "summary.txt").write_text("\n".join(lines) + "\n")
    print("wrote out/summary.txt")

    # --- Figure 1: placebo percentiles dot plot ---
    fig, ax = plt.subplots(figsize=(9, 8))
    y_pos = np.arange(len(NAMES))
    values = [mean_s2(n, "HOLDOUT") for n in NAMES]
    colors = ["#c0392b" if (not np.isnan(v) and v >= 95.0) else "#2c3e50" for v in values]
    ax.scatter(values, y_pos, c=colors, zorder=3)
    ax.axvline(50, color="gray", linestyle="--", linewidth=1, label="50th percentile")
    ax.axvline(95, color="#c0392b", linestyle="--", linewidth=1, label="95th percentile")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(NAMES, fontsize=7)
    ax.set_xlabel("Mean placebo percentile across tickers (HOLDOUT)")
    ax.set_title("C02: strategy mean placebo percentile, HOLDOUT window")
    ax.set_xlim(0, 100)
    ax.legend(loc="lower right", fontsize=8)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(C02 / "out" / "placebo_percentiles.png", dpi=150)
    plt.close(fig)
    print("wrote out/placebo_percentiles.png")

    # --- Figure 2: as-shown vs holdout, relative to buy-and-hold ---
    fig, ax = plt.subplots(figsize=(10, 8))
    as_shown_rel = []
    holdout_rel = []
    labels = []
    for n in NAMES:
        as_shown = STRATS[n]["as_shown"]
        if as_shown.get("best_ticker") is None:
            continue
        as_shown_gross = as_shown["best_ticker_gross_total_return"]
        as_shown_bh = as_shown["best_ticker_buy_hold_gross_total_return"]
        as_shown_relv = as_shown_gross - as_shown_bh

        holdout_cells = STRATS[n]["HOLDOUT"]["cells"]
        if not holdout_cells:
            continue
        holdout_relv = float(np.mean([
            c["net_total_return"] - c["buy_hold_net_total_return"] for c in holdout_cells.values()
        ]))

        as_shown_rel.append(as_shown_relv)
        holdout_rel.append(holdout_relv)
        labels.append(n)

    y_pos = np.arange(len(labels))
    width = 0.38
    ax.barh(y_pos - width / 2, as_shown_rel, height=width, label="As-shown best ticker, DEFINE, gross, vs B&H",
            color="#e67e22")
    ax.barh(y_pos + width / 2, holdout_rel, height=width, label="HOLDOUT net, mean across tickers, vs B&H",
            color="#2980b9")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Total return relative to buy-and-hold")
    ax.set_title("C02: as-shown (best ticker, DEFINE) vs HOLDOUT (all tickers), relative to buy-and-hold")
    ax.legend(loc="best", fontsize=8)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(C02 / "out" / "as_shown_vs_holdout.png", dpi=150)
    plt.close(fig)
    print("wrote out/as_shown_vs_holdout.png")


if __name__ == "__main__":
    main()
