"""CR095 round-2 auditor pin — an independent adversarial pass on the three
round-1 fixes, written by the auditor rather than the architect. Every test
here targets a scenario the round-2 submission raised as its OWN suspicion
(the `{}`/unrelated-keys partial-update shape, DST around the 20h window,
the paid-path early-return) or a caller the submission did not examine at
all (`price_alert_evaluator.py`'s non-null `source_ref`).

All pass against `82fd43fd` as shipped — none of these are new fixes, they
are new coverage confirming the round-2 fixes hold under attack.
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.daily_challenge import router as daily_challenge_router
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import get_session
from app.db.models import NotificationRow, User
from app.schemas.mandate import Plan
from app.services import daily_reminder as dr
from app.services.daily_challenge_service import DailyChallengeService
from app.services.notification_service import notify

_CHALLENGE_ID = "dc_2026_06_01_r2audit_fixture"
_CHALLENGE_ID_DAY2 = "dc_2026_06_02_r2audit_fixture"
_FIXTURE = [
    {
        "id": _CHALLENGE_ID, "type": "predict_the_call", "difficulty": 2,
        "locale": "en", "scenario": "AAPL P/E elevated.",
        "question": "Cheap or expensive?", "options": ["Cheap", "Expensive", "Fair"],
        "answer": 1, "explanation": "Premium multiple.",
        "related_lesson": "039", "related_agent": "fundamentals_analyst",
        "tags": ["valuation"],
    },
    {
        "id": _CHALLENGE_ID_DAY2, "type": "predict_the_call", "difficulty": 2,
        "locale": "en", "scenario": "MSFT margin surprise.",
        "question": "Beat or miss?", "options": ["Beat", "Miss", "In-line"],
        "answer": 0, "explanation": "Guidance raise.",
        "related_lesson": "039", "related_agent": "fundamentals_analyst",
        "tags": ["valuation"],
    },
]


def _svc(tmp_path: Path) -> DailyChallengeService:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    return DailyChallengeService(content_dir=d)


def _svc_for_dates(tmp_path: Path, day1: date, day2: date) -> DailyChallengeService:
    """`for_date` matches on the challenge id's own date prefix (`dc_YYYY_MM_DD_*`),
    so a fixture used across two different real calendar dates needs ids
    generated for those exact dates."""
    d = tmp_path / "daily_challenges"
    d.mkdir()
    fixture = [
        {
            "id": f"dc_{day1.year:04d}_{day1.month:02d}_{day1.day:02d}_r2audit",
            "type": "predict_the_call", "difficulty": 2, "locale": "en",
            "scenario": "AAPL P/E elevated.", "question": "Cheap or expensive?",
            "options": ["Cheap", "Expensive", "Fair"], "answer": 1,
            "explanation": "Premium multiple.", "related_lesson": "039",
            "related_agent": "fundamentals_analyst", "tags": ["valuation"],
        },
        {
            "id": f"dc_{day2.year:04d}_{day2.month:02d}_{day2.day:02d}_r2audit",
            "type": "predict_the_call", "difficulty": 2, "locale": "en",
            "scenario": "MSFT margin surprise.", "question": "Beat or miss?",
            "options": ["Beat", "Miss", "In-line"], "answer": 0,
            "explanation": "Guidance raise.", "related_lesson": "039",
            "related_agent": "fundamentals_analyst", "tags": ["valuation"],
        },
    ]
    (d / f"{day1.year:04d}_{day1.month:02d}.json").write_text(
        json.dumps(fixture), encoding="utf-8",
    )
    return DailyChallengeService(content_dir=d)


# ---------------------------------------------------------------------------
# 1. Partial update — `{}` and unrelated-keys-only bodies.
#
# The shipped pin only exercises "omit the hour key, send timezone" and "send
# an explicit null". Neither is exactly `{}` or a body whose only key Pydantic
# silently drops (extra="ignore" is the BaseModel default here — no
# model_config override) — both routes to `model_fields_set` ending up empty
# in a way the existing pins don't hit.
# ---------------------------------------------------------------------------


@pytest.fixture()
def user() -> User:
    with get_session() as s:
        row = User(
            id=uuid4(), handle=f"r2_{uuid4().hex[:8]}", locale="en", timezone="UTC",
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        s.expunge(row)
    return row


@pytest.fixture()
def client(user: User) -> TestClient:
    app = FastAPI()
    app.include_router(daily_challenge_router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_empty_body_leaves_both_fields_unchanged(client: TestClient, user: User) -> None:
    client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"},
    )
    r = client.put("/v1/daily_challenge/reminder", json={})
    assert r.status_code == 200
    with get_session() as s:
        stored = s.get(User, user.id)
        assert stored.daily_reminder_hour == 8, "an empty {} body cleared the hour"
        assert stored.timezone == "Asia/Riyadh", "an empty {} body cleared the timezone"


def test_body_with_only_unrelated_keys_leaves_both_fields_unchanged(
    client: TestClient, user: User,
) -> None:
    client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"},
    )
    # Pydantic's default extra="ignore" drops this key entirely — it must
    # NOT be treated as "the caller sent a body, so wipe the fields they
    # didn't mention".
    r = client.put(
        "/v1/daily_challenge/reminder", json={"device_id": "abc123", "foo": "bar"},
    )
    assert r.status_code == 200
    with get_session() as s:
        stored = s.get(User, user.id)
        assert stored.daily_reminder_hour == 8
        assert stored.timezone == "Asia/Riyadh"


# ---------------------------------------------------------------------------
# 2. The 20h window vs. real DST transitions on a FIXED IANA zone (no
# explicit timezone change by the user — the scenario the fix targets is a
# user CHANGING timezone; this is the ordinary case of staying in one zone
# that observes DST). The architect flagged this as the gap they suspect
# most. US Eastern in 2027: spring-forward (23h local day) 2027-03-14,
# fall-back (25h local day) 2027-11-07 — both confirmed via zoneinfo before
# writing this test.
# ---------------------------------------------------------------------------


def test_next_days_reminder_survives_spring_forward_dst(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _svc_for_dates(tmp_path, date(2027, 3, 13), date(2027, 3, 14))
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")
    calls: list[str] = []
    monkeypatch.setattr(dr, "send_daily_reminder", lambda to, teaser: calls.append(to) or True)

    tz = ZoneInfo("America/New_York")
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.FLOOR_PASS.value, timezone="America/New_York",
            daily_reminder_hour=10, email="springfwd@example.com", is_anonymous=False,
        ))

    day1_local = datetime(2027, 3, 13, 10, 5, tzinfo=tz)
    day2_local = datetime(2027, 3, 14, 10, 5, tzinfo=tz)  # DST day; 3am->2am skip
    real_gap = (day2_local.astimezone(timezone.utc) - day1_local.astimezone(timezone.utc))
    assert real_gap == timedelta(hours=23), f"fixture assumption broke: gap={real_gap}"

    stats1 = dr.send_due_reminders(now=day1_local.astimezone(timezone.utc))
    assert stats1["sent_email"] == 1

    stats2 = dr.send_due_reminders(now=day2_local.astimezone(timezone.utc))
    assert stats2["sent_email"] == 1, (
        f"spring-forward's 23h local day was swallowed by the 20h window: {stats2}"
    )
    assert len(calls) == 2


def test_next_days_reminder_survives_fall_back_dst(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _svc_for_dates(tmp_path, date(2027, 11, 6), date(2027, 11, 7))
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")
    calls: list[str] = []
    monkeypatch.setattr(dr, "send_daily_reminder", lambda to, teaser: calls.append(to) or True)

    tz = ZoneInfo("America/New_York")
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.FLOOR_PASS.value, timezone="America/New_York",
            daily_reminder_hour=10, email="fallback@example.com", is_anonymous=False,
        ))

    day1_local = datetime(2027, 11, 6, 10, 5, tzinfo=tz)
    day2_local = datetime(2027, 11, 7, 10, 5, tzinfo=tz)  # DST day; 2am repeats
    real_gap = (day2_local.astimezone(timezone.utc) - day1_local.astimezone(timezone.utc))
    assert real_gap == timedelta(hours=25), f"fixture assumption broke: gap={real_gap}"

    stats1 = dr.send_due_reminders(now=day1_local.astimezone(timezone.utc))
    assert stats1["sent_email"] == 1

    stats2 = dr.send_due_reminders(now=day2_local.astimezone(timezone.utc))
    assert stats2["sent_email"] == 1, f"fall-back's 25h local day was swallowed: {stats2}"
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# 3. Exact boundary of the 20h window, exercised directly against
# `_already_reminded_today` so the math is pinned independent of any
# timezone/DST scenario. Window is `created_at >= now - 20h` (inclusive).
# ---------------------------------------------------------------------------


def test_20h_window_boundary_is_inclusive_at_exactly_20h() -> None:
    user_id = uuid4()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)
    stamped_at = now - timedelta(hours=20)  # exactly on the cutoff
    with get_session() as s:
        s.add(NotificationRow(
            id=uuid4(), user_id=user_id, type="daily_reminder", title="t", body="b",
            deep_link={}, source_ref="2026-06-01", created_at=stamped_at,
        ))
    # Different local_date so only the trailing-window leg can suppress.
    blocked = dr._already_reminded_today(user_id, date(2026, 6, 2), now)
    assert blocked is True, "exactly-20h-old row must still suppress (inclusive boundary)"


def test_20h_window_boundary_releases_just_after_20h() -> None:
    user_id = uuid4()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)
    stamped_at = now - timedelta(hours=20, seconds=1)  # 1s past the cutoff
    with get_session() as s:
        s.add(NotificationRow(
            id=uuid4(), user_id=user_id, type="daily_reminder", title="t", body="b",
            deep_link={}, source_ref="2026-06-01", created_at=stamped_at,
        ))
    blocked = dr._already_reminded_today(user_id, date(2026, 6, 2), now)
    assert blocked is False, "a row 20h+1s old must no longer suppress a new local_date"


# ---------------------------------------------------------------------------
# 4. Paid-tier concurrency: two overlapping ticks racing on a PAID user with
# push unconfigured (push_status is therefore "not_configured" on the
# winner too — never "sent" — forcing every result through the "did push
# fail -> try email fallback" branch). Without the `was_duplicate`
# early-return on the paid path, the loser would read its own IntegrityError
# suppression as "push didn't deliver" and send a second fallback email.
# The shipped concurrency pin only exercises the free-tier path.
# ---------------------------------------------------------------------------


def test_paid_tier_duplicate_does_not_fall_through_to_email(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _svc(tmp_path)
    monkeypatch.setattr(dr, "get_daily_challenge_service", lambda: svc)
    monkeypatch.setattr(settings, "onesignal_app_id", "")
    monkeypatch.setattr(settings, "onesignal_rest_key", "")

    calls: list[str] = []
    calls_lock = threading.Lock()

    def _fake_email(to: str, teaser: str) -> bool:
        with calls_lock:
            calls.append(to)
        return True

    monkeypatch.setattr(dr, "send_daily_reminder", _fake_email)

    _real_check = dr._already_reminded_today
    import time as _time

    def _slow_check(user_id, local_date, now):
        seen = _real_check(user_id, local_date, now)
        _time.sleep(0.4)
        return seen

    monkeypatch.setattr(dr, "_already_reminded_today", _slow_check)

    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan=Plan.TRADER.value, timezone="UTC",
            daily_reminder_hour=9, email="paidrace@example.com", is_anonymous=False,
        ))

    now = datetime(2026, 6, 1, 9, 5, tzinfo=timezone.utc)
    barrier = threading.Barrier(2)
    outcomes: list[dict[str, int]] = []
    outcomes_lock = threading.Lock()

    def _run_tick() -> None:
        barrier.wait()
        stats = dr.send_due_reminders(now=now)
        with outcomes_lock:
            outcomes.append(stats)

    t1 = threading.Thread(target=_run_tick)
    t2 = threading.Thread(target=_run_tick)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(outcomes) == 2

    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == "daily_reminder",
            )
        ).scalars().all()

    total_errors = sum(o["errors"] for o in outcomes)
    total_fallback = sum(o["fallback_email"] for o in outcomes)
    assert total_errors == 0, outcomes
    assert len(calls) == 1, (
        f"paid-tier race sent {len(calls)} fallback emails for one user — the "
        "was_duplicate early-return on the paid path did not hold"
    )
    assert total_fallback == 1, outcomes
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 5. `uq_notifications_dedupe` vs. a DIFFERENT real caller: price_alert_
# evaluator.py calls notify() with a non-null source_ref (`str(alert.id)`),
# so it IS in scope of the new constraint (unlike the majority of callers
# that pass no source_ref at all). Confirms two DIFFERENT alerts for the
# same user don't collide, and that the constraint's `existing_id` recovery
# path degrades cleanly if the exact same source_ref were ever reused.
# ---------------------------------------------------------------------------


def test_price_alert_style_calls_with_distinct_source_refs_do_not_collide() -> None:
    user_id = uuid4()
    alert_id_1 = uuid4()
    alert_id_2 = uuid4()
    r1 = notify(
        user_id, "price_alert", "Price Alert: AAPL", "body1",
        {"route": "open_holding_detail", "ticker": "AAPL"}, str(alert_id_1),
    )
    r2 = notify(
        user_id, "price_alert", "Price Alert: MSFT", "body2",
        {"route": "open_holding_detail", "ticker": "MSFT"}, str(alert_id_2),
    )
    assert r1.push_status != "duplicate"
    assert r2.push_status != "duplicate"
    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(NotificationRow.user_id == user_id)
        ).scalars().all()
        assert len(rows) == 2


def test_notify_same_alert_id_twice_degrades_to_duplicate_not_500() -> None:
    """The one-shot `WHERE status='active'` CAS in price_alert_evaluator.py
    is what normally prevents this from ever happening in production, but
    verify the constraint's own failure mode directly: a second notify() for
    the exact same (user, type, source_ref) must degrade cleanly, not raise."""
    user_id = uuid4()
    alert_id = uuid4()
    r1 = notify(
        user_id, "price_alert", "Price Alert: AAPL", "body1",
        {"route": "open_holding_detail", "ticker": "AAPL"}, str(alert_id),
    )
    r2 = notify(
        user_id, "price_alert", "Price Alert: AAPL (again)", "body2",
        {"route": "open_holding_detail", "ticker": "AAPL"}, str(alert_id),
    )
    assert r1.push_status != "duplicate"
    assert r2.was_duplicate
    assert r2.notification_id == r1.notification_id
    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(NotificationRow.user_id == user_id)
        ).scalars().all()
        assert len(rows) == 1


def test_notify_null_source_ref_never_collides_even_for_same_user_and_type() -> None:
    """Callers that never pass source_ref (the majority — game events,
    trial-end, Room verdicts, ...) must be completely unaffected: SQL
    treats NULL as distinct from NULL in a unique constraint. Also
    independently confirmed against a real throwaway Postgres 16 instance
    during this audit (not just sqlite, which the shipped suite is
    restricted to) — see CR095.auditor.md round 2."""
    user_id = uuid4()
    r1 = notify(user_id, "trial_end", "t1", "b1", {})
    r2 = notify(user_id, "trial_end", "t2", "b2", {})
    assert r1.push_status != "duplicate"
    assert r2.push_status != "duplicate"
    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(NotificationRow.user_id == user_id)
        ).scalars().all()
        assert len(rows) == 2
