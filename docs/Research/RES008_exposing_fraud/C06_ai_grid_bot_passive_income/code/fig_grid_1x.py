"""Rebuild out/grid_dashboard_vs_truth.png from the daily, unlevered grid runs only.

The full runner takes ~14 minutes, most of it the hourly arm; the figure needs only the 9,522
daily 1x runs, which take seconds. Same simulator, same starts, same settings as run_c06.py — this
changes no reported number, it only redraws the picture.
"""

from pathlib import Path

from grid_sim import run_grid
from run_c06 import (DATA_END, GRID_CAPITAL, GRID_LEVELS, GRID_R_VALUES, HORIZON_DAYS, START_STEP_DAYS,
                     _run_starts, _slice_horizon, build_grid_dashboard_figure, load_daily)

OUT = Path(__file__).resolve().parent.parent / "out"

records = []
for ticker, start in (("BTC-USD", "2014-09-01"), ("ETH-USD", "2017-11-01")):
    bars = load_daily([ticker], start, DATA_END)[ticker]
    for start_pos in _run_starts(bars.index, HORIZON_DAYS, START_STEP_DAYS):
        window = _slice_horizon(bars, start_pos, HORIZON_DAYS)
        if len(window) < 2:
            continue
        p0 = float(window.iloc[0]["open"])
        for r in GRID_R_VALUES:
            for levels in GRID_LEVELS:
                res = run_grid(window, p0=p0, r=r, levels=levels, capital=GRID_CAPITAL, leverage=1.0)
                records.append({"leverage": 1.0, "grid_profit": res.grid_profit, "true_pnl": res.true_pnl})

negative = sum(rec["true_pnl"] < 0 for rec in records) / len(records)
print(f"{len(records)} runs, true P&L negative in {negative:.4%}")
build_grid_dashboard_figure(records, OUT / "grid_dashboard_vs_truth.png")
