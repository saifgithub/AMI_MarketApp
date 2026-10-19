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
