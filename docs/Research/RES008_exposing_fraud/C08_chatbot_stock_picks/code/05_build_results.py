"""C08 -- combine part1/part2-3 JSONs into out/results.json and write out/summary.txt.

Pure aggregation: no new statistics are computed here, only pulled from the
files 02_random_portfolios.py, 03_parse_picks.py and 04_analyse_picks.py
already wrote, and formatted into the headline numbers PREREGISTRATION.md's
hypotheses and "what would support the claim" section ask for.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
OUT_DIR = CODE_DIR.parent / "out"


def main() -> None:
    part1 = json.loads((OUT_DIR / "part1_random_portfolios.json").read_text())
    part23 = json.loads((OUT_DIR / "part2_3_analysis.json").read_text())

    with (OUT_DIR / "picks.csv").open() as f:
        picks_rows = list(csv.DictReader(f))

    refusal_counts = {}
    for r in picks_rows:
        key = (r["prompt_key"], r["model"])
        refusal_counts.setdefault(key, [0, 0])
        refusal_counts[key][1] += 1
        if r["refused"] == "True":
            refusal_counts[key][0] += 1
    refusal_summary = {
        f"{k[0]}_{k[1]}": {"refused": v[0], "total": v[1], "rate": v[0] / v[1]}
        for k, v in sorted(refusal_counts.items())
    }

    results = {
        "part1_random_portfolios": part1,
        "part2_3_analysis": part23,
        "refusal_rates": refusal_summary,
    }
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))

    p1 = part1["pooled"]
    p2s = part23["part2_stability_and_frequency"]
    p2m = part23["part2_momentum_tilt"]
    p3 = part23["part3_hindsight"]

    h1_spread_met = p2s is not None and p1["excess_vs_universe_pct"]["median_within_window_spread_5_95"] < 10.0
    h2_jaccard_low = p2s["mean_jaccard_overall"] is not None and p2s["mean_jaccard_overall"] < 0.2
    h2_tilt_neutral = (
        p2m["36m"]["mean_percentile"] is not None and 45.0 <= p2m["36m"]["mean_percentile"] <= 55.0
    )
    h3_no_hindsight = p3["pooled"]["mean_percentile"] is not None and 35.0 <= p3["pooled"]["mean_percentile"] <= 65.0

    lines = []
    lines.append("C08 -- 'A chatbot's stock picks beat the market' -- SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("PART 1 -- what luck alone does (10,000 random 10-stock portfolios/window,")
    lines.append(f"{part1['meta']['n_windows']} month-start 12-month windows, 2006-01 -> 2025-08)")
    lines.append("-" * 70)
    lines.append(f"  share beating universe equal-weight mean (pooled): {p1['beat_universe_share']:.4f}")
    lines.append(f"  share beating SPY (pooled):                        {p1['beat_spy_share']:.4f}")
    lines.append(f"  excess vs universe mean, pooled IQR:                {p1['excess_vs_universe_pct']['iqr']:.2f}pp")
    lines.append(f"  excess vs universe mean, pooled 5-95 spread:        {p1['excess_vs_universe_pct']['spread_5_95_pooled_across_windows']:.2f}pp")
    lines.append(f"  excess vs universe mean, MEDIAN WITHIN-WINDOW 5-95 spread (headline): {p1['excess_vs_universe_pct']['median_within_window_spread_5_95']:.2f}pp")
    lines.append("    -- this is the honest 'one year, one draw' number: it answers what spread")
    lines.append("       a single chatbot run in a single actual year faces, not the spread you'd")
    lines.append("       see only by also mixing across 20 different market regimes (2006 vs 2024).")
    lines.append(f"  analytic P(>=3-of-4 coin-flip portfolios beat SPY at p=0.5): {p1['p_ge3of4_analytic_p50']:.4f}")
    lines.append(f"  same P using MEASURED p=share-beating-SPY ({p1['beat_spy_share']:.4f}): {p1['p_ge3of4_measured_p_beat_spy']:.4f}")
    lines.append(f"  same P using MEASURED p=share-beating-universe ({p1['beat_universe_share']:.4f}): {p1['p_ge3of4_measured_p_beat_universe']:.4f}")
    lines.append("")
    lines.append("PART 2 -- what chatbots actually pick ('now' prompt, 30 replies: 3 models x 10 runs)")
    lines.append("-" * 70)
    lines.append(f"  replies naming >=1 pick: {p2s['n_replies_with_picks']}/30")
    lines.append(f"  mean pairwise Jaccard within model: {p2s['mean_jaccard_within_model']}")
    lines.append(f"  mean pairwise Jaccard across model pairs: {p2s['mean_jaccard_across_model_pairs']}")
    lines.append(f"  mean pairwise Jaccard, all picks-giving replies pooled: {p2s['mean_jaccard_overall']:.4f}" if p2s['mean_jaccard_overall'] is not None else "  mean pairwise Jaccard pooled: n/a")
    lines.append(f"  share of picks outside U_LARGE100: {p2s['share_outside_universe']:.4f} ({p2s['n_outside_universe']}/{p2s['n_total_picks']})")
    lines.append(f"  most-picked names (top 10): {p2s['most_picked_names'][:10]}")
    lines.append(f"  trailing 36-month return percentile of in-universe picks: mean={p2m['36m']['mean_percentile']:.2f}, "
                 f"95% CI=[{p2m['36m']['bootstrap_ci']['lower']:.2f}, {p2m['36m']['bootstrap_ci']['upper']:.2f}] (n={p2m['36m']['n_replies']} replies, as of {p2m['end_date']})")
    lines.append(f"  trailing 12-month return percentile of in-universe picks: mean={p2m['12m']['mean_percentile']:.2f}, "
                 f"95% CI=[{p2m['12m']['bootstrap_ci']['lower']:.2f}, {p2m['12m']['bootstrap_ci']['upper']:.2f}] (n={p2m['12m']['n_replies']} replies, as of {p2m['end_date']})")
    lines.append("")
    lines.append("PART 3 -- hindsight (backdated 'as of Jan 2, 2019' prompt, 30 replies: 3 models x 10 runs)")
    lines.append("-" * 70)
    lines.append(f"  replies analysed (named >=1 in-universe pick): {p3['n_replies_analysed']}/30")
    lines.append(f"  random-portfolio pool size (names with data 2019-01-02): {p3['n_available_universe_names_at_2019_01_02']}")
    lines.append(f"  pooled mean percentile vs 10,000 random n-stock portfolios: {p3['pooled']['mean_percentile']:.2f}, "
                 f"95% CI=[{p3['pooled']['bootstrap_ci']['lower']:.2f}, {p3['pooled']['bootstrap_ci']['upper']:.2f}]")
    for model, stats in p3["by_model"].items():
        lines.append(f"    {model}: mean={stats['mean_percentile']:.2f}, 95% CI=[{stats['bootstrap_ci']['lower']:.2f}, {stats['bootstrap_ci']['upper']:.2f}] (n={stats['n_replies']})")
    lines.append(f"  replies explicitly caveating/refusing on future-knowledge grounds: {p3['n_replies_with_future_knowledge_caveat']}/{p3['n_asof2019_replies_total']}")
    for ex in p3["caveat_examples"]:
        lines.append(f"    example ({ex['file']}): \"{ex['quote']}\"")
    lines.append("")
    lines.append("REFUSAL / HEDGE RATES (0 picks named) PER MODEL x PROMPT")
    lines.append("-" * 70)
    for key, v in refusal_summary.items():
        lines.append(f"  {key:<20} {v['refused']}/{v['total']} ({v['rate']*100:.0f}%)")
    lines.append("")
    lines.append("HYPOTHESES vs 'WHAT WOULD SUPPORT THE CLAIM' (measured, stated neutrally)")
    lines.append("-" * 70)
    lines.append(f"  H1 (noise): beat_universe_share in [0.40, 0.55]? measured={p1['beat_universe_share']:.4f} "
                 f"-> {'inside band' if 0.40 <= p1['beat_universe_share'] <= 0.55 else 'outside band'}")
    lines.append(f"      median within-window 5-95 spread > 30pp? measured={p1['excess_vs_universe_pct']['median_within_window_spread_5_95']:.2f}pp "
                 f"-> {'met' if p1['excess_vs_universe_pct']['median_within_window_spread_5_95'] > 30.0 else 'not met'}")
    lines.append(f"      [claim support condition: spread < 10pp] -> measured {p1['excess_vs_universe_pct']['median_within_window_spread_5_95']:.2f}pp "
                 f"-> {'SUPPORTS CLAIM' if h1_spread_met else 'does not support claim'}")
    lines.append(f"  H2 (momentum tilt): mean Jaccard >= 0.4? measured={p2s['mean_jaccard_overall']:.4f} "
                 f"-> {'met' if p2s['mean_jaccard_overall'] >= 0.4 else 'not met'}")
    lines.append(f"      trailing-36m percentile >= 65th? measured={p2m['36m']['mean_percentile']:.2f} "
                 f"-> {'met' if p2m['36m']['mean_percentile'] >= 65.0 else 'not met'}")
    lines.append(f"      [claim support condition: Jaccard < 0.2 AND trailing pctile in 45-55] "
                 f"-> measured Jaccard={p2s['mean_jaccard_overall']:.4f}, pctile={p2m['36m']['mean_percentile']:.2f} "
                 f"-> {'SUPPORTS CLAIM (H2 wrong)' if (h2_jaccard_low and h2_tilt_neutral) else 'does not support claim'}")
    lines.append(f"  H3 (hindsight): pooled mean percentile >= 90th? measured={p3['pooled']['mean_percentile']:.2f} "
                 f"-> {'met' if p3['pooled']['mean_percentile'] >= 90.0 else 'not met'}")
    lines.append(f"      [claim support condition: pooled mean percentile in 35-65] -> measured {p3['pooled']['mean_percentile']:.2f} "
                 f"-> {'SUPPORTS CLAIM (no measurable hindsight)' if h3_no_hindsight else 'does not support claim'}")

    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
