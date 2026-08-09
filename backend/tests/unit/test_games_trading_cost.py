"""CR109 slice 2, Amendment D — the trading cost.

10 bps of notional, floored at 1.00 AMI Cash, on BOTH sides of a fill,
GAME-path only, BURNED (never pooled). Also re-confirms the training path
is untouched by any of this: it still enforces the safety floor and still
carries zero fee.

implementation_plan.md §9 test matrix items 5-9 (Amendment D's additions).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import select

from app.db import Base, get_session
from app.db.models import GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import OrderType, Side
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.games_scoring import FEE_BPS, FEE_MIN, trade_fee
from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick
from app.services.sim_engine import SimEngine
from app.trading_math.twr import NavPoint, sub_period_returns

_DAY_1 = date(2026, 8, 10)
_DAY_2 = date(2026, 8, 11)
_NOW = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


class _ConstProvider:
    """A fixed-price provider — same shape as test_cr026's, kept local so
    this file has no cross-test-file dependency."""

    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
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


def test_trade_fee_constants_are_10bps_min_1():
    """The loud test the constants module promises — a retune is a one-
    line change here that fails until updated."""
    assert FEE_BPS == 10.0
    assert FEE_MIN == 1.00
    assert trade_fee(1_000.0) == 1.00  # 10bps of 1000 = 1.00, no flooring needed
    assert trade_fee(50.0) == 1.00     # 10bps of 50 = 0.05, floored to 1.00


def test_game_buy_1000_notional_deducts_1001():
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    run_id = uuid4()
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    assert result.accepted, result.reason
    assert result.fee == 1.00
    portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert portfolio.current_cash == pytest.approx(10_000.0 - 1_001.00)


def test_game_buy_50_notional_deducts_51_the_floor_applies():
    sim = SimEngine(provider=_ConstProvider(10.0))
    user_id = uuid4()
    run_id = uuid4()
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=5,
    )
    assert result.accepted, result.reason
    assert result.fee == 1.00  # 10bps of 50 = 0.05, floored to FEE_MIN
    portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert portfolio.current_cash == pytest.approx(10_000.0 - 51.00)


def test_game_sell_also_charges_the_fee_both_sides():
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    run_id = uuid4()
    buy = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    assert buy.accepted
    cash_after_buy = sim.ensure_portfolio(user_id, kind="game", run_id=run_id).current_cash

    sell = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.SELL, quantity=10,
    )
    assert sell.accepted, sell.reason
    assert sell.fee == 1.00  # 10bps of 1000 proceeds
    portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    # Proceeds (1000) credited, minus the sell-side fee (1.00) — NOT the
    # full 1000, which is what "both sides" means.
    assert portfolio.current_cash == pytest.approx(cash_after_buy + 1_000.00 - 1.00)


def test_training_path_trades_carry_zero_fee():
    """The split, asserted from both sides: submit() never passes a fee to
    _execute_fill, so a training BUY moves exactly its notional."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10, mandate=mandate,
    )
    assert result.accepted
    portfolio = sim.ensure_portfolio(user_id)  # kind="training" default
    assert portfolio.current_cash == pytest.approx(10_000.0 - 1_000.00)


def test_training_submit_path_still_rejects_mandate_breaches():
    """The floor is intact — CR109 touches NOTHING on the training path.
    Same blocklist shape as test_sim_engine.py::test_blocklist_rejects."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "compliance": {"ticker_blocklist": ["AAPL"]},
    })
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1, mandate=mandate,
    )
    assert not result.accepted
    assert any("blocklist" in v for v in result.compliance.violations)


def test_fee_is_burned_total_system_value_shrinks_by_exactly_the_fee():
    """BURNED, never pooled: the fee must vanish from the system with no
    offsetting credit anywhere. Conservation check with a constant-price
    provider makes this exact: cash + holdings-value after a fee-charged
    BUY must be starting_capital MINUS the fee, not merely re-shuffled."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    run_id = uuid4()
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=5,
    )
    assert result.accepted
    assert result.fee == 1.00  # notional 500 -> 10bps=0.50 -> floored to 1.00

    _p, marks, total_value, _dd, _src = sim.portfolio_marks_snapshot(
        user_id, kind="game", run_id=run_id,
    )
    assert total_value == pytest.approx(10_000.0 - result.fee)


def test_no_table_or_field_total_ever_accumulates_fees():
    """No table, counter or aggregate anywhere sums the fee — structural
    assertion over the schema itself, not just one run's arithmetic.

    CR109 slice 3 adds `career_events` — a per-user, append-only POINTS
    ledger (implementation_plan.md §4.5), not a fee pool. It is fine for it
    to exist; what must stay true is that it carries no fee-summing column
    at all, same as `game_fields`."""
    table_names = set(Base.metadata.tables.keys())
    assert "fee_pool" not in table_names
    assert "trading_fees" not in table_names
    # game_fields carries no fee-related column at all — fees live ONLY on
    # the per-user, per-entry `game_entries.fees_paid` (a personal record,
    # never summed across entrants).
    field_columns = {c.name for c in GameFieldRow.__table__.columns}
    assert not any("fee" in name for name in field_columns)
    career_event_columns = {c.name for c in Base.metadata.tables["career_events"].columns}
    assert not any("fee" in name for name in career_event_columns)


def test_fee_is_not_a_capital_event_and_does_not_split_the_twr_chain():
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    run_id = uuid4()
    sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    stats = run_game_nav_snapshot_tick(now=_NOW, trading_day=lambda: _DAY_1)
    assert stats["written"] == 1

    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=5,
    )
    assert result.accepted

    stats = run_game_nav_snapshot_tick(now=_NOW, trading_day=lambda: _DAY_2)
    assert stats["written"] == 1

    with get_session() as s:
        rows = s.execute(
            select(PortfolioNavDailyRow)
            .where(PortfolioNavDailyRow.run_id == run_id)
            .order_by(PortfolioNavDailyRow.as_of_date)
        ).scalars().all()
    assert [r.as_of_date for r in rows] == [_DAY_1, _DAY_2]
    assert rows[0].capital_event == "open"  # the run's own entry, not the fee
    assert rows[1].capital_event is None    # the fee-charged day carries NO event

    navs = [
        NavPoint(as_of=r.as_of_date, nav=float(r.nav), capital_event=r.capital_event)
        for r in rows
    ]
    sub_periods = sub_period_returns(navs)
    assert len(sub_periods) == 1, (
        "a capital_event=None row must not split the TWR chain — two "
        "sub-periods here would mean the fee is being treated as a "
        "capital event"
    )
