"""UAT area: platform, version gate & seeding (CR263, cases/platform.yaml)."""

import pytest


@pytest.mark.uat("UAT-PLAT-001")
def test_health_and_ready(api):
    h = api.get("/v1/health")
    assert h.status_code == 200
    assert h.json()["status"] == "ok"
    assert len(h.json()["version"]) >= 7
    r = api.get("/v1/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True
    assert r.json()["failed_probes"] == []


@pytest.mark.uat("UAT-PLAT-002")
def test_release_floor_blocks_old_builds(api):
    floor = api.get("/v1/client/release-floor").json()["min_build"]
    old = api.get("/v1/client/release-floor", params={"build": max(floor - 1, 0), "platform": "ios"}).json()
    assert old["action"] == "block"
    # Until IOS_TESTFLIGHT_JOIN_URL is set this is the generic TestFlight page
    # (CR121's loud fallback) — still an Apple link, never a dead button.
    assert (old["store_url"] or "").startswith(("https://apps.apple.com/", "https://testflight.apple.com/"))
    cur = api.get("/v1/client/release-floor", params={"build": floor, "platform": "android"}).json()
    assert cur["action"] in ("ok", "nag")
    assert "play.google.com" in (cur["store_url"] or "")


@pytest.mark.uat("UAT-PLAT-003")
def test_seeding_round_trip(seed):
    u = seed.anon_user()
    before = seed.detail(u)
    seed.set_plan(u, "trader")
    seed.add_credits(u, 5)
    after = seed.detail(u)
    assert after["last_app_version"] == "uat"
    assert after["plan"] == "trader"
    assert after["credit_balance"] == before["credit_balance"] + 5
    me = u.get("/v1/auth/me")
    assert me.status_code == 200
    assert str(me.json()["id"]) == u.id


@pytest.mark.uat("UAT-PLAT-007")
def test_every_error_carries_a_trace_id_in_header_and_body(api):
    import uuid

    from client import exempt_headers  # DEF490: spoofed IPs are ignored since DEF464
    fake_ip = exempt_headers()
    forged = str(uuid.uuid4())

    responses = [
        (404, api.get("/v1/_uat_no_such_route")),
        (401, api.get("/v1/feedback/updates")),
        (422, api.post("/v1/feedback/bug", files={"title": (None, "x")}, headers=fake_ip)),
        (401, api.get("/v1/feedback/updates", headers={"X-Request-Id": forged})),
    ]
    seen = set()
    for status, r in responses:
        assert r.status_code == status, r.text
        header_id = r.headers.get("x-request-id")
        assert header_id, f"{status} response has no X-Request-Id header"
        uuid.UUID(header_id)
        body = r.json()
        assert body["request_id"] == header_id, f"{status}: body request_id != header"
        assert "detail" in body
        seen.add(header_id)
    assert len(seen) == len(responses), "two errors shared a trace id"
    assert isinstance(responses[2][1].json()["detail"], list)
    assert responses[3][1].headers["x-request-id"] != forged
    assert forged not in responses[3][1].text
