"""Guard tests for `trading_math.cost_basis` (CR029-MATH — pure FIFO engine).

Hand-worked multi-lot FIFO matches, plus the deliberate edge-case rules the
CR029-MATH lane brief asked for: oversell (partial-fill + reported shortfall,
not an error), a sell against an empty lot queue, fractional shares, and the
None-on-nonsense guard the rest of `trading_math` uses.
"""

from __future__ import annotations

from app.trading_math import FifoSellResult, LotClose, OpenLot, fifo_sell

# ── cost_basis.fifo_sell (CR029-MATH) ────────────────────────────────────────


def test_fifo_sell_multi_lot_partial_close_hand_worked():
    # buy 10@$100, buy 10@$120, sell 15@$130.
    # realised P&L = 10*(130-100) + 5*(130-120) = 300 + 50 = 350.
    # lot 1 (10@100) fully closes; lot 2 (10@120) partially closes, 5 remain open.
    result = fifo_sell([(10, 100), (10, 120)], sell_quantity=15, sell_price=130)

    assert result == FifoSellResult(
        closes=[
            LotClose(entry_price=100, quantity_closed=10.0, realised_pnl=300.0),
            LotClose(entry_price=120, quantity_closed=5.0, realised_pnl=50.0),
        ],
        realised_pnl_total=350.0,
        open_lots=[OpenLot(quantity_open=5.0, entry_price=120)],
        quantity_unmatched=0.0,
    )


def test_fifo_sell_exact_single_lot_close():
    result = fifo_sell([(10, 100)], sell_quantity=10, sell_price=150)

    assert result.closes == [LotClose(entry_price=100, quantity_closed=10.0, realised_pnl=500.0)]
    assert result.realised_pnl_total == 500.0
    assert result.open_lots == []
    assert result.quantity_unmatched == 0.0


def test_fifo_sell_loss_on_a_lot_is_a_negative_realised_pnl():
    result = fifo_sell([(10, 100)], sell_quantity=10, sell_price=90)

    assert result.closes == [LotClose(entry_price=100, quantity_closed=10.0, realised_pnl=-100.0)]
    assert result.realised_pnl_total == -100.0


def test_fifo_sell_leaves_later_untouched_lots_in_the_queue():
    # sell only draws down the oldest lot; the two younger lots are untouched.
    result = fifo_sell([(5, 100), (5, 110), (5, 120)], sell_quantity=5, sell_price=130)

    assert result.closes == [LotClose(entry_price=100, quantity_closed=5.0, realised_pnl=150.0)]
    assert result.open_lots == [
        OpenLot(quantity_open=5.0, entry_price=110),
        OpenLot(quantity_open=5.0, entry_price=120),
    ]
    assert result.quantity_unmatched == 0.0


def test_fifo_sell_oversell_closes_everything_and_reports_the_shortfall():
    # only 20 shares open; a 25-share sell is not an error — it closes all 20
    # and reports the remaining 5 as unmatched rather than raising.
    result = fifo_sell([(10, 100), (10, 120)], sell_quantity=25, sell_price=130)

    assert result.closes == [
        LotClose(entry_price=100, quantity_closed=10.0, realised_pnl=300.0),
        LotClose(entry_price=120, quantity_closed=10.0, realised_pnl=100.0),
    ]
    assert result.realised_pnl_total == 400.0
    assert result.open_lots == []
    assert result.quantity_unmatched == 5.0


def test_fifo_sell_against_an_empty_lot_queue_is_fully_unmatched():
    result = fifo_sell([], sell_quantity=10, sell_price=130)

    assert result == FifoSellResult(
        closes=[],
        realised_pnl_total=0.0,
        open_lots=[],
        quantity_unmatched=10.0,
    )


def test_fifo_sell_accepts_fractional_shares():
    # buy 3.5@$50, buy 6.5@$55, sell 5.25@$60.
    # 3.5 closes lot 1 fully (35.00 realised); 1.75 closes part of lot 2 (8.75
    # realised), leaving 4.75 shares of lot 2 open.
    result = fifo_sell([(3.5, 50), (6.5, 55)], sell_quantity=5.25, sell_price=60)

    assert result.closes == [
        LotClose(entry_price=50, quantity_closed=3.5, realised_pnl=35.0),
        LotClose(entry_price=55, quantity_closed=1.75, realised_pnl=8.75),
    ]
    assert result.realised_pnl_total == 43.75
    assert result.open_lots == [OpenLot(quantity_open=4.75, entry_price=55)]
    assert result.quantity_unmatched == 0.0


def test_fifo_sell_open_lots_output_threads_back_in_as_next_call_input():
    # a second sell consumes the `open_lots` the first call returned, unchanged.
    first = fifo_sell([(10, 100), (10, 120)], sell_quantity=15, sell_price=130)
    second = fifo_sell(first.open_lots, sell_quantity=5, sell_price=140)

    assert second == FifoSellResult(
        closes=[LotClose(entry_price=120, quantity_closed=5.0, realised_pnl=100.0)],
        realised_pnl_total=100.0,
        open_lots=[],
        quantity_unmatched=0.0,
    )


def test_fifo_sell_rejects_nonpositive_sell_quantity_or_price():
    assert fifo_sell([(10, 100)], sell_quantity=0, sell_price=130) is None
    assert fifo_sell([(10, 100)], sell_quantity=-5, sell_price=130) is None
    assert fifo_sell([(10, 100)], sell_quantity=5, sell_price=0) is None
    assert fifo_sell([(10, 100)], sell_quantity=5, sell_price=-10) is None


def test_fifo_sell_rejects_a_nonpositive_lot_in_the_queue():
    assert fifo_sell([(0, 100), (10, 120)], sell_quantity=5, sell_price=130) is None
    assert fifo_sell([(-10, 100)], sell_quantity=5, sell_price=130) is None
    assert fifo_sell([(10, 0)], sell_quantity=5, sell_price=130) is None
    assert fifo_sell([(10, -100)], sell_quantity=5, sell_price=130) is None
