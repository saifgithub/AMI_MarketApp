"""CR095 auditor pin (round 1, FIXED in round 2) — `PUT
/v1/daily_challenge/reminder` used to treat an OMITTED `daily_reminder_hour`
as an explicit `null`, silently turning reminders off as a side effect of a
request that only meant to change the timezone.

**Now asserts the fixed behaviour**: an omitted hour leaves the stored value
alone, an explicit `null` still turns reminders off. Both directions are
tested, because a fix that made the field simply un-clearable would pass the
first assertion and break the column's only "off" value.

The fix is `if "daily_reminder_hour" in req.model_fields_set:` in
`app/api/daily_challenge.py` — `model_fields_set` carries exactly the
omitted-vs-explicitly-null distinction that Pydantic drops on the value.

Original defect description follows, kept because it is why this pin exists:

`ReminderPreference.timezone` has explicit "leave unchanged" semantics
(`if req.timezone is not None: row.timezone = req.timezone`) documented in
its own Field description ("Omit to leave unchanged"). `daily_reminder_hour`
has NO such guard — the route unconditionally does
`row.daily_reminder_hour = req.daily_reminder_hour`, and Pydantic's default
for an omitted field is the same `None` used for an explicit "turn off".
The two are indistinguishable at the route, so a caller that PUTs only
`{"timezone": "..."}` intending a partial update gets their reminder turned
off with no error — CR040 territory: nothing tells them their `hour` was
just cleared. No test in the CR095 submission exercises "omit hour, keep
tz" (only the reverse, "omit tz, keep hour", is covered).

Not the common case today (mobile isn't wired to this endpoint yet — CR095's
own "Known gaps"), but the asymmetry is untested, undocumented, and a live
trap for whichever slice wires up Settings next.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.daily_challenge import router as daily_challenge_router
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User


@pytest.fixture()
def user() -> User:
    with get_session() as s:
        row = User(
            id=uuid.uuid4(), handle=f"pref_{uuid.uuid4().hex[:8]}",
            locale="en", timezone="UTC",
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


def test_updating_only_timezone_leaves_an_existing_hour_alone(
    client: TestClient, user: User,
) -> None:
    # User already has reminders on at hour=8.
    r1 = client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"},
    )
    assert r1.status_code == 200
    assert r1.json()["daily_reminder_hour"] == 8

    # A later request meant only to update the timezone (no
    # `daily_reminder_hour` key at all in the JSON body — the shape a
    # "just change my timezone" client would naturally send).
    r2 = client.put(
        "/v1/daily_challenge/reminder", json={"timezone": "Asia/Kuala_Lumpur"},
    )
    assert r2.status_code == 200

    assert r2.json()["daily_reminder_hour"] == 8
    with get_session() as s:
        stored = s.get(User, user.id)
        assert stored.daily_reminder_hour == 8, (
            "a timezone-only PUT turned reminders off as a side effect — the "
            "route is treating an omitted field as an explicit null again"
        )
        assert stored.timezone == "Asia/Kuala_Lumpur"


def test_an_explicit_null_hour_still_turns_reminders_off(
    client: TestClient, user: User,
) -> None:
    """The other half, and the reason the fix can't just be "never assign
    when None": `null` is the column's own "off" value, so it has to keep
    working. A fix that made the hour un-clearable would pass the test above
    and silently remove the only way to turn reminders off."""
    client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"},
    )

    r = client.put(
        "/v1/daily_challenge/reminder", json={"daily_reminder_hour": None},
    )
    assert r.status_code == 200
    assert r.json()["daily_reminder_hour"] is None
    with get_session() as s:
        stored = s.get(User, user.id)
        assert stored.daily_reminder_hour is None
        # And the omitted timezone was left alone, as it always was.
        assert stored.timezone == "Asia/Riyadh"
