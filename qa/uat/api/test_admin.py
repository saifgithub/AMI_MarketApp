"""UAT area: admin back-office & LLM status (CR263, cases/admin.yaml).

Never calls: POST /v1/admin/messages, anything under /v1/admin/push,
POST /v1/admin/release-floor, LLM translate. The backtest room-run endpoint is
only POSTed with a deliberately invalid ticker, so even a broken gate cannot
start a run (it would 422 on the ticker, not 202).
"""

import uuid

import pytest

from client import admin_secret, new_client

READ_ENDPOINTS = [
    "/v1/admin/config-check",
    "/v1/admin/overview",
    "/v1/admin/bugs",
    "/v1/admin/analytics/summary",
    "/v1/admin/analytics/timeseries",
    "/v1/admin/analytics/revenuecat",
    "/v1/admin/room/runs",
    "/v1/admin/ticker-interest/top",
    "/v1/admin/verdict-outcomes/aggregates",
    "/v1/llm/status",
    "/v1/llm/cache_rate",
]

BACKTEST = "/v1/admin/backtest/room-run"


def _backtest_body(user_id):
    return {"user_id": str(user_id), "ticker": "ZZZZNOTATICKER", "as_of": "2024-01-02",
            "batch_id": "uat-gate-probe"}


@pytest.mark.uat("UAT-ADMIN-001")
def test_admin_reads_refuse_everyone_but_admin(api, seed):
    u = seed.user(plan="floor_manager")
    wrong = new_client("uat-not-the-admin-secret")
    try:
        for who, client in (("anon", api), ("user", u), ("wrong-secret", wrong)):
            for path in READ_ENDPOINTS:
                r = client.get(path)
                assert r.status_code in (401, 403), f"{who} GET {path} -> {r.status_code}"
            r = client.post(BACKTEST, json=_backtest_body(u.id))
            assert r.status_code in (401, 403), f"{who} POST backtest -> {r.status_code}"
            assert r.status_code != 202
    finally:
        wrong.close()


@pytest.mark.uat("UAT-ADMIN-002")
def test_user_token_cannot_escalate(seed):
    u = seed.user(plan="floor_pass")
    before = seed.detail(u)
    uid = u.id
    attempts = [
        u.patch(f"/v1/admin/users/{uid}/plan", json={"plan": "floor_manager", "note": "x"}),
        u.post(f"/v1/admin/users/{uid}/credits", json={"delta": 1000, "note": "x"}),
        u.post(f"/v1/admin/users/{uid}/trial", json={"days": 30, "note": "x"}),
        u.post(f"/v1/admin/users/{uid}/suspend", json={"note": "x"}),
    ]
    for r in attempts:
        assert r.status_code in (401, 403), r.request.url
    after = seed.detail(u)
    for key in ("plan", "credit_balance", "trial_expires_at", "suspended_at", "effective_plan"):
        assert after[key] == before[key], key
    assert len(after["recent_events"]) == len(before["recent_events"])


@pytest.mark.uat("UAT-ADMIN-003")
def test_admin_read_only_views(admin):
    cfg = admin.get("/v1/admin/config-check")
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["env"] and isinstance(body["gates"], list) and body["gates"]
    assert all(isinstance(g["configured"], bool) for g in body["gates"])
    secret = admin_secret()
    assert secret not in cfg.text, "config-check leaked the admin secret"

    ov = admin.get("/v1/admin/overview")
    assert ov.status_code == 200
    ob = ov.json()
    for key in ("ready", "build", "llm", "llm_cache", "release_floor", "bugs", "config"):
        assert key in ob, key
    assert secret not in ov.text

    bugs = admin.get("/v1/admin/bugs")
    assert bugs.status_code == 200 and isinstance(bugs.json()["bugs"], list)
    assert admin.get(f"/v1/admin/bugs/{uuid.uuid4()}").status_code == 404

    summ = admin.get("/v1/admin/analytics/summary")
    assert summ.status_code == 200
    sj = summ.json()
    assert sj["users"]["total"] >= sj["users"]["claimed"] >= 0
    assert set(sj["active"]) >= {"dau", "wau", "mau"}
    ts = admin.get("/v1/admin/analytics/timeseries", params={"days": 7})
    assert ts.status_code == 200 and len(ts.json()["days"]) == 7
    assert admin.get("/v1/admin/analytics/timeseries", params={"days": 0}).status_code == 422
    assert admin.get("/v1/admin/analytics/revenuecat").status_code == 200

    llm = admin.get("/v1/llm/status")
    assert llm.status_code == 200
    lj = llm.json()
    assert lj["active_provider"] and lj["has_real_provider"] is True
    assert lj["active_provider_liveness"]["state"] == "ok"
    cr = admin.get("/v1/llm/cache_rate")
    assert cr.status_code == 200
    cj = cr.json()
    assert cj["status"]
    if cj["status"] != "ok":
        assert cj["rate"] is None
    else:
        assert 0.0 <= cj["rate"] <= 1.0

    assert admin.get("/v1/admin/users").status_code == 400
    empty = admin.get("/v1/admin/users", params={"device_user_id": str(uuid.uuid4())})
    assert empty.status_code == 200 and empty.json() == []


@pytest.mark.uat("UAT-ADMIN-004")
def test_admin_user_management(seed, admin):
    u = seed.user(plan="floor_pass")
    uid = u.id
    d = seed.detail(u)
    found = admin.get("/v1/admin/users", params={"device_user_id": d["device_user_id"]}).json()
    assert [x["id"] for x in found] == [uid]
    assert admin.get(f"/v1/admin/users/{uuid.uuid4()}").status_code == 404

    assert admin.patch(f"/v1/admin/users/{uid}/plan", json={"plan": "platinum", "note": "x"}).status_code == 400
    assert admin.patch(f"/v1/admin/users/{uid}/plan", json={"plan": "trader", "note": "CR263 UAT"}).json()["plan"] == "trader"

    t = admin.post(f"/v1/admin/users/{uid}/trial", json={"days": 3, "note": "CR263 UAT"}).json()
    assert t["plan"] == "trial_trader" and t["trial_active"] is True
    expires = t["trial_expires_at"]
    ext = admin.patch(f"/v1/admin/users/{uid}/trial", json={"action": "extend", "days": 2, "note": "CR263 UAT"}).json()
    assert ext["trial_expires_at"] > expires
    assert admin.patch(f"/v1/admin/users/{uid}/trial", json={"action": "extend", "note": "x"}).status_code == 400
    rev = admin.patch(f"/v1/admin/users/{uid}/trial", json={"action": "revoke", "note": "CR263 UAT"}).json()
    assert rev["plan"] == "floor_pass" and rev["trial_active"] is False

    start = admin.post(f"/v1/admin/users/{uid}/credits", json={"delta": 10, "note": "CR263 UAT"}).json()["credit_balance"]
    down = admin.post(f"/v1/admin/users/{uid}/credits", json={"delta": -4, "note": "CR263 UAT"}).json()["credit_balance"]
    assert down == start - 4
    floor = admin.post(f"/v1/admin/users/{uid}/credits", json={"delta": -99999, "note": "CR263 UAT"}).json()["credit_balance"]
    assert floor == 0
    assert admin.post(f"/v1/admin/users/{uid}/credits", json={"delta": 0, "note": "x"}).status_code == 400

    assert admin.post(f"/v1/admin/users/{uid}/suspend", json={"note": "CR263 UAT"}).status_code == 200
    assert admin.post(f"/v1/admin/users/{uid}/suspend", json={"note": "CR263 UAT"}).status_code == 409
    assert admin.post(f"/v1/admin/users/{uid}/reinstate", json={"note": "CR263 UAT"}).status_code == 200
    assert admin.post(f"/v1/admin/users/{uid}/reinstate", json={"note": "CR263 UAT"}).status_code == 409

    ev = admin.get(f"/v1/admin/users/{uid}/events", params={"limit": 200}).json()
    types = [e["event_type"] for e in ev["events"]]
    for needed in ("plan_changed", "trial_granted", "trial_extended", "trial_revoked",
                   "credits_added", "credits_deducted", "user_suspended", "user_reinstated"):
        assert needed in types, needed
    assert ev["total"] == len(types)
    assert admin.get(f"/v1/admin/users/{uuid.uuid4()}/events").status_code == 404


@pytest.mark.uat("UAT-ADMIN-005")
def test_suspended_user_is_locked_out(seed, admin):
    u = seed.user()
    assert u.get("/v1/auth/me").status_code == 200
    assert admin.post(f"/v1/admin/users/{u.id}/suspend", json={"note": "CR263 UAT lockout"}).status_code == 200
    try:
        for path in ("/v1/auth/me", f"/v1/mandate/{u.id}"):
            assert u.get(path).status_code in (401, 403), path
    finally:
        assert admin.post(f"/v1/admin/users/{u.id}/reinstate", json={"note": "CR263 UAT lockout"}).status_code == 200
    assert u.get("/v1/auth/me").status_code == 200
