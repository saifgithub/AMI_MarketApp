"""UAT area: authentication, sessions & account identity (CR263, cases/auth.yaml).

Live-Alpha. Every user minted here — including ones minted by deliberately
adversarial `/v1/auth/anon` calls — is registered with the Seeder so teardown
suspends it. Email magic-link sign-in and merge are blocked on a test inbox;
`magic_link/start` is called exactly twice in this file (3/min limit).
"""

import time
import uuid

import pytest

from client import UAT_APP_VERSION, UAT_DEVICE_MODEL, UatUser, new_client


def _mint(seed, *, device_user_id=None, token=None, locale="en", timezone="UTC"):
    """Raw POST /v1/auth/anon (rate limit 10/min/IP, so back off on 429).
    Returns (response, UatUser). The user is registered for teardown."""
    body = {
        "device_user_id": str(device_user_id) if device_user_id else str(uuid.uuid4()),
        "locale": locale, "timezone": timezone,
        "device_model": UAT_DEVICE_MODEL, "os_version": f"uat-run-{seed.run_id}",
        "app_version": UAT_APP_VERSION, "device_install_id": str(uuid.uuid4()),
    }
    with new_client(token) as c:
        for attempt in range(6):
            r = c.post("/v1/auth/anon", json=body)
            if r.status_code != 429:
                break
            time.sleep(10 * (attempt + 1))
    assert r.status_code == 200, r.text
    j = r.json()
    user = UatUser(id=str(j["user"]["id"]), token=j["token"], plan=j["user"].get("plan", "floor_pass"),
                   http=new_client(j["token"]))
    seed.created.append(user)
    return r, user


def _me(token):
    with new_client(token) as c:
        return c.get("/v1/auth/me")


@pytest.mark.uat("UAT-AUTH-001")
def test_anon_bootstrap_mints_tagged_anonymous_user(seed):
    r, u = _mint(seed, locale="ar", timezone="Asia/Riyadh")
    j = r.json()
    assert j["is_new"] is True
    assert j["token"]
    user = j["user"]
    assert user["is_anonymous"] is True
    assert user["claimed_at"] is None
    assert not user["email"] and not user["apple_id"] and not user["google_id"]
    me = u.get("/v1/auth/me")
    assert me.status_code == 200
    assert str(me.json()["id"]) == u.id == str(user["id"])
    detail = seed.detail(u)
    assert detail["locale"] == "ar"
    assert detail["last_app_version"] == "uat"


@pytest.mark.uat("UAT-AUTH-002")
def test_anon_bootstrap_rejects_malformed_device_id(api):
    r = api.post("/v1/auth/anon", json={"device_user_id": "not-a-uuid"})
    assert r.status_code == 422
    assert any("device_user_id" in ".".join(map(str, e["loc"])) for e in r.json()["detail"])
    assert "token" not in r.text


@pytest.mark.uat("UAT-AUTH-003")
def test_rightful_device_rebootstraps_to_same_user(seed):
    _, u = _mint(seed)
    r, again = _mint(seed, device_user_id=u.id, token=u.token)
    j = r.json()
    assert j["is_new"] is False
    assert str(j["user"]["id"]) == u.id
    assert _me(j["token"]).json()["id"] == u.id


@pytest.mark.uat("UAT-AUTH-004")
def test_knowing_a_user_id_does_not_yield_their_token(seed):
    _, victim = _mint(seed)
    _, attacker = _mint(seed)
    r1, _ = _mint(seed, device_user_id=victim.id)
    r2, _ = _mint(seed, device_user_id=victim.id, token=attacker.token)
    for r in (r1, r2):
        j = r.json()
        assert j["is_new"] is True
        assert str(j["user"]["id"]) not in (victim.id, attacker.id)
        got = _me(j["token"])
        assert got.status_code == 200
        assert got.json()["id"] == str(j["user"]["id"])
        assert got.json()["id"] != victim.id
    # The victim's own session is untouched.
    assert victim.get("/v1/auth/me").status_code == 200


@pytest.mark.uat("UAT-AUTH-005")
def test_bad_tokens_are_401(api, seed):
    u = seed.anon_user()
    assert api.get("/v1/auth/me").status_code == 401
    assert _me("garbage").status_code == 401
    assert _me(u.token[:-4] + "0000").status_code == 401
    no_scheme = api.get("/v1/auth/me", headers={"Authorization": u.token})
    assert no_scheme.status_code == 401
    via_query = api.get("/v1/auth/me", params={"token": u.token})
    assert via_query.status_code == 401
    assert api.get("/v1/auth/me").json()["detail"] == "authentication required"
    assert _me("garbage").json()["detail"] == "invalid or expired token"


@pytest.mark.uat("UAT-AUTH-006")
def test_sign_out_revokes_token_and_cannot_be_reminted(seed):
    _, u = _mint(seed)
    assert u.get("/v1/auth/me").status_code == 200
    out = u.delete("/v1/auth/session")
    assert out.status_code == 200
    assert out.json() == {"signed_out": True}
    after = _me(u.token)
    assert after.status_code == 401
    assert after.json()["detail"] == "invalid or expired token"

    r, fresh = _mint(seed, device_user_id=u.id, token=u.token)
    assert r.json()["is_new"] is True
    assert str(r.json()["user"]["id"]) != u.id
    assert _me(u.token).status_code == 401
    assert _me(fresh.token).status_code == 200


@pytest.mark.uat("UAT-AUTH-007")
def test_sign_out_requires_a_session(api):
    assert api.delete("/v1/auth/session").status_code == 401
    with new_client("garbage") as c:
        assert c.delete("/v1/auth/session").status_code == 401


@pytest.mark.uat("UAT-AUTH-008")
def test_suspended_account_is_locked_out(seed, admin):
    _, u = _mint(seed)
    assert u.get("/v1/auth/me").status_code == 200
    s = admin.post(f"/v1/admin/users/{u.id}/suspend", json={"note": "CR263 UAT-AUTH-008"})
    assert s.status_code in (200, 409), s.text
    me = _me(u.token)
    assert me.status_code == 403
    assert me.json()["detail"] == "account_suspended"
    r, _ = _mint(seed, device_user_id=u.id, token=u.token)
    assert r.json()["is_new"] is True
    assert str(r.json()["user"]["id"]) != u.id


@pytest.mark.uat("UAT-AUTH-009")
@pytest.mark.parametrize("route", ["/v1/auth/apple", "/v1/auth/google"])
def test_oidc_sign_in_rejects_bad_input(route, api, seed):
    u = seed.anon_user()
    garbage = u.post(route, json={"identity_token": "x.y.z"})
    assert garbage.status_code == 400, garbage.text
    assert "undecodable" in garbage.json()["detail"].lower() or "token" in garbage.json()["detail"].lower()
    anon = api.post(route, json={"identity_token": "x.y.z"})
    assert anon.status_code == 401
    assert anon.json()["detail"] == "authentication required"
    empty = u.post(route, json={})
    assert empty.status_code == 422
    assert any("identity_token" in ".".join(map(str, e["loc"])) for e in empty.json()["detail"])
    me = u.get("/v1/auth/me").json()
    assert me["is_anonymous"] is True
    assert not me["apple_id"] and not me["google_id"]


@pytest.mark.uat("UAT-AUTH-010")
def test_magic_link_start_contract_and_no_code_leak(api, seed):
    # The ONLY two magic_link/start calls in the suite (3/min per IP).
    u = seed.anon_user()
    ok = u.post("/v1/auth/magic_link/start", json={"email": "uat-cr263@example.com"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["sent"] is True
    assert ok.json()["debug_code"] is None
    anon = api.post("/v1/auth/magic_link/start", json={"email": "uat-cr263@example.com"})
    assert anon.status_code == 401
    assert anon.json()["detail"] == "authentication required"


@pytest.mark.uat("UAT-AUTH-011")
def test_magic_link_verify_refuses_without_session_or_challenge(api, seed):
    u = seed.anon_user()
    no_auth = api.post("/v1/auth/magic_link/verify",
                       json={"email": "uat-nochallenge@example.com", "code": "123456"})
    assert no_auth.status_code == 401
    assert no_auth.json()["detail"] == "authentication required"
    no_challenge = u.post("/v1/auth/magic_link/verify",
                          json={"email": f"uat-nochallenge-{uuid.uuid4().hex[:8]}@example.com", "code": "000000"})
    assert no_challenge.status_code == 401
    assert no_challenge.json()["detail"] == "invalid or expired code"
    missing = u.post("/v1/auth/magic_link/verify", json={"email": "uat-nochallenge@example.com"})
    assert missing.status_code == 422
    assert u.get("/v1/auth/me").json()["is_anonymous"] is True


@pytest.mark.uat("UAT-AUTH-012")
def test_merge_requires_a_recorded_adoption(api, seed):
    caller = seed.anon_user()
    other = seed.anon_user()
    for resp in (
        caller.get(f"/v1/auth/merge/preview/{other.id}"),
        caller.get(f"/v1/auth/merge/preview/{uuid.uuid4()}"),
        caller.post("/v1/auth/merge", json={"from_user_id": other.id}),
    ):
        assert resp.status_code == 403, resp.text
        assert "no recorded adoption" in resp.json()["detail"]
    assert api.get(f"/v1/auth/merge/preview/{other.id}").status_code == 401
    assert api.post("/v1/auth/merge", json={"from_user_id": other.id}).status_code == 401
    assert other.get("/v1/auth/me").status_code == 200


@pytest.mark.uat("UAT-AUTH-013")
def test_handle_regenerates_exactly_once(api, seed):
    u = seed.anon_user()
    first = u.get("/v1/me")
    assert first.status_code == 200
    assert "handle" in first.json()
    regen = u.patch("/v1/me/handle")
    assert regen.status_code == 200
    handle = regen.json()["handle"]
    assert isinstance(handle, str) and handle.strip()
    assert u.get("/v1/me").json()["handle"] == handle
    again = u.patch("/v1/me/handle")
    assert again.status_code == 409
    assert again.json()["detail"] == "already_regenerated"
    assert u.get("/v1/me").json()["handle"] == handle
    assert api.get("/v1/me").status_code == 401
    assert api.patch("/v1/me/handle").status_code == 401


@pytest.mark.uat("UAT-AUTH-014")
def test_legacy_handle_alias_shares_the_once_only_rule(seed):
    u = seed.anon_user()
    legacy = u.patch("/v1/league/handle")
    assert legacy.status_code == 200
    assert legacy.json()["handle"]
    again = u.patch("/v1/me/handle")
    assert again.status_code == 409
    assert again.json()["detail"] == "already_regenerated"


@pytest.mark.uat("UAT-AUTH-015")
def test_handles_are_per_user(seed):
    a, b = seed.anon_user(), seed.anon_user()
    b_before = b.get("/v1/me").json()["handle"]
    a_new = a.patch("/v1/me/handle").json()["handle"]
    assert a.get("/v1/me").json()["handle"] == a_new
    assert b.get("/v1/me").json()["handle"] == b_before
    assert b.patch("/v1/me/handle").status_code == 200
