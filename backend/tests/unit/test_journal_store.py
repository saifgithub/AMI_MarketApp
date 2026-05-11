"""Tests for the Decision Journal store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas import Plan
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.services.journal_store import JournalStore


def _draft(user_id, **kw) -> JournalEntryCreate:
    return JournalEntryCreate(
        user_id=user_id,
        entry_type=kw.pop("entry_type", EntryType.ONE_ON_ONE),
        title=kw.pop("title", "test entry"),
        **kw,
    )


def test_append_and_list_for_user():
    store = JournalStore()
    user_id = uuid4()
    store.append(_draft(user_id, title="A", entry_type=EntryType.ONE_ON_ONE))
    store.append(_draft(user_id, title="B", entry_type=EntryType.AGENT_COACH))
    entries, total, retention = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total == 2
    assert retention is None  # paid tiers unlimited
    assert {e.title for e in entries} == {"A", "B"}


def test_floor_pass_30_day_retention():
    store = JournalStore()
    user_id = uuid4()
    # Append + manually backdate one entry to 31 days ago
    e_old = store.append(_draft(user_id, title="old"))
    # mutate created_at directly (store is in-memory)
    store._entries[user_id][0] = e_old.model_copy(
        update={"created_at": datetime.now(timezone.utc) - timedelta(days=31)}
    )
    store.append(_draft(user_id, title="new"))
    entries, total, retention = store.list_for_user(user_id, plan=Plan.FLOOR_PASS)
    assert retention == 30
    assert total == 1
    assert entries[0].title == "new"

    # Trader sees both
    _, total_paid, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total_paid == 2


def test_filter_by_entry_type_and_ticker():
    store = JournalStore()
    user_id = uuid4()
    store.append(_draft(user_id, title="aapl chat", ticker="AAPL"))
    store.append(_draft(user_id, title="msft chat", ticker="MSFT"))
    store.append(_draft(
        user_id, title="coach", ticker="AAPL", entry_type=EntryType.AGENT_COACH
    ))
    only_aapl, _, _ = store.list_for_user(user_id, plan=Plan.TRADER, ticker="aapl")
    assert {e.title for e in only_aapl} == {"aapl chat", "coach"}
    coach_only, _, _ = store.list_for_user(
        user_id, plan=Plan.TRADER, entry_type=EntryType.AGENT_COACH
    )
    assert [e.title for e in coach_only] == ["coach"]


def test_annotate_writes_note_tags_outcome():
    store = JournalStore()
    user_id = uuid4()
    e = store.append(_draft(user_id, title="t"))
    updated = store.annotate(
        user_id, e.id, note="this was a great call", tags=["semi", "win"], outcome=Outcome.WIN,
    )
    assert updated is not None
    assert updated.user_note == "this was a great call"
    assert updated.tags == ["semi", "win"]
    assert updated.outcome == "win"


def test_get_returns_none_for_unknown():
    store = JournalStore()
    assert store.get(uuid4(), uuid4()) is None
