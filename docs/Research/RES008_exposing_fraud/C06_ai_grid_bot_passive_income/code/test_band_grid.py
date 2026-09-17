"""
Hand-computed checks for band_grid_sim.run_band_grid, per C06 PREREGISTRATION.md's
pytest list: a series that touches the upper band, extends, and mean-reverts gives
the hand-computed basket P&L; a one-way trend produces ruin at the hand-computed bar.

The synthetic series alternates closes 99/101 for 20 bars (population mean 100,
std exactly 1.0, so Bollinger(20,2) is upper=102/lower=98 the instant the warm-up
window is full) with open == previous close and high/low = max/min(open,close)+/-0.5
(constant true range of 3.0 for every warm-up bar, so ATR(14) is exactly 3.0 once its
own window is full). Every expected number below is computed independently in this
file's arithmetic, not copied from the simulator's own output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from band_grid_sim import run_band_grid

EQUITY0 = 10_000.0
FX_BPS = 2.0
FEE_RATE = FX_BPS / 10_000.0


def _bars_from_closes(closes: list[float]) -> pd.DataFrame:
    opens = [100.0] + closes[:-1]
    highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.date_range("2020-01-01", periods=len(closes)),
    )


WARMUP = [99.0, 101.0] * 10


def test_touch_extend_revert_matches_hand_computed_basket_pnl():
    closes = WARMUP + [103.0, 108.0, 100.0, 99.0]
    bars = _bars_from_closes(closes)

    res = run_band_grid(bars, equity0=EQUITY0, unit_frac=1.0, sizing="constant", fx_cost_bps=FX_BPS)

    entry_price = 103.0
    add_price = 108.0
    close_price = 100.0
    qty0 = EQUITY0 / entry_price
    qty1 = EQUITY0 / add_price
    fee0 = EQUITY0 * FEE_RATE
    fee1 = EQUITY0 * FEE_RATE

    gross_pnl = (qty0 * (entry_price - close_price)) + (qty1 * (add_price - close_price))
    close_fee = (qty0 + qty1) * close_price * FEE_RATE
    expected_realized = gross_pnl - close_fee

    assert res.n_baskets_closed == 1
    assert res.n_baskets_won == 1
    np.testing.assert_allclose(res.basket_pnls[0], expected_realized, atol=1e-6)

    expected_final_equity = EQUITY0 - fee0 - fee1 + expected_realized
    np.testing.assert_allclose(res.equity_curve.iloc[-1], expected_final_equity, atol=1e-6)
    assert res.ruined is False


def test_one_way_trend_produces_ruin_at_hand_computed_bar():
    closes = WARMUP + [103.0, 200.0, 400.0, 800.0]
    bars = _bars_from_closes(closes)

    res = run_band_grid(bars, equity0=EQUITY0, unit_frac=1.0, sizing="constant", fx_cost_bps=FX_BPS)

    entry_price = 103.0
    qty = EQUITY0 / entry_price
    fee = EQUITY0 * FEE_RATE
    cash_after_entry = EQUITY0 - fee

    entry_bar_high = max(103.0, 200.0) + 0.5
    worst_equity = cash_after_entry + qty * (entry_price - entry_bar_high)

    assert worst_equity <= 0.20 * EQUITY0
    assert res.ruined is True
    assert res.ruin_bar == len(WARMUP) + 1
    np.testing.assert_allclose(res.equity_curve.iloc[-1], worst_equity, atol=1e-6)


def test_no_ruin_and_no_close_when_price_stays_inside_bands():
    bars = _bars_from_closes(WARMUP)
    res = run_band_grid(bars, equity0=EQUITY0, unit_frac=1.0, sizing="constant", fx_cost_bps=FX_BPS)
    assert res.ruined is False
    assert res.n_baskets_closed == 0
    np.testing.assert_allclose(res.equity_curve.iloc[-1], EQUITY0, atol=1e-9)


def test_martingale_add_is_larger_than_constant_add():
    closes = WARMUP + [103.0, 108.0, 100.0, 99.0]
    bars = _bars_from_closes(closes)

    res_const = run_band_grid(bars, equity0=EQUITY0, unit_frac=0.5, sizing="constant", fx_cost_bps=FX_BPS)
    res_mart = run_band_grid(bars, equity0=EQUITY0, unit_frac=0.5, sizing="martingale", fx_cost_bps=FX_BPS)

    assert res_const.n_baskets_closed == 1
    assert res_mart.n_baskets_closed == 1
    assert res_mart.basket_pnls[0] != res_const.basket_pnls[0]
