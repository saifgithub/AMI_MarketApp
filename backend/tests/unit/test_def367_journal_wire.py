"""DEF367 — close the Decision Journal entry / note / trash wire surfaces (AT:B1).

`backend/scripts/wire_contract/verify.py` calls a route -> Dart-model surface
UNVERIFIED when no test drives it through a `TestClient` and gets a real 2xx
JSON body to compare against the keys `api_client.dart` reads. The list route
`GET /v1/journal/$userId` was already observed; its three siblings were not:

  GET  /v1/journal/$userId/entry/$entryId       -> JournalEntry
  POST /v1/journal/$userId/entry/$entryId/note  -> JournalEntry
  GET  /v1/journal/$userId/trash                -> JournalListResponse

The trash route needs a soft-deleted entry in the window, so the test deletes
one through the real DELETE route first.

Test-only: no product code changes.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.journal import router as journal_router
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.auth_service import AuthService
from app.services.journal_store import get_journal_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(journal_router)
    return TestClient(app, raise_server_exceptions=False)


def _user_with_entry():
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    entry = get_journal_store().append(JournalEntryCreate(
        user_id=user.id,
        entry_type=EntryType.AGENT_COACH,
        title="Briefed Bear Researcher -> v1",
        summary="Weigh liquidity more.",
        agents_involved=["bear_researcher"],
    ))
    return user.id, entry.id, {"Authorization": f"Bearer {token}"}


_ENTRY_KEYS = ("id", "user_id", "entry_type", "title", "created_at")


def test_get_entry_returns_the_entry(client: TestClient) -> None:
    user_id, entry_id, headers = _user_with_entry()

    r = client.get(f"/v1/journal/{user_id}/entry/{entry_id}", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(entry_id)
    for key in _ENTRY_KEYS:
        assert key in body, key


def test_annotate_returns_the_updated_entry(client: TestClient) -> None:
    user_id, entry_id, headers = _user_with_entry()

    r = client.post(
        f"/v1/journal/{user_id}/entry/{entry_id}/note",
        json={"note": "Held up under review.", "tags": ["reviewed"]},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(entry_id)
    assert body["user_note"] == "Held up under review."
    assert body["tags"] == ["reviewed"]
    for key in _ENTRY_KEYS:
        assert key in body, key


def test_trash_lists_a_soft_deleted_entry(client: TestClient) -> None:
    user_id, entry_id, headers = _user_with_entry()
    deleted = client.delete(f"/v1/journal/{user_id}/entry/{entry_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    r = client.get(f"/v1/journal/{user_id}/trash", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert [e["id"] for e in body["entries"]] == [str(entry_id)]
    for key in _ENTRY_KEYS:
        assert key in body["entries"][0], key
