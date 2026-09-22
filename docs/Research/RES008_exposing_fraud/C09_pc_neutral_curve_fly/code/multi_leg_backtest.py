"""
Multi-leg portfolio backtest for C09's PC-neutral fly (Arm A) and the naive
2-leg spread (Arm B).

`common/backtest.py::run_positions` prices ONE instrument's position series.
The PC-neutral fly is 5 simultaneous positions (one per `U-RATES` ETF) whose
combined weights change daily, so this module composes per-leg
`run_positions` calls: each leg is backtested independently under the exact
same next_open convention and cost rate, then the legs' net daily returns
are summed (a correctly-margined portfolio of positions with the same
notional-per-leg unit, matching how `target_position_by_ticker` is scaled
in PREREGISTRATION.md -- gross exposure normalized to 1 across legs).

This is a thin composition layer, not a new pricing model: no leg here does
anything `common/backtest.py` doesn't already guarantee (no lookahead,
correct next_open compounding, correct cost charging per leg).
"""

from __future__ import annotations

import pandas as pd

from common.backtest import run_positions


def run_portfolio(
    bars_by_ticker: dict[str, pd.DataFrame],
    target_weights: pd.DataFrame,
    cost_bps: float,
) -> dict[str, object]:
    """Backtest a multi-leg portfolio: one target-position series per column.

    `target_weights` columns must match `bars_by_ticker` keys. Each column
    is independently run through `run_positions` (next_open, same cost_bps
    per leg) and the legs' net daily returns are summed. Returns
    {"daily_returns": pd.Series, "leg_trades": {ticker: trades_df},
    "leg_results": {ticker: BacktestResult}}.
    """
    leg_results = {}
    leg_returns = {}

    for ticker in target_weights.columns:
        bars = bars_by_ticker[ticker]
        target = target_weights[ticker].reindex(bars.index).fillna(0.0)
        result = run_positions(bars, target, cost_bps=cost_bps, execution="next_open")
        leg_results[ticker] = result
        leg_returns[ticker] = result.daily_returns

    combined = pd.concat(leg_returns, axis=1).fillna(0.0)
    portfolio_daily_returns = combined.sum(axis=1)
    portfolio_daily_returns.name = "daily_returns"

    leg_trades = {t: r.trades for t, r in leg_results.items()}

    return {
        "daily_returns": portfolio_daily_returns,
        "leg_trades": leg_trades,
        "leg_results": leg_results,
    }


def total_trade_count(leg_trades: dict[str, pd.DataFrame]) -> int:
    return sum(len(df) for df in leg_trades.values())
