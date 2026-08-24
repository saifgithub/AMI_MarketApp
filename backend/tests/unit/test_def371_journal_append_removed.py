"""DEF371 (security review M11) — the streak ladder is not farmable by POSTing junk.

`_activity_days` counts `JournalEntryRow.created_at` from any source, and
`POST /v1/journal` accepted an arbitrary entry from any authenticated user. One
throwaway POST a day walked the 7/30/100/365 ladder for **630 real credits**
without doing a single thing the streak is meant to reward.

**Two things the fix had to get past, both recorded because both are wrong
turns a future reader might repeat.**

1. The review's suggested fix — *"only system-generated entry types qualify"* —
   does not work as stated. **Every** value of `EntryType` is system-generated;
   there is no user-authored type to exclude, so a type filter excludes nothing.
2. Gating the route behind `get_admin` does not work either. This router
   already carries `dependencies=[Depends(get_current_user)]`, and both gates
   read the same `Authorization` header — a caller with the admin secret cannot
   also present a user bearer, so the route would have been satisfiable by
   nobody. **The guard for this fix is what discovered that**, which is what a
   guard is for.

So the route was **deleted**. It had no caller: the app uses the read, note,
delete, restore and trash paths and never the bare POST; internal capture calls
`get_journal_store().append(...)` in Python without crossing HTTP; and a
repo-wide search found only this file. No caller, one abuser — C2's shape.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.journal import router as journal_router
from app.schemas.journal import EntryType
from app.services.auth_service import AuthService


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(journal_router)
    return TestClient(app, raise_server_exceptions=False)


def _user() -> tuple[str, dict]:
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _post(client, headers, user_id, entry_type=EntryType.ROOM_RUN):
    return client.post(
        "/v1/journal",
        json={
            "user_id": str(user_id),
            "entry_type": entry_type.value,
            "title": "farmed",
            "body": "farmed",
        },
        headers=headers,
    )


def test_an_authenticated_user_cannot_append_a_journal_entry(client):
    """THE regression. A 201 here is one rung of the credit ladder."""
    user_id, headers = _user()
    r = _post(client, headers, user_id)
    assert r.status_code in (404, 405), r.text


def test_no_entry_type_is_a_way_around_it(client):
    """Swept, because the review framed the fix as a type restriction — if one
    type slipped through, the ladder is farmable again at that type."""
    user_id, headers = _user()
    for et in EntryType:
        r = _post(client, headers, et and user_id, entry_type=et)
        assert r.status_code in (404, 405), (et, r.status_code)


def test_an_unauthenticated_caller_cannot_append_either(client):
    r = client.post(
        "/v1/journal",
        json={"user_id": str(uuid4()), "entry_type": "room_run",
              "title": "x", "body": "x"},
    )
    assert r.status_code in (401, 403, 404, 405)


def test_the_route_is_gone_from_the_router():
    """Structural. The behavioural tests above would also pass if the route
    merely started 404ing for an unrelated reason; this names the actual fix."""
    from app.api import journal

    bare_posts = [
        r for r in journal.router.routes
        if getattr(r, "path", "").rstrip("/").endswith("journal")
        and "POST" in getattr(r, "methods", set())
    ]
    assert bare_posts == [], bare_posts


def test_internal_capture_still_works_without_crossing_http():
    """The gate must not break the path every real entry actually uses — if it
    did, the whole journal would go dark, which is a bigger defect than the one
    being fixed."""
    from app.schemas.journal import JournalEntryCreate
    from app.services.journal_store import get_journal_store

    user_id, _ = _user()
    entry = get_journal_store().append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.SIM_TRADE,
        title="internal", body="written in Python, not over the wire",
    ))
    assert entry.id is not None


def test_the_other_journal_routes_still_work(client):
    """Deleting one route must not take its neighbours with it."""
    user_id, headers = _user()
    r = client.get(f"/v1/journal/{user_id}", headers=headers)
    assert r.status_code == 200, r.text
