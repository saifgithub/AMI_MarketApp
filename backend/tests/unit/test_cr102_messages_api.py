"""CR102 — /v1/messages user API: newest-first inbox with both directions,
and the cross-user 404s — indistinguishable from a nonexistent id, same
pattern as feedback ack (the user_id predicate IS the authorization)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.messages import router as messages_router
from app.db import get_session
from app.db.models import User
from app.schemas.messages import AdminSendRequest, Audience
from app.services.auth_service import _scaffold_token
from app.services.inbox_store import get_inbox_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(messages_router)
    return TestClient(app)


def _auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_scaffold_token(user_id, token_version=1)}"}


def _make_user() -> UUID:
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, device_model="iPhone18,1", last_app_version="0.1.0+54"))
    return uid


def _send_high() -> None:
    get_inbox_store().send(
        AdminSendRequest(
            title="Heads up",
            body="AMI has a new build for you.",
            priority="high",
            audience=Audience(mode="all"),
        )
    )


def test_inbox_newest_first_both_directions_with_priority(client: TestClient) -> None:
    uid = _make_user()
    _send_high()
    msg_id = get_inbox_store().list_inbox(uid)[0].id
    get_inbox_store().reply(uid, msg_id, "thanks!")

    r = client.get("/v1/messages", headers=_auth(uid))
    assert r.status_code == 200
    rows = r.json()
    assert [row["direction"] for row in rows] == ["in", "out"]  # newest first
    assert rows[1]["priority"] == "high" and rows[1]["read_at"] is None
    assert rows[0]["priority"] is None  # replies carry no broadcast priority
    assert rows[0]["reply_to_id"] == str(msg_id)
    assert "toasted_at" in rows[1]


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get("/v1/messages").status_code == 401


def test_read_reply_toasted_cross_user_404_like_nonexistent(client: TestClient) -> None:
    owner = _make_user()
    intruder = _make_user()
    _send_high()
    msg_id = get_inbox_store().list_inbox(owner)[0].id

    for path, body in (
        (f"/v1/messages/{msg_id}/read", None),
        (f"/v1/messages/{msg_id}/reply", {"body": "hi"}),
        (f"/v1/messages/{msg_id}/toasted", None),
    ):
        foreign = client.post(path, headers=_auth(intruder), json=body)
        ghost = client.post(
            path.replace(str(msg_id), str(uuid4())), headers=_auth(intruder), json=body
        )
        assert foreign.status_code == 404
        # Indistinguishable from a nonexistent id — no probing signal.
        assert (foreign.status_code, foreign.json()) == (ghost.status_code, ghost.json())


def test_read_and_toasted_happy_path_204(client: TestClient) -> None:
    uid = _make_user()
    _send_high()
    msg_id = get_inbox_store().list_inbox(uid)[0].id
    assert client.post(f"/v1/messages/{msg_id}/read", headers=_auth(uid)).status_code == 204
    assert client.post(f"/v1/messages/{msg_id}/toasted", headers=_auth(uid)).status_code == 204
    row = client.get("/v1/messages", headers=_auth(uid)).json()[0]
    assert row["read_at"] is not None and row["toasted_at"] is not None


def test_reply_body_over_2000_chars_is_422(client: TestClient) -> None:
    uid = _make_user()
    _send_high()
    msg_id = get_inbox_store().list_inbox(uid)[0].id
    r = client.post(
        f"/v1/messages/{msg_id}/reply", headers=_auth(uid), json={"body": "x" * 2001}
    )
    assert r.status_code == 422
    ok = client.post(
        f"/v1/messages/{msg_id}/reply", headers=_auth(uid), json={"body": "x" * 2000}
    )
    assert ok.status_code == 200
    assert ok.json()["reply_to_id"] == str(msg_id)
