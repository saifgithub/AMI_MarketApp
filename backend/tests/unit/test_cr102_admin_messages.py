"""CR102 — /v1/admin/messages*: get_admin gate (403 wrong secret, 503
unset), preview-then-send round trip, broadcast listing with reply
counts, and the since-filtered reply feed."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router as admin_router
from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.services.inbox_store import get_inbox_store

_SECRET = "test-admin-secret-cr102"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user() -> UUID:
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, device_model="iPhone18,1", last_app_version="0.1.0+54"))
    return uid


def _payload(mode: str = "all", **audience_extra) -> dict:
    return {
        "title": "Build 55",
        "body": "Please update.",
        "priority": "normal",
        "audience": {"mode": mode, **audience_extra},
    }


def test_wrong_secret_403_on_every_route(client: TestClient) -> None:
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/v1/admin/messages/preview", headers=bad, json=_payload()).status_code == 403
    assert client.post("/v1/admin/messages", headers=bad, json=_payload()).status_code == 403
    assert client.get("/v1/admin/messages", headers=bad).status_code == 403
    assert client.get("/v1/admin/messages/replies", headers=bad).status_code == 403


def test_unset_secret_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", "")
    assert client.post("/v1/admin/messages/preview", headers=_HDR, json=_payload()).status_code == 503


def test_preview_then_send_round_trip(client: TestClient) -> None:
    uid = _make_user()
    prev = client.post("/v1/admin/messages/preview", headers=_HDR, json=_payload())
    assert prev.status_code == 200
    assert prev.json() == {"recipient_count": 1}

    sent = client.post("/v1/admin/messages", headers=_HDR, json=_payload())
    assert sent.status_code == 200
    assert sent.json()["recipient_count"] == 1
    assert get_inbox_store().list_inbox(uid)[0].title == "Build 55"


def test_targeted_single_user_previews_one_writes_one_row(client: TestClient) -> None:
    uid = _make_user()
    _make_user()  # bystander must not receive
    p = _payload(mode="user", user_ids=[str(uid)])
    assert client.post("/v1/admin/messages/preview", headers=_HDR, json=p).json() == {
        "recipient_count": 1
    }
    client.post("/v1/admin/messages", headers=_HDR, json=p)
    store = get_inbox_store()
    assert len(store.list_inbox(uid)) == 1
    with get_session() as s:
        from sqlalchemy import func, select
        from app.db.models import InboxMessageRow
        assert s.execute(select(func.count()).select_from(InboxMessageRow)).scalar_one() == 1


def test_unknown_audience_key_rejected_loudly(client: TestClient) -> None:
    p = _payload()
    p["audience"]["platform"] = "ios"  # deferred out of CR102 — must not pass silently
    assert client.post("/v1/admin/messages/preview", headers=_HDR, json=p).status_code == 422


def test_list_broadcasts_shows_reply_counts(client: TestClient) -> None:
    uid = _make_user()
    client.post("/v1/admin/messages", headers=_HDR, json=_payload())
    store = get_inbox_store()
    msg_id = store.list_inbox(uid)[0].id
    store.reply(uid, msg_id, "works great")
    r = client.get("/v1/admin/messages", headers=_HDR)
    assert r.status_code == 200
    assert r.json()[0]["reply_count"] == 1
    assert r.json()[0]["recipient_count"] == 1


def test_replies_since_filters(client: TestClient) -> None:
    uid = _make_user()
    client.post("/v1/admin/messages", headers=_HDR, json=_payload())
    store = get_inbox_store()
    msg_id = store.list_inbox(uid)[0].id
    store.reply(uid, msg_id, "fresh reply")

    all_r = client.get("/v1/admin/messages/replies", headers=_HDR)
    assert len(all_r.json()) == 1
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    none_r = client.get(
        "/v1/admin/messages/replies", params={"since": future}, headers=_HDR
    )
    assert none_r.json() == []
