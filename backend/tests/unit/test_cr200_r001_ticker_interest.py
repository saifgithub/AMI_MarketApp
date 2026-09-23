"""CR200-R001 — ticker interest analytics: real-user exclusion, per-ticker
grouping, and the filled/pending/not-filled split.

Covers: top_tickers groups room_runs by ticker and excludes room-benchmark
synthetics; ticker_orders sums sim_trades as filled and sim_resting_orders by
state bucket (working/triggered/filling -> pending, cancelled/expired/rejected
-> not_filled); watchlist_interest counts sim_watchlists adds; ticker_detail
returns one symbol's full history; the admin route is get_admin-gated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_ticker_interest import router as ticker_interest_router
from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import (
    RoomRunRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimRestingOrderRow,
    SimTradeRow,
    SimWatchlistRow,
    User,
)
from app.services.admin_analytics import _EXCLUDED_USER_IDS
from app.services.ticker_interest import (
    ticker_detail,
    ticker_orders,
    top_tickers,
    watchlist_interest,
)

_SECRET = "test-admin-secret-ticker-interest"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


def _mk_user(
    user_id: UUID | None = None,
    last_app_version: str | None = "0.1.0+70",
) -> UUID:
    init_schema()
    uid = user_id or uuid4()
    with get_session() as s:
        s.add(User(
            id=uid,
            plan="floor_pass",
            credit_balance=8,
            is_anonymous=True,
            last_app_version=last_app_version,
            created_at=datetime.now(timezone.utc),
        ))
    return uid


def _mk_room_run(user_id: UUID, ticker: str, status: str = "complete", credit_cost: int = 2) -> None:
    with get_session() as s:
        s.add(RoomRunRow(
            user_id=user_id, ticker=ticker, triggered_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status=status, credit_cost=credit_cost,
        ))


def _mk_portfolio(user_id: UUID) -> UUID:
    pid = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=pid, user_id=user_id, kind="training",
            starting_capital=100000, current_cash=100000,
        ))
    return pid


def _mk_trade(user_id: UUID, portfolio_id: UUID, ticker: str) -> None:
    # conftest's end-of-test invariant reconciles sim_trades against
    # sim_holdings for any (portfolio, ticker) the engine would have touched —
    # a hand-seeded trade row needs its matching holding row too.
    with get_session() as s:
        s.add(SimTradeRow(
            user_id=user_id, portfolio_id=portfolio_id, ticker=ticker,
            side="buy", quantity=10, entry_price=100, status="open",
            opened_at=datetime.now(timezone.utc),
        ))
        s.add(SimHoldingRow(
            portfolio_id=portfolio_id, ticker=ticker, quantity=10, avg_cost=100,
        ))


def _mk_resting_order(user_id: UUID, portfolio_id: UUID, ticker: str, state: str) -> None:
    with get_session() as s:
        s.add(SimRestingOrderRow(
            user_id=user_id, portfolio_id=portfolio_id, ticker=ticker,
            side="buy", quantity=5, order_type="limit", limit_price=90,
            tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            state=state, placed_at=datetime.now(timezone.utc),
        ))


def _mk_watchlist(user_id: UUID, ticker: str) -> None:
    with get_session() as s:
        s.add(SimWatchlistRow(
            user_id=user_id, ticker=ticker, added_at=datetime.now(timezone.utc),
        ))


def test_top_tickers_groups_and_excludes_synthetics() -> None:
    real = _mk_user()
    synthetic = _mk_user(last_app_version="room-benchmark")
    _mk_room_run(real, "NVDA", status="complete")
    _mk_room_run(real, "NVDA", status="error")
    _mk_room_run(synthetic, "NVDA")

    result = top_tickers(days=30, limit=25)
    row = next(t for t in result["tickers"] if t["ticker"] == "NVDA")
    assert row["runs"] == 2
    assert row["researchers"] == 1
    assert row["by_status"] == {"complete": 1, "error": 1}


def test_ticker_orders_splits_filled_pending_not_filled() -> None:
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    _mk_trade(uid, pid, "TSLA")
    _mk_resting_order(uid, pid, "TSLA", "working")
    _mk_resting_order(uid, pid, "TSLA", "triggered")
    _mk_resting_order(uid, pid, "TSLA", "rejected")

    result = ticker_orders(days=30, limit=25)
    row = next(t for t in result["tickers"] if t["ticker"] == "TSLA")
    assert row["filled"] == 1
    assert row["pending"] == 2
    assert row["not_filled"] == 1


def test_watchlist_interest_counts_adds() -> None:
    u1, u2 = _mk_user(), _mk_user()
    _mk_watchlist(u1, "AMD")
    _mk_watchlist(u2, "AMD")

    result = watchlist_interest(days=30, limit=25)
    row = next(t for t in result["tickers"] if t["ticker"] == "AMD")
    assert row["watchlist_adds"] == 2


def test_ticker_orders_excludes_probe_user() -> None:
    probe = _mk_user(user_id=_EXCLUDED_USER_IDS[0])
    pid = _mk_portfolio(probe)
    _mk_trade(probe, pid, "MSFT")

    result = ticker_orders(days=30, limit=25)
    assert not any(t["ticker"] == "MSFT" for t in result["tickers"])


def test_ticker_detail_returns_full_history() -> None:
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    _mk_room_run(uid, "GOOG")
    _mk_trade(uid, pid, "GOOG")
    _mk_resting_order(uid, pid, "GOOG", "working")
    _mk_watchlist(uid, "GOOG")

    d = ticker_detail("GOOG", days=90)
    assert d["ticker"] == "GOOG"
    assert len(d["room_runs"]) == 1
    assert len(d["trades"]) == 1
    assert len(d["resting_orders"]) == 1
    assert d["watchlist_adds"] == 1


def test_admin_route_gated() -> None:
    init_schema()
    app = FastAPI()
    app.include_router(ticker_interest_router)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/v1/admin/ticker-interest/top", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/ticker-interest/orders", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/ticker-interest/watchlist", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/ticker-interest/detail/AAPL", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/ticker-interest/top").status_code == 403
