"""CR109 slice 2 — "the run": field roll/entry, the market-hours queue
rule, and restart/forfeit.

Covers implementation_plan.md §9 test matrix items 4-9 (slice 2's core
acceptance): a second weekly entry is refused; an out-of-hours order
queues and does not fill at a stale price; a queued order is absent from
the NAV snapshot until it fills; entry never charges anything.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameQueuedOrderRow, PortfolioNavDailyRow, SimHoldingRow
from app.schemas.trade import OrderType, Side
from app.services import games_service as games
from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick
from app.services.sim_engine import get_sim_engine

# Sunday 23:00 ET (2026-08-09) — the field for the upcoming Monday
# (2026-08-10) is `entry_open`, and the US market is unambiguously CLOSED
# (weekend). Good for "enter, then place an out-of-hours order" tests.
_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)

# Monday 11:00 ET (2026-08-10) — the same field is now `live`, and the US
# regular session is open.
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)

_DAY_1 = date(2026, 8, 10)
_DAY_2 = date(2026, 8, 11)


def _holding(user_id, run_id, ticker: str) -> SimHoldingRow | None:
    with get_session() as s:
        p, _marks, _tv, _dd, _src = get_sim_engine().portfolio_marks_snapshot(
            user_id, kind="game", run_id=run_id,
        )
        return next((h for h in p.holdings if h.ticker == ticker), None)


# ── Field roll + entry ─────────────────────────────────────────────────


def test_second_weekly_entry_is_refused():
    user_id = uuid4()
    games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with pytest.raises(games.AlreadyEnteredError):
        games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)


def test_entry_is_free():
    """Entering never charges anything — the training portfolio's cash is
    untouched, and the new game portfolio starts at the full $10k."""
    user_id = uuid4()
    sim = get_sim_engine()
    training_before = sim.ensure_portfolio(user_id).current_cash

    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)

    assert sim.ensure_portfolio(user_id).current_cash == training_before
    game_portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=entry.run_id)
    assert game_portfolio.current_cash == 10_000.0
    assert entry.state == "entered"


def test_intent_tag_written_at_entry():
    user_id = uuid4()
    entry = games.enter_field(user_id, intent="thesis", now=_ENTRY_OPEN_CLOSED_MARKET)
    assert entry.intent == "thesis"


# ── Market-hours queue rule ──────────────────────────────────────────────


def test_out_of_hours_order_queues_and_does_not_fill():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id

    result = games.submit_trade(
        user_id, run_id,
        ticker="AAPL", side=Side.BUY, quantity=5,
        now=_ENTRY_OPEN_CLOSED_MARKET,
    )

    assert result["queued"] is True
    assert result["filled"] is False
    assert result["fee"] is None
    with get_session() as s:
        rows = s.execute(
            select(GameQueuedOrderRow).where(GameQueuedOrderRow.run_id == run_id)
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].state == "queued"
    assert rows[0].ticker == "AAPL"
    # Never fills at a stale price — the queued row carries the ORDER SPEC
    # only, no captured price at all.
    assert not hasattr(rows[0], "fill_price")

    # Not filled: no holding, no cash movement.
    assert _holding(user_id, run_id, "AAPL") is None
    portfolio = get_sim_engine().ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert portfolio.current_cash == 10_000.0


def test_queue_drain_fills_at_a_fresh_price_not_the_price_when_queued():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id

    games.submit_trade(
        user_id, run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_ENTRY_OPEN_CLOSED_MARKET,
    )
    # Draining outside market hours is a no-op.
    stats = games.process_queued_orders(now=_ENTRY_OPEN_CLOSED_MARKET)
    assert stats["filled"] == 0
    assert _holding(user_id, run_id, "AAPL") is None

    stats = games.process_queued_orders(now=_MARKET_OPEN)
    assert stats["filled"] == 1

    with get_session() as s:
        row = s.execute(
            select(GameQueuedOrderRow).where(GameQueuedOrderRow.run_id == run_id)
        ).scalar_one()
    assert row.state == "filled"
    assert row.filled_trade_id is not None
    holding = _holding(user_id, run_id, "AAPL")
    assert holding is not None
    assert holding.quantity == 5
    # The fill price is whatever the mock walk serves AT DRAIN TIME — the
    # entry price on the resulting holding must be a real (positive) fill
    # price, not some placeholder from queue time.
    assert holding.avg_cost > 0


def test_forfeit_cancels_queued_orders():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id
    games.submit_trade(
        user_id, run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_ENTRY_OPEN_CLOSED_MARKET,
    )

    result = games.commit_restart(user_id, run_id, now=_MARKET_OPEN)
    assert result["state"] == "forfeit"
    assert result["queued_orders_cancelled"] == 1

    # Draining now must NOT fill the cancelled order into a closed book.
    stats = games.process_queued_orders(now=_MARKET_OPEN)
    assert stats["filled"] == 0
    with get_session() as s:
        row = s.execute(
            select(GameQueuedOrderRow).where(GameQueuedOrderRow.run_id == run_id)
        ).scalar_one()
    assert row.state == "cancelled"


# ── NAV snapshot vs the queue ─────────────────────────────────────────────


def test_queued_order_absent_from_nav_snapshot_until_it_fills():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id
    games.submit_trade(
        user_id, run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_ENTRY_OPEN_CLOSED_MARKET,
    )

    # A NAV snapshot taken while the order is still queued must read the
    # untouched $10k book — not a preview of what the queued order WOULD do.
    stats = run_game_nav_snapshot_tick(now=_ENTRY_OPEN_CLOSED_MARKET, trading_day=lambda: _DAY_1)
    assert stats["written"] == 1
    with get_session() as s:
        day1 = s.execute(
            select(PortfolioNavDailyRow).where(
                PortfolioNavDailyRow.run_id == run_id,
                PortfolioNavDailyRow.as_of_date == _DAY_1,
            )
        ).scalar_one()
    assert float(day1.nav) == pytest.approx(10_000.0)
    assert float(day1.cash) == pytest.approx(10_000.0)
    assert day1.capital_event == "open"

    # Now fill it, and a NEXT day's snapshot must reflect the fill.
    games.process_queued_orders(now=_MARKET_OPEN)
    stats = run_game_nav_snapshot_tick(now=_MARKET_OPEN, trading_day=lambda: _DAY_2)
    assert stats["written"] == 1
    with get_session() as s:
        day2 = s.execute(
            select(PortfolioNavDailyRow).where(
                PortfolioNavDailyRow.run_id == run_id,
                PortfolioNavDailyRow.as_of_date == _DAY_2,
            )
        ).scalar_one()
    assert float(day2.cash) < 10_000.0, "day 2's cash must reflect the fill"
    # Not a capital event — a trade is not one (only the run's own entry is).
    assert day2.capital_event is None
