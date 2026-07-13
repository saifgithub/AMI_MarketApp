"""DEF054/DEF055 — Bull/Bear Researcher must get real Decision Journal
history for the ticker being discussed, not the fabricated claim the
prompts made with nothing reading past entries back into a future run.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.mandate import Plan
from app.services.journal_context import (
    build_journal_context_block,
    fetch_recent_journal_entries,
    format_journal_entry,
)
from app.services.journal_store import get_journal_store


def _seed(user_id, ticker, title, outcome=None):
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ROOM_RUN,
        title=title, ticker=ticker, outcome=outcome,
    ))


def test_fetch_returns_real_entries_for_this_ticker():
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE", outcome=Outcome.WIN)
    _seed(user_id, "AAPL", "Room on AAPL — REJECT")
    _seed(user_id, "MSFT", "Room on MSFT — APPROVE")  # different ticker, must not leak in

    entries = fetch_recent_journal_entries(user_id, "AAPL")
    assert len(entries) == 2
    assert {e.title for e in entries} == {"Room on AAPL — APPROVE", "Room on AAPL — REJECT"}


def test_fetch_returns_empty_for_a_ticker_with_no_history():
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE")

    assert fetch_recent_journal_entries(user_id, "TSLA") == []


def test_fetch_returns_empty_for_anonymous_user():
    assert fetch_recent_journal_entries(None, "AAPL") == []


def test_fetch_never_raises_when_store_errors(monkeypatch):
    import app.services.journal_context as journal_context_module

    class _BoomStore:
        def list_for_user(self, *a, **kw):
            raise RuntimeError("db is on fire")

    monkeypatch.setattr(journal_context_module, "get_journal_store", lambda: _BoomStore())
    assert fetch_recent_journal_entries(uuid4(), "AAPL") == []


def test_format_journal_entry_includes_date_title_and_outcome():
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE", outcome=Outcome.WIN)
    entry = fetch_recent_journal_entries(user_id, "AAPL")[0]

    line = format_journal_entry(entry)
    assert "Room on AAPL — APPROVE" in line
    assert "win" in line
    assert entry.created_at.strftime("%Y-%m-%d") in line


def test_format_journal_entry_omits_outcome_when_absent():
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — REJECT")
    entry = fetch_recent_journal_entries(user_id, "AAPL")[0]

    line = format_journal_entry(entry)
    assert line == f"{entry.created_at.strftime('%Y-%m-%d')}: Room on AAPL — REJECT"


def test_build_context_block_none_when_no_history():
    assert build_journal_context_block(uuid4(), "AAPL") is None


def test_build_context_block_present_with_real_entries():
    user_id = uuid4()
    _seed(user_id, "AAPL", "Room on AAPL — APPROVE", outcome=Outcome.WIN)

    block = build_journal_context_block(user_id, "AAPL")
    assert block is not None
    assert "DECISION JOURNAL HISTORY — AAPL" in block
    assert "Room on AAPL — APPROVE" in block
    assert "win" in block


def test_build_context_block_caps_at_five_most_recent(monkeypatch):
    """DEF054's own MAX_ENTRIES cap keeps the prompt from becoming a wall
    of history — verify the fetch actually respects the limit param."""
    import app.services.journal_context as journal_context_module

    captured = {}

    class _RecordingStore:
        def list_for_user(self, user_id, *, plan, ticker, limit):
            captured["limit"] = limit
            return [], 0, None

    monkeypatch.setattr(journal_context_module, "get_journal_store", lambda: _RecordingStore())
    fetch_recent_journal_entries(uuid4(), "AAPL")
    assert captured["limit"] == 5
