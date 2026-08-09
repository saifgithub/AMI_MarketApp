"""CR109 slice 1 — the daily NAV snapshot tick: reset-immunity fence,
idempotency, mock-day flagging (CR040), and the capital_event inference the
TWR chain (`trading_math/twr.py`) depends on.

Mirrors `test_portfolio_snapshot.py` (CR136 M03)'s shape — same idempotent-
tick pattern — but this table's contract is the opposite on mock data: M03
REFUSES a mock-priced day, this tick WRITES it and flags it, because a hole
in the equity-curve spine is a worse lie than a flagged mock day.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db import get_session
from app.db.models import PortfolioNavDailyRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.portfolio_nav_daily import (
    nav_history,
    run_portfolio_nav_snapshot_tick,
    twr_pct_for_window,
)
from app.services.sim_engine import get_sim_engine

_DAY_1 = date(2026, 8, 3)
_DAY_2 = date(2026, 8, 4)


def _tick(**kwargs):
    kwargs.setdefault("trading_day", lambda: _DAY_1)
    return run_portfolio_nav_snapshot_tick(**kwargs)


def _rows_for(user_id) -> list[PortfolioNavDailyRow]:
    with get_session() as s:
        return list(s.execute(
            select(PortfolioNavDailyRow)
            .where(PortfolioNavDailyRow.user_id == user_id)
            .order_by(PortfolioNavDailyRow.as_of_date)
        ).scalars().all())


def _row_count() -> int:
    with get_session() as s:
        return s.execute(
            select(func.count()).select_from(PortfolioNavDailyRow)
        ).scalar_one()


# ── T1. The fence ────────────────────────────────────────────────────────


def test_nav_snapshot_survives_reset_portfolio() -> None:
    """FENCE (implementation plan §4.1): `portfolio_nav_daily` carries NO FK
    to `sim_portfolios`. `reset_portfolio()` hard-deletes the portfolio row
    and every trade and replaces the portfolio with a brand-new UUID; the
    stored NAV history must not move."""
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    _tick()
    rows_before = _rows_for(user_id)
    assert len(rows_before) == 1
    surviving_id = rows_before[0].id

    sim.reset_portfolio(user_id)

    rows_after = _rows_for(user_id)
    assert len(rows_after) == 1, "reset_portfolio() must not touch portfolio_nav_daily"
    assert rows_after[0].id == surviving_id
    assert rows_after[0].as_of_date == _DAY_1
    assert float(rows_after[0].nav) == pytest.approx(10_000.0)


# ── T2. Idempotency ──────────────────────────────────────────────────────


def test_tick_is_idempotent_for_the_same_trading_day() -> None:
    sim = get_sim_engine()
    for _ in range(3):
        sim.ensure_portfolio(uuid4())

    first = _tick()
    assert first["written"] == 3
    assert first["skipped_existing"] == 0

    second = _tick()
    assert second["written"] == 0
    assert second["skipped_existing"] == 3
    assert _row_count() == 3


def test_no_trading_day_is_a_loud_no_op() -> None:
    get_sim_engine().ensure_portfolio(uuid4())
    stats = run_portfolio_nav_snapshot_tick(trading_day=lambda: None)
    assert stats["as_of"] == "none"
    assert stats["written"] == 0
    assert _row_count() == 0


# ── T4. Mock-day flag (CR040) ────────────────────────────────────────────


def test_mock_priced_day_is_flagged_not_absorbed() -> None:
    """The whole test suite is pinned to `MockWalkProvider` (see
    `conftest.py`), so a holding's mark is always mock-sourced here. Unlike
    CR136 M03's sibling tick, this one must still WRITE the row — just
    flagged `price_source="mock"` — never silently refuse it."""
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert result.accepted

    stats = _tick()
    assert stats["written"] == 1

    rows = _rows_for(user_id)
    assert len(rows) == 1
    assert rows[0].price_source == "mock"


def test_cash_only_portfolio_still_writes_a_row() -> None:
    """No holdings means no quote fetch at all — the tick must not confuse
    'nothing to price' with 'refuse to write'."""
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    stats = _tick()
    assert stats["written"] == 1
    rows = _rows_for(user_id)
    assert float(rows[0].nav) == pytest.approx(10_000.0)
    assert float(rows[0].cash) == pytest.approx(10_000.0)


# ── T3 (integration half). capital_event feeds the TWR chain ────────────


def test_first_row_is_open_and_a_post_reset_row_is_restart() -> None:
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    _tick(trading_day=lambda: _DAY_1)
    rows = _rows_for(user_id)
    assert rows[0].capital_event == "open"

    sim.reset_portfolio(user_id)
    _tick(trading_day=lambda: _DAY_2)

    rows = _rows_for(user_id)
    assert len(rows) == 2
    assert rows[1].as_of_date == _DAY_2
    assert rows[1].capital_event == "restart"


def test_nav_history_and_twr_pct_read_the_stored_rows() -> None:
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    _tick(trading_day=lambda: _DAY_1)

    rows = nav_history(user_id)
    assert len(rows) == 1
    assert twr_pct_for_window(rows) is None, "one point — nothing to compound yet"
