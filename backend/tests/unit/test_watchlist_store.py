"""WatchlistStore tests (A18) — add/list/remove/idempotency."""

from __future__ import annotations

from uuid import uuid4

from app.services.watchlist_store import get_watchlist_store


def test_add_then_list_returns_entry():
    store = get_watchlist_store()
    user_id = uuid4()
    store.add(user_id, "NVDA", notes="watching the Blackwell ramp")
    entries = store.list_for_user(user_id)
    assert len(entries) == 1
    assert entries[0].ticker == "NVDA"
    assert entries[0].notes == "watching the Blackwell ramp"


def test_ticker_is_normalised_uppercase():
    store = get_watchlist_store()
    user_id = uuid4()
    store.add(user_id, "  msft  ")
    entries = store.list_for_user(user_id)
    assert entries[0].ticker == "MSFT"


def test_add_is_idempotent_and_updates_notes():
    store = get_watchlist_store()
    user_id = uuid4()
    store.add(user_id, "AAPL")
    store.add(user_id, "AAPL", notes="earnings next week")
    entries = store.list_for_user(user_id)
    assert len(entries) == 1
    assert entries[0].notes == "earnings next week"


def test_remove_works_and_returns_false_when_absent():
    store = get_watchlist_store()
    user_id = uuid4()
    store.add(user_id, "TSLA")
    assert store.remove(user_id, "TSLA") is True
    assert store.list_for_user(user_id) == []
    # Removing again is a no-op
    assert store.remove(user_id, "TSLA") is False


def test_list_orders_by_added_at_desc():
    store = get_watchlist_store()
    user_id = uuid4()
    store.add(user_id, "AAPL")
    store.add(user_id, "MSFT")
    store.add(user_id, "GOOGL")
    tickers = [e.ticker for e in store.list_for_user(user_id)]
    assert tickers == ["GOOGL", "MSFT", "AAPL"]


def test_empty_ticker_rejected():
    store = get_watchlist_store()
    user_id = uuid4()
    import pytest
    with pytest.raises(ValueError):
        store.add(user_id, "   ")


def test_per_user_isolation():
    store = get_watchlist_store()
    a = uuid4()
    b = uuid4()
    store.add(a, "AAPL")
    store.add(b, "NVDA")
    assert [e.ticker for e in store.list_for_user(a)] == ["AAPL"]
    assert [e.ticker for e in store.list_for_user(b)] == ["NVDA"]
