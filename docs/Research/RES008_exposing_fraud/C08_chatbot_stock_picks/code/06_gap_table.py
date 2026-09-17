"""Pool the per-window gap frequencies already in out/results.json into one table.

Part 1 pre-registered "how often a random portfolio lands +3, +13, +22 points ahead or -8 behind".
02_random_portfolios.py stored those per window; every window has the same 10,000 draws, so the
pooled share is the plain mean of the per-window shares. No new simulation — a derived table.
"""

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "out"
windows = json.loads((OUT / "results.json").read_text())["part1_random_portfolios"]["per_window"]

table = {"n_windows": len(windows), "draws_per_window": 10_000}
for bench in ("spy", "universe"):
    ahead = {k: float(np.mean([w[f"gap_share_vs_{bench}_ahead"][k] for w in windows])) for k in ("+3", "+13", "+22")}
    behind = float(np.mean([w[f"gap_share_vs_{bench}_behind_-8"] for w in windows]))
    table[f"vs_{bench}"] = {"ahead_by_at_least": ahead, "behind_by_at_least_8": behind}
spreads = [w["excess_vs_universe_pct"]["spread_5_95"] for w in windows]
table["within_window_spread_5_95"] = {
    "median": float(np.median(spreads)), "min": float(np.min(spreads)), "max": float(np.max(spreads)),
    "share_of_windows_above_30": float(np.mean(np.array(spreads) > 30)),
}
(OUT / "gap_table.json").write_text(json.dumps(table, indent=2))
print(json.dumps(table, indent=2))
