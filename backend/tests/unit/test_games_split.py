"""CR109 slice 2 (G2) — corporate split handling.

A 4:1 split must adjust the held position's quantity and cost basis IN
PLACE, flag the row, and leave NAV continuous (once the market price
divides by the same ratio) — and it must NOT be treated as a capital
event, so it never breaks the TWR chain.

implementation_plan.md §9 test matrix item 27; design §12 / §12.1 G2.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine


class _MutablePriceProvider:
    """A provider whose price for one ticker can be changed mid-test — used
    to simulate what a split does to the market price (divides by the
    ratio) at the same instant the position is adjusted."""

    name = "fake"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def test_4_for_1_split_adjusts_quantity_and_basis_and_flags_the_row():
    provider = _MutablePriceProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    run_id = uuid4()

    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    assert result.accepted

    adjustment = sim.apply_split(user_id, "AAPL", 4.0, run_id=run_id)
    assert adjustment is not None
    assert adjustment.ticker == "AAPL"
    assert adjustment.quantity == pytest.approx(40.0)   # 10 * 4
    assert adjustment.avg_cost == pytest.approx(25.0)   # 100 / 4
    assert adjustment.split_adjusted_at is not None


def test_split_leaves_nav_continuous():
    """Cost basis (quantity * avg_cost) is unchanged by the split itself,
    and once the market price ALSO divides by the ratio (what a real split
    does), the position's market value is unchanged too — NAV continuity."""
    provider = _MutablePriceProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    run_id = uuid4()

    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    _p, marks_before, total_before, _dd, _src = sim.portfolio_marks_snapshot(
        user_id, kind="game", run_id=run_id,
    )
    market_value_before = marks_before["AAPL"] * 10

    sim.apply_split(user_id, "AAPL", 4.0, run_id=run_id)
    provider.price = 100.0 / 4.0  # what a 4:1 split does to the quote

    p_after, marks_after, total_after, _dd, _src = sim.portfolio_marks_snapshot(
        user_id, kind="game", run_id=run_id,
    )
    holding = next(h for h in p_after.holdings if h.ticker == "AAPL")
    market_value_after = marks_after["AAPL"] * holding.quantity

    assert market_value_after == pytest.approx(market_value_before)
    assert total_after == pytest.approx(total_before)


def test_split_is_not_a_capital_event_no_nav_row_touched():
    """apply_split() is a holdings-only mutation — it must never itself
    write a portfolio_nav_daily row, let alone one with a capital_event.
    That is what keeps a split from splitting the TWR chain: there is
    nothing here for the chain to split ON."""
    provider = _MutablePriceProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    run_id = uuid4()
    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    sim.apply_split(user_id, "AAPL", 4.0, run_id=run_id)

    with get_session() as s:
        rows = s.execute(
            select(PortfolioNavDailyRow).where(PortfolioNavDailyRow.run_id == run_id)
        ).scalars().all()
    assert rows == []


def test_split_on_a_ticker_not_held_is_a_no_op():
    provider = _MutablePriceProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    run_id = uuid4()
    sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert sim.apply_split(user_id, "AAPL", 4.0, run_id=run_id) is None


def test_split_never_touches_a_training_holding_by_default():
    """G2's scope is GAME portfolios only ('training absorbs it with a
    free reset', design §12.1) — apply_split defaults to kind='game', so a
    training holding is untouched unless a caller deliberately opts in."""
    provider = _MutablePriceProvider(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10, mandate=mandate,
    )
    assert result.accepted

    # Default kind="game" — no game portfolio exists for this user/run, so
    # this must be a no-op, NOT an accidental adjustment of the training
    # holding under a coincidentally-matching run_id.
    assert sim.apply_split(user_id, "AAPL", 4.0, run_id=uuid4()) is None
    training = sim.ensure_portfolio(user_id)
    assert training.holdings[0].quantity == 10  # unchanged
