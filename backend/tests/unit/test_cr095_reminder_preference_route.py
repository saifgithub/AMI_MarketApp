"""CR095 — the write path for the daily-reminder preference.

The reminder job shipped complete and unreachable: `users.daily_reminder_hour`
is NULL for everyone, NULL means off, and nothing in the API wrote it. The tick
would have run every 15 minutes forever and correctly sent nothing, which is the
worst shape of bug to find later — no error, no log, no user complaint, just a
feature that is on and does nothing. CR095's own acceptance says the reminder
fires "at their configured local time"; there was no way to configure it.

These tests are about the boundary, not the arithmetic: the hour round-trips,
`null` really means off, an unknown timezone is rejected here rather than
surfacing inside the tick, and one user cannot write another's row.
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
            id=uuid.uuid4(),
            handle=f"pref_{uuid.uuid4().hex[:8]}",
            locale="en",
            timezone="UTC",
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


def _stored(user_id) -> tuple[int | None, str]:
    with get_session() as s:
        row = s.get(User, user_id)
        return row.daily_reminder_hour, row.timezone


def test_setting_an_hour_and_timezone_persists_both(client: TestClient, user: User) -> None:
    resp = client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"daily_reminder_hour": 8, "timezone": "Asia/Riyadh"}
    assert _stored(user.id) == (8, "Asia/Riyadh")


def test_null_hour_turns_reminders_off(client: TestClient, user: User) -> None:
    """`null` is the off switch — there is no separate enabled flag, precisely so
    the two cannot drift apart."""
    client.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": 8})
    assert _stored(user.id)[0] == 8

    resp = client.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": None})
    assert resp.status_code == 200
    assert _stored(user.id)[0] is None


def test_an_unknown_timezone_is_rejected_at_the_boundary(client: TestClient, user: User) -> None:
    """Rejected here rather than inside the tick.

    A bad zone stored on the row is invisible until the job runs, and then it is
    one user's reminder silently never firing — a failure with no error anyone
    ever sees.
    """
    resp = client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 8, "timezone": "Mars/Olympus_Mons"},
    )
    assert resp.status_code == 400
    assert "Mars/Olympus_Mons" in resp.text
    assert _stored(user.id) == (None, "UTC"), "a rejected request must not write anything"


@pytest.mark.parametrize("hour", [-1, 24, 99])
def test_out_of_range_hours_are_rejected(client: TestClient, user: User, hour: int) -> None:
    resp = client.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": hour})
    assert resp.status_code == 422
    assert _stored(user.id)[0] is None


def test_omitting_timezone_leaves_it_unchanged(client: TestClient, user: User) -> None:
    client.put(
        "/v1/daily_challenge/reminder",
        json={"daily_reminder_hour": 6, "timezone": "Asia/Kuala_Lumpur"},
    )
    client.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": 9})
    assert _stored(user.id) == (9, "Asia/Kuala_Lumpur")


def test_a_user_can_only_write_their_own_row(user: User) -> None:
    """There is no user_id in the path — the row is resolved from the
    authenticated caller. This pins that, so nobody later "helpfully" adds a
    path parameter and turns it into an IDOR.
    """
    other = User(
        id=uuid.uuid4(),
        handle=f"other_{uuid.uuid4().hex[:8]}",
        locale="en",
        timezone="UTC",
    )
    with get_session() as s:
        s.add(other)
        s.commit()
        s.refresh(other)
        s.expunge(other)

    app = FastAPI()
    app.include_router(daily_challenge_router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    client.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": 7})

    assert _stored(user.id)[0] == 7
    assert _stored(other.id)[0] is None, "another user's row was modified"
