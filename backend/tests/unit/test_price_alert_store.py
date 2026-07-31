"""PriceAlertStore — CR027 §4."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.price_alert import PriceAlertCreate
from app.services.price_alert_store import (
    MAX_ACTIVE_ALERTS_PER_USER,
    PriceAlertConflictError,
    get_price_alert_store,
)


def _create(store, user_id, ticker="AAPL", threshold_type="stop", price=150.0, trade_ref=None):
    return store.create(
        user_id,
        PriceAlertCreate(
            ticker=ticker, threshold_type=threshold_type, threshold_price=price,
            trade_ref=trade_ref,
        ),
    )


def test_create_and_list_for_user():
    store = get_price_alert_store()
    user_id = uuid4()
    created = _create(store, user_id)
    assert created.status == "active"
    assert created.ticker == "AAPL"

    listed = store.list_for_user(user_id)
    assert len(listed) == 1
    assert listed[0].id == created.id


def test_ticker_is_normalized_uppercase():
    store = get_price_alert_store()
    user_id = uuid4()
    created = _create(store, user_id, ticker="aapl")
    assert created.ticker == "AAPL"


def test_unknown_ticker_rejected():
    store = get_price_alert_store()
    with pytest.raises(Exception):  # TickerNotFoundError, a ValueError subclass
        _create(store, uuid4(), ticker="ZZZNOTREAL")


def test_list_for_user_does_not_leak_other_users_alerts():
    store = get_price_alert_store()
    a, b = uuid4(), uuid4()
    _create(store, a)
    assert store.list_for_user(b) == []


def test_cancel_marks_cancelled_and_stops_listing_as_active():
    store = get_price_alert_store()
    user_id = uuid4()
    created = _create(store, user_id)
    cancelled = store.cancel(user_id, created.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None
    assert store.list_for_user(user_id, status="active") == []


def test_cancel_unknown_alert_returns_none():
    store = get_price_alert_store()
    assert store.cancel(uuid4(), uuid4()) is None


def test_cancel_another_users_alert_returns_none():
    store = get_price_alert_store()
    owner, other = uuid4(), uuid4()
    created = _create(store, owner)
    assert store.cancel(other, created.id) is None


def test_cancel_terminal_alert_is_conflict_not_silent():
    store = get_price_alert_store()
    user_id = uuid4()
    created = _create(store, user_id)
    store.cancel(user_id, created.id)  # now cancelled
    with pytest.raises(PriceAlertConflictError):
        store.cancel(user_id, created.id)


def test_eleventh_active_alert_auto_cancels_oldest():
    store = get_price_alert_store()
    user_id = uuid4()
    created = [_create(store, user_id, price=100.0 + i) for i in range(MAX_ACTIVE_ALERTS_PER_USER + 1)]

    active = store.list_for_user(user_id, status="active")
    assert len(active) == MAX_ACTIVE_ALERTS_PER_USER

    active_ids = {a.id for a in active}
    assert created[0].id not in active_ids  # the very first (oldest) got closed
    assert all(c.id in active_ids for c in created[1:])  # every later one survives

    cancelled = store.list_for_user(user_id, status="cancelled")
    assert len(cancelled) == 1
    assert cancelled[0].id == created[0].id


def test_trade_ref_must_belong_to_same_user():
    from app.db import get_session
    from app.db.models import SimPortfolioRow, SimTradeRow

    store = get_price_alert_store()
    owner, other = uuid4(), uuid4()
    with get_session() as s:
        portfolio = SimPortfolioRow(user_id=other, starting_capital=10_000, current_cash=10_000)
        s.add(portfolio)
        s.flush()
        trade = SimTradeRow(
            user_id=other, portfolio_id=portfolio.id, ticker="AAPL", side="buy",
            quantity=1, entry_price=150.0,
        )
        s.add(trade)
        s.flush()
        trade_id = trade.id

    with pytest.raises(ValueError):
        _create(store, owner, trade_ref=trade_id)
