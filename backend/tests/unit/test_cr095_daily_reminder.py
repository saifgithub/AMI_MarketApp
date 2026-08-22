"""CR095 — daily-challenge reminder (push paid-tier / email free-tier).

`app.services.daily_reminder.send_due_reminders` is the whole feature under
test here. No network: OneSignal push goes through the REAL
`notification_service.notify()` (so its row-write — the durable idempotency
marker every assertion below relies on — behaves exactly as it does in
production) with `httpx.post` monkeypatched at the transport boundary, same
style as CR027's own `test_notification_service.py`; the outbound email
transport (`email_service.send_daily_reminder`) is monkeypatched directly,
since `daily_reminder.py` imports it by name.

Uses a temp-directory `DailyChallengeService` fixture (same pattern as
`test_daily_challenge_attempt.py`) rather than the real `content/` corpus —
deterministic and independent of whatever challenges ship later.
"""

from __future__ import annotations

import importlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import DailyChallengeAttemptRow, NotificationRow, User
from app.schemas.mandate import Plan
from app.services import daily_reminder as dr
from app.services import notification_service
from app.services.daily_challenge_service import DailyChallengeService

_CHALLENGE_ID = "dc_2026_06_01_fixture"

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

_TARGET_DATE = date(2026, 6, 1)
# 2026-06-01 09:15 America/New_York (EDT, UTC-4 in June) == 13:15 UTC.
_NOW_NY_9AM = datetime(2026, 6, 1, 13, 15, tzinfo=timezone.utc)


@pytest.fixture
def _challenge_svc(tmp_path: Path) -> DailyChallengeService:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    return DailyChallengeService(content_dir=d)


@pytest.fixture(autouse=True)
def _wire_challenge_service(
    _challenge_svc: DailyChallengeService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: _challenge_svc)


def _make_user(
    *,
    plan: Plan = Plan.FLOOR_PASS,
    tz: str = "UTC",
    hour: int | None = 9,
    email: str | None = None,
) -> User:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=plan.value, timezone=tz,
            daily_reminder_hour=hour, email=email,
            is_anonymous=email is None,
        ))
    with get_session() as s:
        return s.execute(select(User).where(User.id == user_id)).scalar_one()


def _notifications_for(user_id) -> list[NotificationRow]:
    with get_session() as s:
        return s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == "daily_reminder",
            )
        ).scalars().all()


class _FakeEmail:
    def __init__(self, attempted: bool = True):
        self.attempted = attempted
        self.calls: list[tuple[str, str]] = []

    def __call__(self, to: str, teaser: str) -> bool:
        self.calls.append((to, teaser))
        return self.attempted


def _no_push_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real `notify()`'s natural `not_configured` path — the alpha default
    (onesignal_app_id/rest_key both empty). No monkeypatch needed beyond
    asserting the settings are in that state, but stated explicitly so a
    future change to the Settings default doesn't silently invalidate it."""
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")


def _push_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    monkeypatch.setattr(
        notification_service.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=200, text="", json=lambda: {"id": "onesignal-id", "recipients": 1}),
    )


def _push_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")

    def _boom(*a, **k):
        raise notification_service.httpx.RequestError("boom")

    monkeypatch.setattr(notification_service.httpx, "post", _boom)


# ── local-hour reach ─────────────────────────────────────────────────────


def test_user_at_local_hour_gets_one_reminder_hour_earlier_user_gets_none(
    monkeypatch: pytest.MonkeyPatch,
):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    due = _make_user(tz="America/New_York", hour=9, email="due@example.com")
    not_due = _make_user(tz="America/New_York", hour=10, email="notdue@example.com")

    stats = dr.send_due_reminders(now=_NOW_NY_9AM)

    assert stats["sent_email"] == 1
    assert stats["hour_not_reached"] == 1
    assert [c[0] for c in fake_email.calls] == ["due@example.com"]
    assert len(_notifications_for(due.id)) == 1
    assert _notifications_for(not_due.id) == []


# ── idempotency, including a simulated restart ──────────────────────────


def test_already_reminded_today_never_sends_twice_across_a_restart(
    _challenge_svc: DailyChallengeService, monkeypatch: pytest.MonkeyPatch,
):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    user = _make_user(tz="UTC", hour=9, email="once@example.com")

    stats1 = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))
    assert stats1["sent_email"] == 1
    assert len(fake_email.calls) == 1

    # Simulate a container restart: rebuild the module object fresh — the
    # dedupe read is a real DB query, not Python-process state, so a reload
    # (a new module object, no shared globals with the one above) must still
    # see "already reminded" and refuse to send again.
    dr2 = importlib.reload(dr)
    monkeypatch.setattr(dr2, "get_daily_challenge_service", lambda: _challenge_svc)
    monkeypatch.setattr(dr2, "send_daily_reminder", fake_email)

    stats2 = dr2.send_due_reminders(now=datetime(2026, 6, 1, 9, 45, tzinfo=timezone.utc))
    assert stats2["already_reminded"] == 1
    assert stats2["sent_email"] == 0
    assert len(fake_email.calls) == 1, "reload + a later same-day tick must not re-send"

    # dr and dr2 are the same module object post-reload (reload mutates
    # in-place) — re-wire the fixtures' patches so later tests in this file
    # aren't left pointed at a stale service/email fake.
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: _challenge_svc)
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)


# ── already engaged ───────────────────────────────────────────────────────


def test_already_engaged_today_is_skipped(monkeypatch: pytest.MonkeyPatch):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    user = _make_user(tz="UTC", hour=9, email="engaged@example.com")
    with get_session() as s:
        s.add(DailyChallengeAttemptRow(
            user_id=user.id, challenge_id=_CHALLENGE_ID,
            selected_option=1, correct=True,
        ))

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["already_engaged"] == 1
    assert stats["sent_email"] == 0
    assert fake_email.calls == []
    assert _notifications_for(user.id) == []


# ── channel by effective plan ───────────────────────────────────────────


def test_paid_user_push_works_sends_push_no_email(monkeypatch: pytest.MonkeyPatch):
    _push_succeeds(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    user = _make_user(plan=Plan.TRADER, tz="UTC", hour=9, email="paid@example.com")

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["sent_push"] == 1
    assert stats["sent_email"] == 0
    assert stats["fallback_email"] == 0
    assert fake_email.calls == []
    rows = _notifications_for(user.id)
    assert len(rows) == 1


def test_paid_user_push_fails_falls_back_to_email_and_is_counted(
    monkeypatch: pytest.MonkeyPatch,
):
    _push_fails(monkeypatch)
    fake_email = _FakeEmail(attempted=True)
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        dr.logger, "warning", lambda event, **kw: warnings.append((event, kw)),
    )

    user = _make_user(plan=Plan.TRADER, tz="UTC", hour=9, email="fallback@example.com")

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["sent_push"] == 0
    assert stats["fallback_email"] == 1
    assert stats["unreachable"] == 0
    assert fake_email.calls == [("fallback@example.com", "Cheap or expensive?")]
    assert any(e == "daily_reminder_push_failed_email_fallback" for e, _ in warnings)
    # notify()'s row is still written even though push failed — CR027 invariant.
    assert len(_notifications_for(user.id)) == 1


# ── unreachable on every channel ────────────────────────────────────────


def test_unreachable_user_is_counted_and_logged_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch,
):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)
    errors: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        dr.logger, "error", lambda event, **kw: errors.append((event, kw)),
    )

    user = _make_user(plan=Plan.FLOOR_PASS, tz="UTC", hour=9, email=None)

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["unreachable"] == 1
    assert fake_email.calls == []
    assert any(e == "daily_reminder_unreachable" for e, _ in errors)
    # Still durably marked reminded-today so a later tick this day doesn't
    # re-log the same unreachable user every interval.
    assert len(_notifications_for(user.id)) == 1


def test_free_user_email_on_file_but_transport_unconfigured_counts_unreachable(
    monkeypatch: pytest.MonkeyPatch,
):
    """A user having an email on file is not the same as the backend's email
    transport being configured — conflating the two would report `sent_email`
    for a reminder that never actually left the process."""
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail(attempted=False)  # mirrors send_daily_reminder()
    # when neither RESEND_API_KEY nor SMTP_HOST is set.
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    user = _make_user(plan=Plan.FLOOR_PASS, tz="UTC", hour=9, email="has@example.com")

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["unreachable"] == 1
    assert stats["sent_email"] == 0
    assert fake_email.calls == [("has@example.com", "Cheap or expensive?")]


# ── invalid timezone ─────────────────────────────────────────────────────


def test_invalid_timezone_falls_back_to_utc_loudly_other_users_still_processed(
    monkeypatch: pytest.MonkeyPatch,
):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        dr.logger, "warning", lambda event, **kw: warnings.append((event, kw)),
    )

    garbage = _make_user(tz="Not/A_Real_Zone", hour=9, email="garbage@example.com")
    normal = _make_user(tz="UTC", hour=9, email="normal@example.com")

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc))

    assert stats["invalid_timezone"] == 1
    assert stats["sent_email"] == 2, "both users, including the garbage-tz one, get processed"
    assert {c[0] for c in fake_email.calls} == {"garbage@example.com", "normal@example.com"}
    invalid_tz_logs = [kw for e, kw in warnings if e == "daily_reminder_invalid_timezone"]
    assert len(invalid_tz_logs) == 1
    assert invalid_tz_logs[0]["chosen"] == "UTC"
    assert invalid_tz_logs[0]["user_id"] == str(garbage.id)


# ── NULL reminder hour ────────────────────────────────────────────────────


def test_null_reminder_hour_is_never_reminded(monkeypatch: pytest.MonkeyPatch):
    _no_push_configured(monkeypatch)
    fake_email = _FakeEmail()
    monkeypatch.setattr(dr, "send_daily_reminder", fake_email)

    user = _make_user(tz="UTC", hour=None, email="off@example.com")

    stats = dr.send_due_reminders(now=datetime(2026, 6, 1, 23, 59, tzinfo=timezone.utc))

    assert stats["eligible"] == 0
    assert fake_email.calls == []
    assert _notifications_for(user.id) == []
