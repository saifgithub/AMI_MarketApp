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
    # Shift created_at back 31 days via the test-only DB helper.
    store._backdate_for_test(
        user_id, e_old.id, datetime.now(timezone.utc) - timedelta(days=31),
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


def test_soft_delete_hides_entry_but_preserves_row():
    from sqlalchemy import select
    from app.db import get_session
    from app.db.models import JournalEntryRow

    store = JournalStore()
    user_id = uuid4()
    e = store.append(_draft(user_id, title="to delete"))

    assert store.soft_delete(user_id, e.id) is True

    # Entry is gone from all read APIs
    entries, total, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total == 0
    assert store.get(user_id, e.id) is None

    # But the raw row still exists in the DB with deleted_at set
    with get_session() as s:
        row = s.execute(
            select(JournalEntryRow).where(JournalEntryRow.id == e.id)
        ).scalar_one_or_none()
    assert row is not None
    assert row.deleted_at is not None


def test_soft_delete_returns_false_for_unknown():
    store = JournalStore()
    assert store.soft_delete(uuid4(), uuid4()) is False


def test_restore_brings_entry_back():
    store = JournalStore()
    user_id = uuid4()
    e = store.append(_draft(user_id, title="will be restored"))
    assert store.soft_delete(user_id, e.id) is True
    _, total_after_delete, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total_after_delete == 0

    assert store.restore(user_id, e.id) is True
    entries, total_after_restore, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total_after_restore == 1
    assert entries[0].title == "will be restored"


def test_restore_returns_false_for_non_deleted_or_unknown():
    store = JournalStore()
    user_id = uuid4()
    e = store.append(_draft(user_id, title="live entry"))
    # Live entry (not deleted) — restore is a no-op
    assert store.restore(user_id, e.id) is False
    # Truly unknown id
    assert store.restore(user_id, uuid4()) is False


def test_list_deleted_window_30_days():
    """Trash list returns only entries soft-deleted in the last 30 days."""
    from sqlalchemy import select
    from app.db import get_session
    from app.db.models import JournalEntryRow

    store = JournalStore()
    user_id = uuid4()

    # 1) live entry (should NOT appear in trash)
    store.append(_draft(user_id, title="live"))

    # 2) recently deleted (should appear)
    e_recent = store.append(_draft(user_id, title="recent trash"))
    store.soft_delete(user_id, e_recent.id)

    # 3) old deletion (>30 days ago — should NOT appear in trash list,
    #    but the row still exists in the DB)
    e_old = store.append(_draft(user_id, title="old trash"))
    store.soft_delete(user_id, e_old.id)
    # Backdate the deletion to 40 days ago.
    with get_session() as s:
        row = s.execute(
            select(JournalEntryRow).where(JournalEntryRow.id == e_old.id)
        ).scalar_one()
        row.deleted_at = datetime.now(timezone.utc) - timedelta(days=40)

    entries, total = store.list_deleted(user_id)
    assert total == 1
    assert entries[0].title == "recent trash"
    assert entries[0].deleted_at is not None

    # Old row still exists in DB and remains restorable
    assert store.restore(user_id, e_old.id) is True


def test_search_filters_by_title_and_summary():
    store = JournalStore()
    user_id = uuid4()
    store.append(_draft(user_id, title="AAPL analysis", summary="bullish thesis"))
    store.append(_draft(user_id, title="MSFT earnings", summary="beat expectations"))
    store.append(_draft(user_id, title="daily recap", summary="quiet session"))

    aapl, total_aapl, _ = store.list_for_user(user_id, plan=Plan.TRADER, q="AAPL")
    assert total_aapl == 1
    assert aapl[0].title == "AAPL analysis"

    bullish, total_bullish, _ = store.list_for_user(user_id, plan=Plan.TRADER, q="bullish")
    assert total_bullish == 1

    # Case-insensitive
    msft, _, _ = store.list_for_user(user_id, plan=Plan.TRADER, q="msft")
    assert len(msft) == 1
    assert msft[0].title == "MSFT earnings"

    # Empty q → all results
    all_e, total_all, _ = store.list_for_user(user_id, plan=Plan.TRADER, q="")
    assert total_all == 3
