"""CR095 auditor pin (round 1) — `PUT /v1/daily_challenge/reminder` treats
an OMITTED `daily_reminder_hour` as an explicit `null`, silently turning
reminders off as a side effect of a request that only meant to change the
timezone.

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


def test_updating_only_timezone_silently_clears_an_existing_hour(
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

    # This is the defect: the previously-configured hour is gone, silently.
    # If/when the endpoint gains real partial-update semantics for
    # `daily_reminder_hour` (mirroring `timezone`'s), this should read
    # `== 8`.
    assert r2.json()["daily_reminder_hour"] is None
    with get_session() as s:
        stored = s.get(User, user.id)
        assert stored.daily_reminder_hour is None, (
            "a timezone-only PUT turned reminders off as a side effect"
        )
        assert stored.timezone == "Asia/Kuala_Lumpur"
