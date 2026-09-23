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
    _PENDING_STATES,
    _TERMINAL_NOT_FILLED_STATES,
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
    assert row["other"] == 0


def test_all_seven_resting_order_states_are_bucketed() -> None:
    """CR200-R001 audit MINOR-1. Pins ticker_orders' three buckets
    (filled/pending/not_filled) against SimRestingOrderRow's seven documented
    states (models.py, via sim_engine.RestingOrderState) — an eighth state
    added to the model without updating this union must fail here, not
    vanish silently into an admin's totals.
    """
    from typing import get_args

    from app.services.sim_engine import RestingOrderState

    documented = set(get_args(RestingOrderState))
    covered = {"filled"} | set(_PENDING_STATES) | set(_TERMINAL_NOT_FILLED_STATES)
    assert covered == documented


def test_unrecognised_state_is_counted_not_dropped() -> None:
    """The loud-degrade fallback (CR040): a state outside the three known
    buckets must still be counted somewhere, never silently disappear from
    the ticker's total. Constructs the row directly (bypassing the DB
    constraint that would normally reject an unknown state) to exercise the
    aggregation function's own defence, independent of whether the model
    layer could ever actually produce one.
    """
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    with get_session() as s:
        s.add(SimRestingOrderRow(
            user_id=uid, portfolio_id=pid, ticker="ZZZZ",
            side="buy", quantity=5, order_type="limit", limit_price=90,
            tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            state="partially_filled", placed_at=datetime.now(timezone.utc),
        ))

    result = ticker_orders(days=30, limit=25)
    row = next(t for t in result["tickers"] if t["ticker"] == "ZZZZ")
    assert row["other"] == 1
    assert row["filled"] + row["pending"] + row["not_filled"] + row["other"] == 1


def test_high_volume_unrecognised_ticker_survives_the_limit_cut() -> None:
    """CR200-R001 audit round-2 MINOR-2. The ranking key used to sum only
    filled/pending/not_filled, so a ticker whose orders were ALL unrecognised
    ranked with key 0 -- below every ticker with a single recognised order --
    and [:limit] silently dropped it from the response. `other` must count
    toward rank, or the loudest possible vocabulary-drift signal (a ticker
    generating many unrecognised orders) is exactly the one the admin never
    sees.
    """
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    with get_session() as s:
        for i in range(30):
            s.add(SimRestingOrderRow(
                user_id=uid, portfolio_id=pid, ticker="GHOST",
                side="buy", quantity=1, order_type="limit", limit_price=90,
                tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
                state="partially_filled", placed_at=datetime.now(timezone.utc),
            ))
        s.add(SimRestingOrderRow(
            user_id=uid, portfolio_id=pid, ticker="QUIET",
            side="buy", quantity=1, order_type="limit", limit_price=90,
            tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            state="working", placed_at=datetime.now(timezone.utc),
        ))
        for n in range(30):
            s.add(SimRestingOrderRow(
                user_id=uid, portfolio_id=pid, ticker=f"FILLER{n}",
                side="buy", quantity=1, order_type="limit", limit_price=90,
                tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
                state="working", placed_at=datetime.now(timezone.utc),
            ))

    result = ticker_orders(days=30, limit=25)
    tickers = {t["ticker"] for t in result["tickers"]}
    assert "GHOST" in tickers, "the 30-order unrecognised-state ticker was truncated out"
    ghost = next(t for t in result["tickers"] if t["ticker"] == "GHOST")
    assert ghost["other"] == 30


def _mk_orders(uid: UUID, pid: UUID, ticker: str, state: str, n: int) -> None:
    with get_session() as s:
        for _ in range(n):
            s.add(SimRestingOrderRow(
                user_id=uid, portfolio_id=pid, ticker=ticker,
                side="buy", quantity=1, order_type="limit", limit_price=90,
                tif="day", expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
                state=state, placed_at=datetime.now(timezone.utc),
            ))


def test_ticker_orders_ranks_by_total_volume_and_cuts_the_quietest() -> None:
    """CR200-R001 audit round-3 MINOR-3. The [:limit] cut must keep the
    busiest and drop the quietest, ranked by total order volume across
    every bucket -- pins ORDER, not just membership. A ranking key that
    names a subset of buckets (e.g. only `other`, or a constant) can keep
    the right rows VISIBLE by accident while returning them in an order
    that is not "by volume" at all; the prior two findings on this same
    line were both membership gaps that a membership-only test could not
    have told apart from a correct fix.
    """
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    # 30 tickers, strictly descending volume: BUSY0 = 30 orders ... BUSY29 = 1.
    for i in range(30):
        _mk_orders(uid, pid, f"BUSY{i}", "working", 30 - i)

    result = ticker_orders(days=30, limit=5)
    assert [t["ticker"] for t in result["tickers"]] == [
        "BUSY0", "BUSY1", "BUSY2", "BUSY3", "BUSY4",
    ]


def test_ticker_orders_ranks_across_mixed_buckets_by_total() -> None:
    """A ticker whose volume is spread across all four buckets must still
    outrank one with a lower total concentrated in a single bucket -- the
    ranking key sums the whole row, not just whichever bucket a given
    order happened to land in.
    """
    uid = _mk_user()
    pid = _mk_portfolio(uid)
    pid2 = _mk_portfolio(_mk_user())
    _mk_orders(uid, pid, "MIX", "working", 5)
    _mk_orders(uid, pid, "MIX", "cancelled", 5)
    _mk_orders(uid, pid, "MIX", "partially_filled", 5)
    _mk_orders(uid, pid, "LESS", "working", 10)

    result = ticker_orders(days=30, limit=25)
    tickers = [t["ticker"] for t in result["tickers"]]
    assert tickers.index("MIX") < tickers.index("LESS")


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
