"""CR109 slice 3 — the career-points ledger (`career_ledger.py`).

Covers implementation_plan.md §9 test matrix items 14, 29 and this brief's
own test 3 ("a player at 0 who scores +8 displays 8 — assert against the
ledger") and test 11 (a `career_events` row is never written with a null
`field_id`/`entry_id`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.db.models import CareerEventRow, GameEntryRow, GameFieldRow
from app.services import career_ledger


def _make_field(session, *, starts_on=None) -> GameFieldRow:
    from datetime import date

    starts_on = starts_on or date(2026, 8, 10)
    field = GameFieldRow(
        cadence="week",
        state="closed",
        entry_opens_at=datetime(2026, 8, 3, 13, 0, tzinfo=timezone.utc),
        locks_at=datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc),
        starts_on=starts_on,
        ends_on=starts_on,
        entrant_count=1,
        kind="open",
        points_policy="full",
        scoring_basis="benchmark",
    )
    session.add(field)
    session.flush()
    return field


def _make_entry(session, field: GameFieldRow, user_id) -> GameEntryRow:
    entry = GameEntryRow(
        field_id=field.id, user_id=user_id, run_id=uuid4(),
        state="finished", fees_paid=0, trade_count=1,
    )
    session.add(entry)
    session.flush()
    return entry


def test_post_career_event_requires_field_id_and_entry_id():
    user_id = uuid4()
    with get_session() as s:
        field = _make_field(s)
        entry = _make_entry(s, field, user_id)
        with pytest.raises(ValueError):
            career_ledger.post_career_event(
                s, user_id=user_id, delta_uncapped=10, reason="run_close",
                field_id=None, entry_id=entry.id,
            )
        with pytest.raises(ValueError):
            career_ledger.post_career_event(
                s, user_id=user_id, delta_uncapped=10, reason="run_close",
                field_id=field.id, entry_id=None,
            )
    with get_session() as s:
        assert career_ledger.career_points_total(s, user_id) == 0


def test_career_events_row_can_never_carry_a_null_field_id_or_entry_id_at_the_db():
    """Belt-and-braces behind the ValueError above — the column-level NOT
    NULL is what survives even a caller that bypasses `post_career_event`
    entirely and inserts the row directly."""
    user_id = uuid4()
    with get_session() as s:
        field = _make_field(s)
        entry = _make_entry(s, field, user_id)
        s.add(CareerEventRow(
            user_id=user_id, delta=5, delta_uncapped=5, reason="run_close",
            field_id=None, entry_id=entry.id,
        ))
        with pytest.raises(IntegrityError):
            s.flush()
        # A failed flush leaves the session's transaction aborted — roll
        # back so `get_session()`'s own exit-time `commit()` doesn't raise
        # a SECOND (unrelated) error over this test's own assertion.
        s.rollback()


def test_clamp_happens_at_write_a_player_at_zero_who_scores_8_displays_8():
    """This is the brief's own test 3 — assert against the LEDGER."""
    from datetime import date, timedelta

    user_id = uuid4()
    with get_session() as s:
        # UniqueConstraint(field_id, user_id) means one entry per field —
        # three DIFFERENT fields (different weeks), same user.
        field = _make_field(s, starts_on=date(2026, 8, 10))
        field2 = _make_field(s, starts_on=date(2026, 8, 17))
        field3 = _make_field(s, starts_on=date(2026, 8, 24))
        entry1 = _make_entry(s, field, user_id)
        entry2 = _make_entry(s, field2, user_id)
        entry3 = _make_entry(s, field3, user_id)

        # Start at 0. A debit larger than the (zero) balance clamps to 0,
        # never negative-on-write... except the design allows a SIGNED
        # negative total via delta_uncapped tracking the raw value — the
        # INVARIANT under test is narrower: SUM(delta) never goes below
        # zero, and the raw value survives in delta_uncapped.
        row1 = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=-30, reason="run_close",
            field_id=field.id, entry_id=entry1.id,
        )
        assert row1.delta == 0
        assert row1.delta_uncapped == -30
        assert career_ledger.career_points_total(s, user_id) == 0

        # Now score +8 — the ledger already sits at the floor, so +8 must
        # land as a plain +8, not a partially-absorbed climb out of a debt
        # the display never showed.
        row2 = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=8, reason="run_close",
            field_id=field2.id, entry_id=entry2.id,
        )
        assert row2.delta == 8
        assert row2.delta_uncapped == 8
        assert career_ledger.career_points_total(s, user_id) == 8

        # A further debit larger than the current total (8) clamps to
        # exactly -8, landing back at zero, never below.
        row3 = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=-100, reason="run_close",
            field_id=field3.id, entry_id=entry3.id,
        )
        assert row3.delta == -8
        assert row3.delta_uncapped == -100
        assert career_ledger.career_points_total(s, user_id) == 0


def test_dedup_same_entry_and_reason_is_a_noop_not_a_double_post():
    user_id = uuid4()
    with get_session() as s:
        field = _make_field(s)
        entry = _make_entry(s, field, user_id)
        first = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=20, reason="run_close",
            field_id=field.id, entry_id=entry.id,
        )
        second = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=20, reason="run_close",
            field_id=field.id, entry_id=entry.id,
        )
        assert first.id == second.id
        assert career_ledger.career_points_total(s, user_id) == 20


def test_stipend_pays_once_per_cadence_period_across_different_entries():
    """The fourth stipend guard (design §6.5) — a SECOND finished run in
    the SAME cadence period must not claim a second stipend, even from a
    completely different entry/field."""
    user_id = uuid4()
    with get_session() as s:
        field1 = _make_field(s)
        field2 = _make_field(s)  # a different field, SAME starts_on -> same period
        entry1 = _make_entry(s, field1, user_id)
        entry2 = _make_entry(s, field2, user_id)
        period_key = "week:2026-W33"

        first = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=5, reason="finish_stipend",
            field_id=field1.id, entry_id=entry1.id, period_key=period_key,
        )
        second = career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=5, reason="finish_stipend",
            field_id=field2.id, entry_id=entry2.id, period_key=period_key,
        )
        assert first is not None
        assert second is None
        assert career_ledger.career_points_total(s, user_id) == 5


def test_forfeit_count():
    user_id = uuid4()
    with get_session() as s:
        field = _make_field(s)
        entry = _make_entry(s, field, user_id)
        entry.state = "forfeit"
        s.flush()
        assert career_ledger.forfeit_count(s, user_id) == 1
