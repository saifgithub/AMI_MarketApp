"""CR095 auditor pin (round 1, FIXED in round 2) — a timezone change after
being reminded used to make "today" look fresh and trigger a second reminder
the same real day.

**Now asserts the fixed behaviour**: the second tick sends nothing and exactly
one notification row exists. The fix is a trailing
`_MIN_HOURS_BETWEEN_REMINDERS` (20h) window on `created_at`, OR'd with the
`source_ref` match in `_already_reminded_today` — `source_ref` moves when
`users.timezone` moves, `created_at` does not.

The companion test below is the one that keeps the fix honest: a 20h window
that also suppressed the *next day's* legitimate reminder would satisfy this
test and quietly break the feature.

Original defect description follows, kept because it is why this pin exists:

`_already_reminded_today()` keys the dedupe row on `local_date`, computed
fresh from `now.astimezone(user.timezone)` on every call. Idempotency is
NOT keyed on any fixed identifier of "today" independent of the user's
current timezone — so a user who is reminded once, then changes timezone
to one with a large enough forward offset, can have the tick compute a
DIFFERENT `local_date` on the very next check even though very little real
time has passed. No notification row exists yet for that "new" local date,
so `_already_reminded_today` returns False and the user is reminded again
— two reminders within the same real UTC day, for the same daily
challenge, from a single legitimate settings change.

This directly contradicts CR095's acceptance ("at most once per day") and
`daily_reminder.py` / `main.py::_daily_reminder_tick`'s own claim that
idempotency "makes the day boundary the user's own, not UTC's" with no
caveat about a tz change invalidating a same-day dedupe.
"""

from __future__ import annotations

import json
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

_CHALLENGE_ID = "dc_2026_06_01_tzchange_fixture"
_CHALLENGE_ID_DAY2 = "dc_2026_06_02_tzchange_fixture"
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
    {
        # Day-2 challenge so the second (tz-shifted) local_date also has a
        # real challenge to engage with -- otherwise `no_challenge_today`
        # would mask the double-send this pin exists to prove.
        "id": _CHALLENGE_ID_DAY2,
        "type": "predict_the_call",
        "difficulty": 2,
        "locale": "en",
        "scenario": "MSFT margin surprise.",
        "question": "Beat or miss?",
        "options": ["Beat", "Miss", "In-line"],
        "answer": 0,
        "explanation": "Guidance raise.",
        "related_lesson": "039",
        "related_agent": "fundamentals_analyst",
        "tags": ["valuation"],
    },
]


def test_changing_timezone_after_being_reminded_does_not_trigger_a_second_reminder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    svc = DailyChallengeService(content_dir=d)
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")

    calls: list[str] = []
    monkeypatch.setattr(dr, "send_daily_reminder", lambda to, teaser: calls.append(to) or True)

    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.FLOOR_PASS.value, timezone="UTC",
            daily_reminder_hour=10, email="tzchange@example.com", is_anonymous=False,
        ))

    # Tick 1: 2026-06-01 10:05 UTC, tz=UTC, hour=10 reached -> reminded.
    # source_ref written = "2026-06-01".
    stats1 = dr.send_due_reminders(now=datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc))
    assert stats1["sent_email"] == 1
    assert len(calls) == 1

    # User changes timezone in Settings shortly after (e.g. PUT /reminder),
    # to a zone whose forward offset is large enough that the SAME wall-clock
    # instant (or a later one, still within the same real UTC calendar day)
    # falls on the NEXT local calendar date.
    with get_session() as s:
        row = s.get(User, user_id)
        row.timezone = "Pacific/Kiritimati"  # UTC+14

    # Tick 2: 2026-06-01 20:05 UTC — still the SAME UTC calendar day as tick
    # 1, only 10 real hours later. Under the new tz this is 2026-06-02 10:05
    # local: a NEW local_date, hour (10) reached again, and no notification
    # row exists yet for "2026-06-02" -- so the user is reminded a second
    # time for the same underlying day.
    stats2 = dr.send_due_reminders(now=datetime(2026, 6, 1, 20, 5, tzinfo=timezone.utc))

    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == "daily_reminder",
            )
        ).scalars().all()

    assert stats2["sent_email"] == 0, (
        "a bare timezone change produced a second reminder ~10 real hours "
        f"after the first; stats2={stats2}"
    )
    assert stats2["already_reminded"] == 1, stats2
    assert len(calls) == 1, calls
    assert len(rows) == 1, [r.source_ref for r in rows]


def test_the_next_days_reminder_still_fires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The non-vacuity leg. The fix above suppresses a send within a trailing
    20h window, so it MUST NOT suppress the genuine next-day reminder 24h
    later. A fix that simply stopped sending would pass the test above."""
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    svc = DailyChallengeService(content_dir=d)
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")

    calls: list[str] = []
    monkeypatch.setattr(dr, "send_daily_reminder", lambda to, teaser: calls.append(to) or True)

    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.FLOOR_PASS.value, timezone="UTC",
            daily_reminder_hour=10, email="nextday@example.com", is_anonymous=False,
        ))

    stats1 = dr.send_due_reminders(now=datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc))
    assert stats1["sent_email"] == 1

    # 24h later, same hour, no timezone change — an ordinary consecutive day.
    stats2 = dr.send_due_reminders(now=datetime(2026, 6, 2, 10, 5, tzinfo=timezone.utc))
    assert stats2["sent_email"] == 1, (
        "the 20h dedupe window swallowed the next day's legitimate reminder; "
        f"stats2={stats2}"
    )
    assert len(calls) == 2, calls
