"""CR135 — /v1/notifications user API: paginated newest-first list,
idempotent mark-read with cross-user 404s indistinguishable from a
nonexistent id, preferences round-trip, and the server-side push
suppression a disabled type gets inside notify() — plus the vocabulary
parity check that keeps NOTIFICATION_TYPES in lockstep with every
emitter's actual type constant (DEF210 class, backend side)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.notifications import router as notifications_router
from app.core.config import settings
from app.db import get_session
from app.db.models import NotificationRow, User
from app.schemas.notifications import NOTIFICATION_TYPES
from app.services import notification_service
from app.services.auth_service import _scaffold_token


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(notifications_router)
    return TestClient(app)


def _auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_scaffold_token(user_id, token_version=1)}"}


def _make_user() -> UUID:
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, device_model="iPhone18,1", last_app_version="0.1.0+54"))
    return uid


_T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _notify(uid: UUID, n: int, type: str = "price_alert") -> UUID:
    """One durable row, push skipped, created_at pinned so ordering is exact."""
    result = notification_service.notify(
        uid, type, f"title {n}", f"body {n}",
        {"route": "open_holding_detail", "ticker": "AAPL"},
        attempt_push=False, created_at=_T0 + timedelta(minutes=n),
    )
    return result.notification_id


def test_list_newest_first_and_paginated(client: TestClient) -> None:
    uid = _make_user()
    ids = [_notify(uid, n) for n in range(3)]

    r = client.get(f"/v1/notifications/{uid}", headers=_auth(uid))
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 3
    assert [row["id"] for row in page["items"]] == [str(i) for i in reversed(ids)]
    assert page["items"][0]["deep_link"]["ticker"] == "AAPL"
    assert page["items"][0]["read_at"] is None

    r2 = client.get(
        f"/v1/notifications/{uid}?limit=1&offset=1", headers=_auth(uid)
    )
    assert r2.status_code == 200
    assert r2.json()["total"] == 3
    assert [row["id"] for row in r2.json()["items"]] == [str(ids[1])]


def test_list_never_leaks_another_users_rows(client: TestClient) -> None:
    mine = _make_user()
    theirs = _make_user()
    my_id = _notify(mine, 0)
    their_id = _notify(theirs, 1)

    page = client.get(f"/v1/notifications/{mine}", headers=_auth(mine)).json()
    assert [row["id"] for row in page["items"]] == [str(my_id)]
    assert page["total"] == 1
    assert str(their_id) not in {row["id"] for row in page["items"]}


def test_path_user_mismatch_is_403(client: TestClient) -> None:
    me = _make_user()
    other = _make_user()
    assert (
        client.get(f"/v1/notifications/{other}", headers=_auth(me)).status_code
        == 403
    )


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get(f"/v1/notifications/{uuid4()}").status_code == 401


def test_mark_read_is_idempotent(client: TestClient) -> None:
    uid = _make_user()
    nid = _notify(uid, 0)

    assert (
        client.post(
            f"/v1/notifications/{uid}/{nid}/read", headers=_auth(uid)
        ).status_code
        == 204
    )
    with get_session() as s:
        first_stamp = s.get(NotificationRow, nid).read_at
    assert first_stamp is not None

    assert (
        client.post(
            f"/v1/notifications/{uid}/{nid}/read", headers=_auth(uid)
        ).status_code
        == 204
    )
    with get_session() as s:
        assert s.get(NotificationRow, nid).read_at == first_stamp


def test_mark_read_cross_user_404_like_nonexistent(client: TestClient) -> None:
    owner = _make_user()
    intruder = _make_user()
    nid = _notify(owner, 0)

    foreign = client.post(
        f"/v1/notifications/{intruder}/{nid}/read", headers=_auth(intruder)
    )
    ghost = client.post(
        f"/v1/notifications/{intruder}/{uuid4()}/read", headers=_auth(intruder)
    )
    assert foreign.status_code == 404
    # Indistinguishable from a nonexistent id — no probing signal.
    assert (foreign.status_code, foreign.json()) == (ghost.status_code, ghost.json())
    with get_session() as s:
        assert s.get(NotificationRow, nid).read_at is None


def test_read_all_and_unread_count(client: TestClient) -> None:
    uid = _make_user()
    bystander = _make_user()
    for n in range(3):
        _notify(uid, n)
    other_id = _notify(bystander, 9)

    r = client.get(f"/v1/notifications/{uid}/unread_count", headers=_auth(uid))
    assert (r.status_code, r.json()) == (200, {"unread": 3})

    r = client.post(f"/v1/notifications/{uid}/read_all", headers=_auth(uid))
    assert (r.status_code, r.json()) == (200, {"updated": 3})

    r = client.get(f"/v1/notifications/{uid}/unread_count", headers=_auth(uid))
    assert (r.status_code, r.json()) == (200, {"unread": 0})

    # Idempotent, and the bystander's rows were never touched.
    r = client.post(f"/v1/notifications/{uid}/read_all", headers=_auth(uid))
    assert (r.status_code, r.json()) == (200, {"updated": 0})
    with get_session() as s:
        assert s.get(NotificationRow, other_id).read_at is None


def test_preferences_default_all_enabled(client: TestClient) -> None:
    uid = _make_user()
    r = client.get(f"/v1/notifications/{uid}/preferences", headers=_auth(uid))
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["type"] for i in items] == list(NOTIFICATION_TYPES)
    assert all(i["enabled"] is True and i["updated_at"] is None for i in items)


def test_preferences_round_trip(client: TestClient) -> None:
    uid = _make_user()
    r = client.patch(
        f"/v1/notifications/{uid}/preferences",
        headers=_auth(uid),
        json={"updates": {"price_alert": False, "game_settled": False}},
    )
    assert r.status_code == 200
    by_type = {i["type"]: i for i in r.json()["items"]}
    assert by_type["price_alert"]["enabled"] is False
    assert by_type["price_alert"]["updated_at"] is not None
    assert by_type["game_settled"]["enabled"] is False
    assert by_type["daily_reminder"]["enabled"] is True

    r2 = client.get(f"/v1/notifications/{uid}/preferences", headers=_auth(uid))
    assert {i["type"]: i["enabled"] for i in r2.json()["items"]} == {
        t: t not in ("price_alert", "game_settled") for t in NOTIFICATION_TYPES
    }

    r3 = client.patch(
        f"/v1/notifications/{uid}/preferences",
        headers=_auth(uid),
        json={"updates": {"price_alert": True}},
    )
    assert r3.status_code == 200
    assert {i["type"]: i["enabled"] for i in r3.json()["items"]} == {
        t: t != "game_settled" for t in NOTIFICATION_TYPES
    }


def test_preferences_unknown_type_is_422_and_named(client: TestClient) -> None:
    uid = _make_user()
    r = client.patch(
        f"/v1/notifications/{uid}/preferences",
        headers=_auth(uid),
        json={"updates": {"room_verdict": False}},
    )
    assert r.status_code == 422
    assert "room_verdict" in r.text
    r_empty = client.patch(
        f"/v1/notifications/{uid}/preferences", headers=_auth(uid),
        json={"updates": {}},
    )
    assert r_empty.status_code == 422


def test_disabled_pref_suppresses_push_but_writes_row(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The acceptance line: server-enforced, not a client-side hide.
    OneSignal is configured and reachable — the ONLY thing stopping the
    push is the stored preference — and the durable row still lands."""
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    calls: list = []

    def _record(*a, **k):
        calls.append(a)
        return SimpleNamespace(status_code=200, text="ok", json=lambda: {"id": "onesignal-id", "recipients": 1})

    monkeypatch.setattr(notification_service.httpx, "post", _record)

    uid = _make_user()
    client.patch(
        f"/v1/notifications/{uid}/preferences", headers=_auth(uid),
        json={"updates": {"price_alert": False}},
    )
    result = notification_service.notify(
        uid, "price_alert", "t", "b", {"route": "open_holding_detail"},
    )
    assert result.push_status == "pref_disabled"
    assert calls == []
    with get_session() as s:
        assert s.get(NotificationRow, result.notification_id) is not None

    enabled_result = notification_service.notify(
        uid, "game_settled", "t", "b", {"route": "open_holding_detail"},
    )
    assert enabled_result.push_status == "sent"
    assert len(calls) == 1


def test_vocabulary_matches_every_emitter() -> None:
    """DEF210 class, backend side: the canonical vocabulary must contain the
    exact constant every emitter passes to notify(). The Dart-enum half of the
    parity check ships with the CR135 mobile lane."""
    from app.services import daily_reminder, games_push, sim_order_push

    emitted = {
        "price_alert",  # price_alert_evaluator passes the literal inline
        daily_reminder._NOTIFICATION_TYPE,
        games_push.TYPE_ENTRIES_CLOSING,
        games_push.TYPE_FINAL_STRETCH,
        games_push.TYPE_SETTLED,
        games_push.TYPE_RANK_MOVE,
        sim_order_push.TYPE_FILLED,
        sim_order_push.TYPE_TRIGGERED,
        sim_order_push.TYPE_REJECTED,
    }
    assert emitted == set(NOTIFICATION_TYPES)
