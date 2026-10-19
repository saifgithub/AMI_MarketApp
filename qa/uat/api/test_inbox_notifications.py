"""UAT area: inbox, notification centre & push (CR263, cases/inbox_notifications.yaml)."""

import uuid

import pytest


@pytest.fixture(scope="module")
def pair(seed):
    return seed.user(plan="floor_pass"), seed.user(plan="floor_pass")


@pytest.mark.uat("UAT-INBOX-001")
def test_new_user_has_empty_inbox_and_centre(pair):
    u, _ = pair
    inbox = u.get("/v1/messages")
    assert inbox.status_code == 200 and inbox.json() == []
    lst = u.get(f"/v1/notifications/{u.id}")
    assert lst.status_code == 200 and lst.json() == {"items": [], "total": 0}
    assert u.get(f"/v1/notifications/{u.id}/unread_count").json() == {"unread": 0}
    ra = u.post(f"/v1/notifications/{u.id}/read_all")
    assert ra.status_code == 200 and ra.json() == {"updated": 0}
    assert u.get(f"/v1/notifications/{u.id}/unread_count").json() == {"unread": 0}


@pytest.mark.uat("UAT-INBOX-002")
def test_preferences_round_trip(seed):
    u = seed.user(plan="floor_pass")
    path = f"/v1/notifications/{u.id}/preferences"
    items = u.get(path).json()["items"]
    types = [i["type"] for i in items]
    assert len(types) >= 8 and len(set(types)) == len(types)
    assert all(i["enabled"] is True for i in items)

    target = "price_alert"
    off = u.patch(path, json={"updates": {target: False}})
    assert off.status_code == 200
    got = {i["type"]: i for i in u.get(path).json()["items"]}
    assert got[target]["enabled"] is False and got[target]["updated_at"]
    assert all(got[t]["enabled"] is True for t in types if t != target)

    on = u.patch(path, json={"updates": {target: True}})
    assert on.status_code == 200
    assert {i["type"]: i["enabled"] for i in on.json()["items"]}[target] is True

    assert u.patch(path, json={"updates": {"not_a_type": False}}).status_code == 422
    assert u.patch(path, json={"updates": {}}).status_code == 422
    assert all(i["enabled"] for i in u.get(path).json()["items"])


@pytest.mark.uat("UAT-INBOX-003")
def test_routes_are_owner_only_and_404_unknown_rows(pair, api):
    a, b = pair
    base = f"/v1/notifications/{a.id}"
    assert b.get(base).status_code == 403
    assert b.get(f"{base}/unread_count").status_code == 403
    assert b.post(f"{base}/read_all").status_code == 403
    assert b.get(f"{base}/preferences").status_code == 403
    assert b.patch(f"{base}/preferences", json={"updates": {"price_alert": False}}).status_code == 403
    assert b.post(f"{base}/{uuid.uuid4()}/read").status_code == 403
    assert a.get(f"{base}/preferences").json()["items"][0]["enabled"] is True

    for method, path in (
        ("get", base), ("get", f"{base}/unread_count"), ("post", f"{base}/read_all"),
        ("get", "/v1/messages"),
    ):
        assert getattr(api, method)(path).status_code == 401, path

    assert a.post(f"{base}/{uuid.uuid4()}/read").status_code == 404
    ghost = uuid.uuid4()
    assert a.post(f"/v1/messages/{ghost}/read").status_code == 404
    assert a.post(f"/v1/messages/{ghost}/toasted").status_code == 404
    assert a.post(f"/v1/messages/{ghost}/reply", json={"body": "hello"}).status_code == 404
    assert a.get("/v1/messages").json() == []
    assert api.post(f"/v1/messages/{ghost}/reply", json={"body": "hello"}).status_code == 401
