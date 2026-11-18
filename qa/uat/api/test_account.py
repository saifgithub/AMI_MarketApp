"""UAT area: account closure and data export (CR276, cases/auth.yaml 040-043).

Live-Alpha. Every user minted here is registered with the Seeder so teardown
suspends it. The users closed in this file are throwaway guests; the post-grace
erasure itself (UAT-AUTH-046) needs the database and is a manual case.
"""

import uuid

import pytest

from client import UAT_APP_VERSION, UAT_DEVICE_MODEL, UatUser, new_client


def _second_session(seed, user: UatUser) -> UatUser:
    """A second bearer for the SAME user (the rightful device re-bootstraps)."""
    body = {
        "device_user_id": user.id, "locale": "en", "timezone": "UTC",
        "device_model": UAT_DEVICE_MODEL, "os_version": f"uat-run-{seed.run_id}",
        "app_version": UAT_APP_VERSION, "device_install_id": str(uuid.uuid4()),
    }
    r = user.post("/v1/auth/anon", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["user"]["id"] == user.id
    return UatUser(id=user.id, token=j["token"], plan=user.plan, http=new_client(j["token"]))


@pytest.mark.uat("UAT-AUTH-040")
def test_policy_states_delete_wording_and_grace(api):
    r = api.get("/v1/account/policy")
    assert r.status_code == 200
    p = r.json()
    assert p["mode"] in ("delete", "anonymise")
    assert p["wording"] == "delete"
    assert p["grace_days"] == 30
    assert p["export_available"] is True


@pytest.mark.uat("UAT-AUTH-041")
def test_close_needs_confirm_and_revokes_every_session(seed):
    u = seed.user()
    second = _second_session(seed, u)
    assert u.get("/v1/auth/me").status_code == 200
    assert second.get("/v1/auth/me").status_code == 200

    refused = u.post("/v1/account/close", json={})
    assert refused.status_code == 400
    assert u.get("/v1/auth/me").status_code == 200 and second.get("/v1/auth/me").status_code == 200

    r = u.post("/v1/account/close", json={"confirm": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["closed"] is True and body["grace_days"] == 30
    from datetime import datetime
    asked = datetime.fromisoformat(body["closure_requested_at"])
    until = datetime.fromisoformat(body["restorable_until"])
    assert (until - asked).days == 30

    for session in (u, second):
        assert session.get("/v1/auth/me").status_code == 401
        assert session.get("/v1/account/export").status_code == 401


@pytest.mark.uat("UAT-AUTH-042")
def test_export_is_own_data_only_a_download_and_secret_free(seed, api):
    a, b = seed.user(), seed.user()
    assert a.post(f"/v1/watchlist/{a.id}", json={"ticker": "AAPL"}).status_code in (200, 201)
    assert b.post(f"/v1/watchlist/{b.id}", json={"ticker": "MSFT"}).status_code in (200, 201)

    r = a.get("/v1/account/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "ami-data-export-" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    doc = r.json()
    assert doc["schema_version"] == 1
    assert doc["profile"]["id"] == a.id
    for section in ("mandates", "journal", "lesson_progress", "settings", "sim_trades", "rooms"):
        assert section in doc, section
    assert [w["ticker"] for w in doc["watchlist"]] == ["AAPL"]
    assert b.id not in r.text and "MSFT" not in r.text

    lowered = r.text.lower()
    for needle in ("api_key", "secret", "password", "code_hash", "token_version"):
        assert needle not in lowered, needle
    assert all("transcript" not in room for room in doc["rooms"])

    assert api.get("/v1/account/export").status_code == 401


@pytest.mark.uat("UAT-AUTH-043")
def test_closed_anonymous_device_starts_over_as_a_new_user(seed):
    u = seed.user()
    assert u.post("/v1/account/close", json={"confirm": True}).status_code == 200

    body = {
        "device_user_id": u.id, "locale": "en", "timezone": "UTC",
        "device_model": UAT_DEVICE_MODEL, "os_version": f"uat-run-{seed.run_id}",
        "app_version": UAT_APP_VERSION, "device_install_id": str(uuid.uuid4()),
    }
    with new_client(u.token) as c:
        r = c.post("/v1/auth/anon", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["is_new"] is True and j["user"]["id"] != u.id
    seed.created.append(UatUser(id=str(j["user"]["id"]), token=j["token"],
                                plan=j["user"].get("plan", "floor_pass"),
                                http=new_client(j["token"])))
    with new_client(j["token"]) as c:
        assert c.get("/v1/auth/me").status_code == 200
    assert u.get("/v1/auth/me").status_code == 401
