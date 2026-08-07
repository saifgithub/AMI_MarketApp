"""CR095 auditor pin (round 1, FIXED in round 2) — concurrent ticks used to
double-send.

**Now asserts the fixed behaviour**: exactly one email, exactly one row, zero
errors, with the TOCTOU window still forced wide open. The fix is the
`uq_notifications_dedupe` unique constraint on
`notifications(user_id, type, source_ref)`, plus `notify()` degrading the
resulting IntegrityError to `push_status="duplicate"` so the losing racer sees
a normal skip rather than an unhandled 500, plus reordering the free-tier path
to write the claiming row BEFORE sending the email — a claim made after
delivery guards nothing.

Note what this test does NOT do: it does not narrow the race. The 0.4s sleep
inside the real check is still there, so both ticks still observe "not yet
reminded". The guarantee is now the DB's, which is the point — it holds
regardless of how the two callers interleave.

Original defect description follows, kept because it is why this pin exists:

`daily_reminder.py`'s own docstring and `main.py::_daily_reminder_tick`'s
docstring both claim idempotency is "entirely DB-derived" and that the
15-minute interval carries "no risk of a double-send". That claim rests
solely on a read-then-write pattern (`_already_reminded_today()` SELECT,
then `notify()` INSERT) with **no unique constraint** on
`notifications(user_id, type, source_ref)` and no row-level locking. Two
overlapping calls to `send_due_reminders()` (a slow tick still running when
the next 15-minute tick fires, or two processes/threads calling it at once)
can both observe "not yet reminded" before either writes, and both send.

This test widens the real TOCTOU window deterministically (a small sleep
inside the *real* `_already_reminded_today`, not a fake) rather than relying
on a timing-sensitive race, then fires two real overlapping calls to
`send_due_reminders()` for one eligible user and shows both send.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import NotificationRow, User
from app.schemas.mandate import Plan
from app.services import daily_reminder as dr
from app.services.daily_challenge_service import DailyChallengeService

_CHALLENGE_ID = "dc_2026_06_01_race_fixture"
_FIXTURE = [
    {
        "id": _CHALLENGE_ID,
        "type": "predict_the_call",
        "difficulty": 2,
        "locale": "en",
        "scenario": "AAPL P/E elevated.",
        "question": "Cheap or expensive?",
        "options": ["Cheap", "Expensive", "Fair"],
        "answer": 1,
        "explanation": "Premium multiple.",
        "related_lesson": "039",
        "related_agent": "fundamentals_analyst",
        "tags": ["valuation"],
    },
]
_NOW = datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc)


def test_two_overlapping_ticks_both_send_no_db_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    svc = DailyChallengeService(content_dir=d)
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)

    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")

    calls: list[tuple[str, str]] = []
    calls_lock = threading.Lock()

    def _fake_email(to: str, teaser: str) -> bool:
        with calls_lock:
            calls.append((to, teaser))
        return True

    monkeypatch.setattr(dr, "send_daily_reminder", _fake_email)

    # Widen the real TOCTOU window: the genuine SELECT still runs and still
    # returns the genuine answer, we just delay the return so two racing
    # callers both observe "not yet reminded" before either writes.
    _real_check = dr._already_reminded_today

    def _slow_check(user_id, local_date, now):
        seen = _real_check(user_id, local_date, now)
        time.sleep(0.4)
        return seen

    monkeypatch.setattr(dr, "_already_reminded_today", _slow_check)

    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.FLOOR_PASS.value, timezone="UTC",
            daily_reminder_hour=9, email="race@example.com", is_anonymous=False,
        ))

    barrier = threading.Barrier(2)
    outcomes: list[dict[str, int]] = []
    outcomes_lock = threading.Lock()

    def _run_tick() -> None:
        barrier.wait()
        stats = dr.send_due_reminders(now=_NOW)
        with outcomes_lock:
            outcomes.append(stats)

    t1 = threading.Thread(target=_run_tick)
    t2 = threading.Thread(target=_run_tick)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(outcomes) == 2, "both overlapping ticks must complete"
    total_sent = sum(o["sent_email"] for o in outcomes)
    total_errors = sum(o["errors"] for o in outcomes)

    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == "daily_reminder",
            )
        ).scalars().all()

    # The claim under test — "no risk of a double-send" — now holds, and holds
    # because of the DB rather than because of how the two ticks happened to
    # interleave. The losing racer must ALSO not error: a 500 from an
    # unhandled IntegrityError would be a different failure wearing the same
    # green tick.
    assert total_errors == 0, f"unexpected errors in either tick: {outcomes}"
    assert len(calls) == 1, f"the race double-sent: {calls}"
    assert total_sent == 1, f"exactly one tick must report sent_email=1, got {outcomes}"
    assert len(rows) == 1, (
        "two notifications rows for the same user/day — uq_notifications_dedupe "
        "is not holding"
    )
    # The loser reported the skip honestly rather than silently doing nothing.
    assert sum(o["already_reminded"] for o in outcomes) == 1, outcomes
