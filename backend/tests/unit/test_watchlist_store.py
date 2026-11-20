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


def test_add_that_loses_the_race_returns_the_winners_row_and_applies_notes(monkeypatch):
    """ISS001 / DEF308: the winner commits between the ticker check and the insert. The loser must
    get the winner's row (no IntegrityError, no second row) and its notes still apply."""
    from app.db import get_session
    from app.db.ami_claim import claim
    from app.db.models import SimWatchlistRow
    from app.services import watchlist_store

    store = get_watchlist_store()
    user_id = uuid4()
    real_check = watchlist_store.require_ticker_exists

    def check_then_winner_commits(session, ticker):
        real_check(session, ticker)
        with get_session() as other:
            claim(other, SimWatchlistRow, key={"user_id": user_id, "ticker": ticker}, values={"notes": "winner"}).or_skip()

    monkeypatch.setattr(watchlist_store, "require_ticker_exists", check_then_winner_commits)
    entry = store.add(user_id, "NVDA", notes="loser")
    monkeypatch.undo()
    entries = store.list_for_user(user_id)
    assert len(entries) == 1
    assert entries[0].id == entry.id
    assert entries[0].notes == "loser"


def test_add_that_loses_the_race_without_notes_keeps_the_winners_notes(monkeypatch):
    from app.db import get_session
    from app.db.ami_claim import claim
    from app.db.models import SimWatchlistRow
    from app.services import watchlist_store

    store = get_watchlist_store()
    user_id = uuid4()
    real_check = watchlist_store.require_ticker_exists

    def check_then_winner_commits(session, ticker):
        real_check(session, ticker)
        with get_session() as other:
            claim(other, SimWatchlistRow, key={"user_id": user_id, "ticker": ticker}, values={"notes": "winner"}).or_skip()

    monkeypatch.setattr(watchlist_store, "require_ticker_exists", check_then_winner_commits)
    store.add(user_id, "MSFT")
    monkeypatch.undo()
    assert [e.notes for e in store.list_for_user(user_id)] == ["winner"]
