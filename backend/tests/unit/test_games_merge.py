"""CR109 slice 2 — merge_service.py must keep a user's game runs across an
anonymous->claimed account merge (implementation_plan.md §9 test matrix
item 9 / §12 "Anonymous -> claimed mid-run"). Covers the tables THIS CR
adds: the game portfolio row, its trades, `game_entries`,
`game_queued_orders`, and the run's own `portfolio_nav_daily` rows.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    GameEntryRow,
    GameQueuedOrderRow,
    PortfolioNavDailyRow,
    SimPortfolioRow,
    SimTradeRow,
    User,
)
from app.schemas.trade import Side
from app.services.auth_service import AuthService
from app.services.games_service import enter_field, submit_trade
from app.services.merge_service import MergeService
from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick
from app.services.sim_engine import get_sim_engine

# Sunday 23:00 ET — field entry_open, market closed (queues the trade).
_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_DAY_1 = date(2026, 8, 10)


def _make_users() -> tuple[User, User]:
    """Two anonymous users — `orphan` (pre-claim) and `adopter` (the
    account it merges into). Mirrors test_merge_service.py's own helper."""
    auth = AuthService()
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        orphan = s.execute(select(User).where(User.id == orphan_au.id)).scalar_one()
        adopter = s.execute(select(User).where(User.id == adopter_au.id)).scalar_one()
        adopter.email = "adopter@example.com"
        adopter.is_anonymous = False
        adopter.claimed_at = datetime.now(timezone.utc)
        return orphan, adopter


def test_claimed_account_keeps_its_game_run():
    orphan, adopter = _make_users()
    entry = enter_field(orphan.id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id

    submit_trade(
        orphan.id, run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_ENTRY_OPEN_CLOSED_MARKET,
    )  # queues (market closed) — GameQueuedOrderRow must survive too
    run_game_nav_snapshot_tick(now=_ENTRY_OPEN_CLOSED_MARKET, trading_day=lambda: _DAY_1)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        # The orphan row is gone.
        assert s.execute(
            select(User).where(User.id == orphan.id)
        ).scalar_one_or_none() is None

        moved_entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        assert moved_entry.user_id == adopter.id

        moved_portfolio = s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.run_id == run_id)
        ).scalar_one()
        assert moved_portfolio.user_id == adopter.id
        assert moved_portfolio.kind == "game"

        moved_queued = s.execute(
            select(GameQueuedOrderRow).where(GameQueuedOrderRow.run_id == run_id)
        ).scalar_one()
        assert moved_queued.user_id == adopter.id

        moved_nav = s.execute(
            select(PortfolioNavDailyRow).where(PortfolioNavDailyRow.run_id == run_id)
        ).scalar_one()
        assert moved_nav.user_id == adopter.id

    # The run is still readable, live, for the adopter — via the same
    # engine call the API route uses.
    sim = get_sim_engine()
    portfolio = sim.ensure_portfolio(adopter.id, kind="game", run_id=run_id)
    assert portfolio.current_cash == pytest.approx(10_000.0)  # order was queued, not filled


def test_merged_game_trades_move_without_touching_the_training_portfolio():
    """A regression guard for the pre-CR109-slice-2 bug this fix closes:
    re-keying game trades must not also sweep the TRAINING portfolio's
    trades, and vice versa — they are scoped by `portfolio_id` now, not by
    a blanket `user_id` match."""
    orphan, adopter = _make_users()
    sim = get_sim_engine()

    # A training trade for the orphan (kind defaults to "training").
    from app.services.coach_engine import hydrate_coach_mandate

    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    training_result = sim.submit(
        user_id=orphan.id, ticker="MSFT", side=Side.BUY, quantity=1, mandate=mandate,
    )
    assert training_result.accepted

    entry = enter_field(orphan.id, now=_ENTRY_OPEN_CLOSED_MARKET)
    run_id = entry.run_id
    game_result = sim.submit_game_trade(
        user_id=orphan.id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=1,
    )
    assert game_result.accepted

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        training_trades = s.execute(
            select(SimTradeRow).where(
                SimTradeRow.user_id == adopter.id, SimTradeRow.ticker == "MSFT",
            )
        ).scalars().all()
        game_trades = s.execute(
            select(SimTradeRow).where(
                SimTradeRow.user_id == adopter.id, SimTradeRow.ticker == "AAPL",
            )
        ).scalars().all()
    assert len(training_trades) == 1
    assert len(game_trades) == 1

    training_portfolio = sim.ensure_portfolio(adopter.id)  # kind="training"
    assert any(h.ticker == "MSFT" for h in training_portfolio.holdings)
    game_portfolio = sim.ensure_portfolio(adopter.id, kind="game", run_id=run_id)
    assert any(h.ticker == "AAPL" for h in game_portfolio.holdings)
