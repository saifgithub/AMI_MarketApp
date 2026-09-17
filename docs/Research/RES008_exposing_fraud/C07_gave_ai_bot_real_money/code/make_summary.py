"""
Builds `out/summary.txt` from `out/results_part1.json` and
`out/results_part2.json` only -- every number here must trace back to one
of those two files (no recomputation, no numbers invented for readability).
"""

from __future__ import annotations

import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
C07_DIR = THIS_DIR.parent
OUT_DIR = C07_DIR / "out"


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.2f}%"


def fmt(x, nd=4) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def main() -> None:
    with open(OUT_DIR / "results_part1.json") as f:
        p1 = json.load(f)
    with open(OUT_DIR / "results_part2.json") as f:
        p2 = json.load(f)

    lines = []
    lines.append("C07 -- \"I gave an AI bot real money and it beat the market\" -- RESULTS SUMMARY")
    lines.append("=" * 78)
    lines.append("")

    lines.append("PART 1 -- the disclosed rule: Wilder RSI(14), long<30/flat>70, long/flat only")
    lines.append(f"U-EQ ({p1['meta']['universe'].__len__()} tickers), next_open execution, "
                 f"{p1['meta']['cost_bps']} bps/side, {p1['meta']['placebo_reps']} placebo reps")
    lines.append("-" * 78)
    for window_key, window_label in [("DEFINE", "DEFINE (2005-2018)"), ("HOLDOUT", "HOLDOUT (2019-2026)"), ("intraday_60m", "60-minute (~730 days)")]:
        pooled = p1[window_key]["pooled"]
        n = pooled["n_tickers"]
        beats = pooled["n_tickers_beat_buy_hold_net"]
        paired = pooled["paired_diff_mean_daily_net_vs_buy_hold"]
        placebo = pooled["mean_placebo_percentile"]
        lines.append(f"[{window_label}]")
        lines.append(f"  Tickers beating buy-and-hold net: {beats}/{n}")
        lines.append(f"  Zero-trade tickers (excluded from placebo mean): {pooled['zero_trade_tickers'] or 'none'}")
        lines.append(
            f"  Paired diff, mean daily net return (rule - buy&hold): {fmt(paired['estimate'], 6)} "
            f"[{fmt(paired['lower'], 6)}, {fmt(paired['upper'], 6)}] (block bootstrap, block_len={paired['block_len']})"
        )
        if placebo is not None:
            lines.append(
                f"  Mean placebo percentile across tickers: {fmt(placebo['estimate'], 3)} "
                f"[{fmt(placebo['lower'], 3)}, {fmt(placebo['upper'], 3)}] "
                f"({pooled['n_tickers_with_trades']}/{n} tickers with trades)"
            )
        else:
            lines.append("  Mean placebo percentile: n/a (no tickers with trades)")
        lines.append("")

    lines.append("PART 2 -- what a short window can show: the zero-skill bot")
    lines.append(
        f"{p2['meta']['n_bots']} bots, {p2['meta']['tickers']}, "
        f"{p2['meta']['start']} -> {p2['meta']['end']} ({p2['meta']['n_trading_days']} trading days)"
    )
    lines.append("-" * 78)

    zs_week = p2["zero_skill_bot"]["week_vs_spy"]
    zs_month = p2["zero_skill_bot"]["month_vs_spy"]
    lines.append("[Zero-skill bot vs SPY]")
    lines.append(
        f"  1-week windows (n={zs_week['n_pairs']}): beats SPY {pct(zs_week['share_beats_spy'])}, "
        f"by >=1pt {pct(zs_week['share_beats_spy_by_1pt'])}, by >=3pt {pct(zs_week['share_beats_spy_by_3pt'])}"
    )
    lines.append(
        f"  1-month (21d) windows (n={zs_month['n_pairs']}): beats SPY {pct(zs_month['share_beats_spy'])}, "
        f"by >=1pt {pct(zs_month['share_beats_spy_by_1pt'])}, by >=3pt {pct(zs_month['share_beats_spy_by_3pt'])}"
    )
    wp = p2["zero_skill_bot"]["week_excess_percentiles"]
    mp = p2["zero_skill_bot"]["month_excess_percentiles"]
    lines.append(
        f"  Weekly excess return percentiles (5/25/50/75/95): "
        f"{pct(wp['p5'])} / {pct(wp['p25'])} / {pct(wp['p50'])} / {pct(wp['p75'])} / {pct(wp['p95'])}"
    )
    lines.append(
        f"  Monthly excess return percentiles (5/25/50/75/95): "
        f"{pct(mp['p5'])} / {pct(mp['p25'])} / {pct(mp['p50'])} / {pct(mp['p75'])} / {pct(mp['p95'])}"
    )
    lines.append("")

    rsi_week = p2["rsi_rule_equal_weight_portfolio"]["week_vs_spy"]
    rsi_month = p2["rsi_rule_equal_weight_portfolio"]["month_vs_spy"]
    lines.append("[Part 1 RSI rule as a 22-ticker equal-weight portfolio, vs SPY, same window]")
    lines.append(f"  Construction: {p2['rsi_rule_equal_weight_portfolio']['construction']}")
    lines.append(
        f"  1-week windows (n={rsi_week['n_pairs']}): beats SPY {pct(rsi_week['share_beats_spy'])}, "
        f"by >=1pt {pct(rsi_week['share_beats_spy_by_1pt'])}, by >=3pt {pct(rsi_week['share_beats_spy_by_3pt'])}"
    )
    lines.append(
        f"  1-month windows (n={rsi_month['n_pairs']}): beats SPY {pct(rsi_month['share_beats_spy'])}, "
        f"by >=1pt {pct(rsi_month['share_beats_spy_by_1pt'])}, by >=3pt {pct(rsi_month['share_beats_spy_by_3pt'])}"
    )
    lines.append("")

    tm = p2["trending_month_conditional"]
    lines.append("[Trending-month conditional: equal-weight basket up >= 8% over 21 days]")
    lines.append(f"  Trending 21-day windows: {tm['n_trending_windows']} of {tm['n_total_21d_windows']} "
                 f"({pct(tm['share_of_windows_trending'])} of all windows)")
    tcw = tm["trend_trade_win_rate_wilson_ci"]
    ucw = tm["unconditional_trade_win_rate_wilson_ci"]
    lines.append(
        f"  Trade win rate in trending windows: {pct(tm['trend_trade_win_rate'])} "
        f"[{pct(tcw['lower']) if tcw else 'n/a'}, {pct(tcw['upper']) if tcw else 'n/a'}] (n={tm['n_trend_trades']} trades)"
    )
    lines.append(
        f"  Trade win rate unconditionally: {pct(tm['unconditional_trade_win_rate'])} "
        f"[{pct(ucw['lower']) if ucw else 'n/a'}, {pct(ucw['upper']) if ucw else 'n/a'}] (n={tm['n_all_trades']} trades)"
    )
    lines.append(f"  Mean 21-day basket return in trending windows: {pct(tm['trend_mean_21d_return'])}")
    lines.append("")

    ss = p2["sample_size_arithmetic"]
    lines.append(f"[Sample-size arithmetic for a genuine +{p2['meta']['edge_pts_per_year_for_sample_size']*100:.0f}pt/year edge at 2 standard errors]")
    lines.append(
        f"  Weekly: measured sigma={fmt(ss['weekly']['sigma'], 5)}, mu/week={fmt(ss['weekly']['mu_per_period'], 5)} "
        f"-> n={ss['weekly']['n_periods']:.1f} weeks ({ss['weekly']['n_years']:.2f} years)"
    )
    lines.append(
        f"  Monthly: measured sigma={fmt(ss['monthly']['sigma'], 5)}, mu/month={fmt(ss['monthly']['mu_per_period'], 5)} "
        f"-> n={ss['monthly']['n_periods']:.1f} months ({ss['monthly']['n_years']:.2f} years)"
    )
    lines.append("")

    text = "\n".join(lines) + "\n"
    (OUT_DIR / "summary.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
