"""
Hand-computed checks for grid_sim.run_grid, per C06 PREREGISTRATION.md's pytest list:
oscillation round-trip, straight fall through the bottom, straight rise through the
top, fees on every fill, and the 5x liquidation trigger. Every expected number here is
computed independently in this file's comments/arithmetic, not copied from the
simulator's own output.

Grid: p0=100, r=0.1, levels=5 -> lines [90, 95, 100, 105, 110], capital=1000,
q_per_slot=250. Slots 2,3 (sell lines 105, 110, both > p0) start as resting sells
holding init_qty = 250/105 + 250/110 base units bought at 100 (paying the 10bps fee on
that purchase). Slots 0,1 (buy lines 90, 95) start as resting buys.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from grid_sim import run_grid

P0 = 100.0
R = 0.1
LEVELS = 5
CAPITAL = 1000.0
Q = CAPITAL / (LEVELS - 1)
FEE = 0.001


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    o, h, l, c = zip(*rows)
    return pd.DataFrame(
        {"open": o, "high": h, "low": l, "close": c},
        index=pd.date_range("2020-01-01", periods=len(rows)),
    )


def _init_state():
    init_qty = Q / 105.0 + Q / 110.0
    init_notional = init_qty * P0
    init_fee = init_notional * FEE
    quote_cash = CAPITAL - init_notional - init_fee
    return quote_cash, init_qty


def test_oscillation_round_trip_matches_hand_computation_and_restores_inventory():
    bars = _bars(
        [
            (100.0, 100.0, 90.0, 90.0),   # down bar: O->H->L->C, falls to range bottom
            (90.0, 100.0, 90.0, 100.0),   # up bar: O->L->H->C, back to start
        ]
    )
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL)

    quote_cash, base_inv = _init_state()
    qty1 = Q / 95.0
    quote_cash -= qty1 * 95.0 * (1 + FEE)
    base_inv += qty1
    qty0 = Q / 90.0
    quote_cash -= qty0 * 90.0 * (1 + FEE)
    base_inv += qty0

    qty_s0 = qty0
    proceeds = qty_s0 * 95.0
    fee_s = proceeds * FEE
    fee_b = qty_s0 * 90.0 * FEE
    grid_profit = qty_s0 * (95.0 - 90.0) - fee_b - fee_s
    quote_cash += proceeds - fee_s
    base_inv -= qty_s0

    qty_s1 = qty1
    proceeds = qty_s1 * 100.0
    fee_s = proceeds * FEE
    fee_b = qty_s1 * 95.0 * FEE
    grid_profit += qty_s1 * (100.0 - 95.0) - fee_b - fee_s
    quote_cash += proceeds - fee_s
    base_inv -= qty_s1

    expected_equity = quote_cash + base_inv * 100.0

    np.testing.assert_allclose(res.grid_profit, grid_profit, atol=1e-9)
    np.testing.assert_allclose(res.true_pnl, expected_equity - CAPITAL, atol=1e-9)
    assert res.n_completed_pairs == 2
    _, expected_init_qty = _init_state()
    np.testing.assert_allclose(base_inv, expected_init_qty, atol=1e-9)


def test_straight_fall_through_bottom_leaves_grid_profit_nonnegative_true_pnl_negative():
    bars = _bars([(100.0, 100.0, 80.0, 80.0)])
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL)

    quote_cash, base_inv = _init_state()
    qty1 = Q / 95.0
    quote_cash -= qty1 * 95.0 * (1 + FEE)
    base_inv += qty1
    qty0 = Q / 90.0
    quote_cash -= qty0 * 90.0 * (1 + FEE)
    base_inv += qty0
    expected_equity = quote_cash + base_inv * 80.0

    assert res.grid_profit >= 0.0
    np.testing.assert_allclose(res.grid_profit, 0.0, atol=1e-9)
    np.testing.assert_allclose(res.true_pnl, expected_equity - CAPITAL, atol=1e-9)
    assert res.true_pnl < 0.0
    assert res.left_range_down is True
    assert res.n_completed_pairs == 0


def test_straight_rise_through_top_sells_everything_then_sits_in_cash():
    bars = _bars([(100.0, 120.0, 100.0, 120.0)])
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL)

    quote_cash, base_inv = _init_state()
    qty_s2 = Q / 105.0
    proceeds = qty_s2 * 105.0
    quote_cash += proceeds * (1 - FEE)
    base_inv -= qty_s2

    qty_s3 = Q / 110.0
    proceeds = qty_s3 * 110.0
    quote_cash += proceeds * (1 - FEE)
    base_inv -= qty_s3

    np.testing.assert_allclose(base_inv, 0.0, atol=1e-9)
    np.testing.assert_allclose(res.final_equity, quote_cash, atol=1e-9)
    np.testing.assert_allclose(res.true_pnl, quote_cash - CAPITAL, atol=1e-9)
    assert res.left_range_up is True
    assert res.n_completed_pairs == 2


def test_fees_charged_on_every_fill_including_initial_purchase():
    bars = _bars([(100.0, 100.0, 100.0, 100.0)])
    res_with_fee = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL, fee_bps=10.0)
    res_no_fee = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL, fee_bps=0.0)

    init_qty = Q / 105.0 + Q / 110.0
    init_notional = init_qty * P0
    expected_fee_drag = init_notional * FEE

    np.testing.assert_allclose(
        res_no_fee.final_equity - res_with_fee.final_equity, expected_fee_drag, atol=1e-9
    )


def test_5x_liquidation_fires_at_hand_computed_price():
    bars = _bars(
        [
            (100.0, 100.0, 90.0, 90.0),
            (90.0, 90.0, 40.0, 40.0),
        ]
    )
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL, leverage=5.0)

    quote_cash, base_inv = _init_state()
    qty1 = Q / 95.0
    quote_cash -= qty1 * 95.0 * (1 + FEE)
    base_inv += qty1
    qty0 = Q / 90.0
    quote_cash -= qty0 * 90.0 * (1 + FEE)
    base_inv += qty0

    worst_price = 40.0
    worst_equity = quote_cash + base_inv * worst_price
    worst_pnl = worst_equity - CAPITAL
    threshold = -(1.0 / 5.0 - 0.005) * CAPITAL
    assert worst_pnl <= threshold

    assert res.liquidated is True
    assert res.liquidation_bar == 1
    np.testing.assert_allclose(res.true_pnl, -CAPITAL / 5.0, atol=1e-9)
    np.testing.assert_allclose(res.true_pnl_frac, -1.0, atol=1e-9)


def test_no_liquidation_at_1x_leverage_for_same_path():
    bars = _bars(
        [
            (100.0, 100.0, 90.0, 90.0),
            (90.0, 90.0, 40.0, 40.0),
        ]
    )
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL, leverage=1.0)
    assert res.liquidated is False


def test_outside_range_bot_does_nothing_further():
    bars = _bars(
        [
            (100.0, 120.0, 100.0, 120.0),
            (120.0, 150.0, 120.0, 150.0),
        ]
    )
    res = run_grid(bars, p0=P0, r=R, levels=LEVELS, capital=CAPITAL)
    assert res.n_completed_pairs == 2
    quote_cash_after_bar0 = res.bar_equity.iloc[0]
    np.testing.assert_allclose(res.final_equity, quote_cash_after_bar0, atol=1e-9)
