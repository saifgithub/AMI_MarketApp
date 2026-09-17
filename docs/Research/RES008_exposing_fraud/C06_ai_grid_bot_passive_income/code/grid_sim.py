"""
Spot grid bot simulator — Mechanism 1 of C06's PREREGISTRATION.md.

Arithmetic levels across [P0*(1-r), P0*(1+r)]; `levels` grid LINES (so
levels-1 order slots), each holding equal QUOTE capital Q = capital /
(levels-1), fixed at that slot's original allocation. At start the bot buys,
at P0 paying the 10 bps fee, the base inventory needed to place a sell at
every line above P0 -- Q/L base units for each line at price L, so filling
that sell releases exactly Q of quote back (the grid is self-financing).
Thereafter a resting buy at line i, when filled, buys qty = Q/P_i base units
and that SAME qty (not re-sized) rests as the sell at line i+1; when that
sell fills the buy at i is re-armed. This exact-quantity-conservation
convention (buy sized at the buy price, quantity carried unchanged to the
paired sell) is the only reading under which "grid profit" per completed
pair is simply qty*(P_{i+1}-P_i) minus the two fees -- recorded in
../out/DEVIATIONS.md since the prereg states the mechanism in prose, not as
order-sizing arithmetic.

Intrabar path is O->L->H->C on an up bar (close >= open) and O->H->L->C on a
down bar, and level crossings are processed in that path order so one bar
can fill several levels and complete several round trips. Outside
[low, high] the bot does nothing.

The 5x version runs the identical grid logic on 5x notional with 1x margin
posted, liquidating the run the first time true P&L <= -(1/5 - 0.005) *
notional, checked against the worst point of the bar's assumed path (the
low of an up bar's path, the high... no -- the worst point for a LONG
book is always the lowest price the path reaches, so the bar's `low`
regardless of bar direction). After liquidation the run's return is -100%
of the margin posted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FEE_BPS = 10.0
MAINTENANCE_MARGIN_FRAC = 0.005
LEVERAGE_5X = 5.0


def grid_lines(p0: float, r: float, levels: int) -> np.ndarray:
    low = p0 * (1.0 - r)
    high = p0 * (1.0 + r)
    return np.linspace(low, high, levels)


@dataclass
class GridRunResult:
    grid_profit: float
    true_pnl: float
    true_pnl_frac: float
    final_equity: float
    starting_capital: float
    left_range_up: bool
    left_range_down: bool
    n_completed_pairs: int
    liquidated: bool = False
    liquidation_bar: int | None = None
    bar_equity: pd.Series = field(default_factory=pd.Series, repr=False)


def _path(row: pd.Series) -> list[float]:
    o, h, low, c = row["open"], row["high"], row["low"], row["close"]
    if c >= o:
        return [o, low, h, c]
    return [o, h, low, c]


def run_grid(
    bars: pd.DataFrame,
    p0: float,
    r: float,
    levels: int,
    capital: float,
    leverage: float = 1.0,
    fee_bps: float = FEE_BPS,
) -> GridRunResult:
    """Simulate one grid run starting at the first row of `bars`.

    `bars` must start at the run's start bar (its first `open` need not
    equal p0 -- p0 is the reference price the range/levels are built from,
    per the spec's "P0" being the start price the range is anchored to).
    `capital` is the notional the grid trades against; at 1x it is also the
    equity posted, at `leverage`>1 the margin posted is capital/leverage.
    """
    lines = grid_lines(p0, r, levels)
    n_slots = levels - 1
    q_per_slot = capital / n_slots
    fee_rate = fee_bps / 10_000.0

    notional = capital
    margin = capital / leverage if leverage > 1.0 else capital

    resting_buy_qty: dict[int, float] = {}
    resting_sell_qty: dict[int, float] = {}
    init_qty = 0.0
    for i in range(n_slots):
        sell_line_price = lines[i + 1]
        if sell_line_price <= p0:
            resting_buy_qty[i] = q_per_slot / lines[i]
        else:
            qty = q_per_slot / sell_line_price
            resting_sell_qty[i] = qty
            init_qty += qty

    init_notional = init_qty * p0
    init_fee = init_notional * fee_rate

    quote_cash = notional - init_notional - init_fee
    base_inventory = init_qty

    grid_profit = 0.0
    n_completed_pairs = 0
    left_range_up = False
    left_range_down = False
    liquidated = False
    liquidation_bar: int | None = None

    last_price = p0
    bar_equity = np.empty(len(bars))

    cur_idx = int(np.searchsorted(lines, p0, side="right") - 1)

    def cross_up(i: int) -> None:
        """Price has just crossed line index i (0-based) moving upward: line i-1's sell, if resting, fills."""
        nonlocal grid_profit, n_completed_pairs, quote_cash, base_inventory
        sell_slot = i - 1
        if sell_slot in resting_sell_qty:
            qty = resting_sell_qty.pop(sell_slot)
            line_price = lines[i]
            proceeds = qty * line_price
            fee = proceeds * fee_rate
            quote_cash += proceeds - fee
            base_inventory -= qty
            buy_price = lines[sell_slot]
            buy_fee = (qty * buy_price) * fee_rate
            grid_profit += qty * (line_price - buy_price) - buy_fee - fee
            n_completed_pairs += 1
            resting_buy_qty[sell_slot] = q_per_slot / buy_price

    def cross_down(i: int) -> None:
        """Price has just crossed line index i (0-based) moving downward: line i's buy, if resting, fills."""
        nonlocal quote_cash, base_inventory
        if i in resting_buy_qty and i not in resting_sell_qty:
            qty = resting_buy_qty.pop(i)
            line_price = lines[i]
            cost = qty * line_price
            fee = cost * fee_rate
            quote_cash -= cost + fee
            base_inventory += qty
            if i + 1 < len(lines):
                resting_sell_qty[i] = qty

    for bar_i in range(len(bars)):
        row = bars.iloc[bar_i]
        path = _path(row)

        for leg_i in range(1, len(path)):
            seg_start = path[leg_i - 1]
            seg_end = path[leg_i]
            if seg_end == seg_start:
                continue

            if seg_end > seg_start:
                while cur_idx + 1 < len(lines) and lines[cur_idx + 1] <= seg_end:
                    cur_idx += 1
                    cross_up(cur_idx)
                    if cur_idx >= len(lines) - 1:
                        left_range_up = True
            else:
                while cur_idx - 1 >= 0 and lines[cur_idx - 1] >= seg_end:
                    cross_down(cur_idx - 1)
                    cur_idx -= 1
                    if cur_idx <= 0:
                        left_range_down = True

        last_price = row["close"]
        equity = quote_cash + base_inventory * last_price
        bar_equity[bar_i] = equity

        if leverage > 1.0:
            worst_price = row["low"]
            worst_equity = quote_cash + base_inventory * worst_price
            worst_pnl = worst_equity - notional
            liq_threshold = -(1.0 / leverage - MAINTENANCE_MARGIN_FRAC) * notional
            if worst_pnl <= liq_threshold:
                liquidated = True
                liquidation_bar = bar_i
                break

    if liquidated:
        true_pnl = -margin
        true_pnl_frac = -1.0
        final_equity = 0.0
        bar_equity = pd.Series(bar_equity[: liquidation_bar + 1], index=bars.index[: liquidation_bar + 1])
    else:
        final_equity = quote_cash + base_inventory * last_price
        true_pnl = final_equity - notional
        true_pnl_frac = true_pnl / margin
        bar_equity = pd.Series(bar_equity, index=bars.index)

    return GridRunResult(
        grid_profit=grid_profit,
        true_pnl=true_pnl,
        true_pnl_frac=true_pnl_frac,
        final_equity=final_equity,
        starting_capital=notional,
        left_range_up=left_range_up,
        left_range_down=left_range_down,
        n_completed_pairs=n_completed_pairs,
        liquidated=liquidated,
        liquidation_bar=liquidation_bar,
        bar_equity=bar_equity,
    )


def buy_and_hold_return(bars: pd.DataFrame, p0: float, fee_bps: float = FEE_BPS) -> float:
    fee_rate = fee_bps / 10_000.0
    qty = (1.0 - fee_rate) / p0
    final_price = bars.iloc[-1]["close"]
    return qty * final_price - 1.0
