"""Descriptive extras computed from the stored Part 2 arrays. Not pre-registered.

Run after run_part2.py (which writes out/part2_arrays.npz; that file is large and git-ignored).
Nothing here feeds the verdict: these are the same 2,000 zero-skill bots, read three more ways for
the episode — a bigger monthly gap, how much one bot's weekly hit rate varies, and winning streaks —
plus the RSI rule's pooled trade win rate from the Part 1 per-ticker rows.
"""

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "out"
arrays = np.load(OUT / "part2_arrays.npz")
week, month = arrays["week_excess_bot"], arrays["month_excess_bot"]

per_bot_week_share = (week > 0).mean(axis=0)
non_overlapping = week[::5] > 0
four_in_a_row = non_overlapping[:-3] & non_overlapping[1:-2] & non_overlapping[2:-1] & non_overlapping[3:]

extras = {
    "note": "descriptive, derived after the run from stored arrays; not pre-registered",
    "month_share_beats_spy_by_10pt": float(np.mean(month >= 0.10)),
    "per_bot_share_of_weeks_beating_spy": {
        "min": float(per_bot_week_share.min()),
        "median": float(np.median(per_bot_week_share)),
        "max": float(per_bot_week_share.max()),
    },
    "share_of_4_consecutive_non_overlapping_weeks_all_beating_spy": float(four_in_a_row.mean()),
}
# The RSI rule's pooled trade win rate, from the per-ticker rows of Part 1. Trade counts per ticker
# are small (3-29), so win_rate * n_trades recovers the integer win count exactly.
part1 = json.loads((OUT / "results_part1.json").read_text())
extras["rsi_rule_pooled_trades"] = {}
for window in ("DEFINE", "HOLDOUT", "intraday_60m"):
    rows = part1[window]["per_ticker"]
    n_trades = sum(r["n_trades"] for r in rows)
    n_wins = sum(round(r["win_rate"] * r["n_trades"]) for r in rows)
    extras["rsi_rule_pooled_trades"][window] = {
        "n_trades": n_trades,
        "n_wins": n_wins,
        "win_rate": n_wins / n_trades,
        "mean_exposure": float(np.mean([r["exposure"] for r in rows])),
        "tickers_with_100pct_win_rate": [
            {"ticker": r["ticker"], "n_trades": r["n_trades"], "net_total_return": r["net_total_return"],
             "buy_hold_total_return": r["buy_hold_total_return"]}
            for r in rows if r["win_rate"] == 1.0
        ],
    }

(OUT / "derived_extras.json").write_text(json.dumps(extras, indent=2))
print(json.dumps(extras, indent=2))
