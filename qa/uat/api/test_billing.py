"""UAT area: billing, plans, credits (CR263, cases/billing.yaml).

The webhook positive path uses the real RevenueCat secret from the git-ignored
infra/alpha.env, only ever against users this suite seeded. The secret is never
printed or asserted into a message.
"""

import uuid

import pytest

from client import _read_env_file, _secrets_root, env

WEBHOOK = "/v1/webhooks/revenuecat"


def _secret() -> str:
    s = env("REVENUECAT_WEBHOOK_SECRET") or _read_env_file(
        _secrets_root() / "infra" / "alpha.env", "REVENUECAT_WEBHOOK_SECRET")
    if not s:
        pytest.fail("no REVENUECAT_WEBHOOK_SECRET (infra/alpha.env) — webhook cases cannot run")
    return s


def _event(run_id, user_id, etype, *, product="trader_monthly", entitlement="trader", **extra):
    ev = {
        "id": f"uat-{run_id}-{uuid.uuid4()}",
        "type": etype,
        "app_user_id": str(user_id),
        "product_id": product,
        "environment": "SANDBOX",
    }
    if entitlement:
        ev["entitlement_ids"] = [entitlement]
    ev.update(extra)
    return {"event": ev}


def _post(api, payload, secret):
    headers = {} if secret is None else {"Authorization": secret}
    return api.post(WEBHOOK, json=payload, headers=headers)


def _snap(seed, u):
    d = seed.detail(u)
    return d["plan"], d["credit_balance"], len(d["recent_events"])


@pytest.mark.uat("UAT-BILL-001")
def test_billing_identity(api, seed):
    assert api.get("/v1/billing/identity").status_code == 401
    u = seed.user()
    r = u.get("/v1/billing/identity")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == u.id
    assert body["app_user_id"] == u.id


@pytest.mark.uat("UAT-BILL-002")
def test_webhook_fails_closed(api, seed, run_id):
    u = seed.user()
    before = _snap(seed, u)
    real = _secret()
    sub = _event(run_id, u.id, "INITIAL_PURCHASE")
    pack = _event(run_id, u.id, "NON_RENEWING_PURCHASE", product="credits_standard", entitlement=None)
    attempts = [None, "", "wrong-secret", f"Bearer {real}", real[:-1], real + "x"]
    for payload in (sub, pack):
        for secret in attempts:
            r = _post(api, payload, secret)
            assert r.status_code in (401, 503), f"secret={'<none>' if secret is None else '<set>'} -> {r.status_code}"
            assert r.status_code != 200
    assert _snap(seed, u) == before


@pytest.mark.uat("UAT-BILL-003")
def test_webhook_subscription_grant_and_replay(api, seed, run_id):
    u = seed.user()
    real = _secret()
    ev = _event(run_id, u.id, "INITIAL_PURCHASE")
    r = _post(api, ev, real)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    d = seed.detail(u)
    assert d["plan"] == "trader"
    assert d["credit_balance"] == 150

    again = _post(api, ev, real)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    d2 = seed.detail(u)
    assert (d2["plan"], d2["credit_balance"]) == ("trader", 150)

    up = _post(api, _event(run_id, u.id, "PRODUCT_CHANGE", product="floor_manager_monthly",
                           entitlement="floor_manager"), real)
    assert up.status_code == 200 and up.json()["status"] == "ok"
    d3 = seed.detail(u)
    assert d3["plan"] == "floor_manager"
    assert d3["credit_balance"] == 500
    rc = [e for e in d3["recent_events"] if e["event_type"] == "plan_changed" and e.get("source") == "revenuecat"]
    assert len(rc) == 2


@pytest.mark.uat("UAT-BILL-004")
def test_webhook_expiration_drops_to_floor_pass(api, seed, run_id):
    u = seed.user()
    real = _secret()
    assert _post(api, _event(run_id, u.id, "INITIAL_PURCHASE"), real).status_code == 200
    assert seed.detail(u)["plan"] == "trader"
    r = _post(api, _event(run_id, u.id, "EXPIRATION"), real)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    m = u.get(f"/v1/mandate/{u.id}").json()
    assert m["plan"] == "floor_pass"
    assert m["credit_allowance"] == 13
    assert 0 <= m["credit_balance"] <= 13
    d = seed.detail(u)
    assert d["plan"] == "floor_pass"
    assert d["credit_balance"] >= 0


@pytest.mark.uat("UAT-BILL-005")
def test_webhook_packs_and_loud_refusals(api, seed, run_id):
    u = seed.user()
    real = _secret()
    # A brand-new user's first allowance is granted lazily on the first balance read.
    base = u.get(f"/v1/mandate/{u.id}").json()["credit_balance"]
    assert base == 13

    r = _post(api, _event(run_id, u.id, "NON_RENEWING_PURCHASE", product="credits_starter", entitlement=None), real)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert seed.detail(u)["credit_balance"] == base + 60
    kinds = [e["event_type"] for e in seed.detail(u)["recent_events"]]
    assert "credits_added" in kinds
    settled = _snap(seed, u)

    bad_pack = _post(api, _event(run_id, u.id, "NON_RENEWING_PURCHASE", product="credits_bogus", entitlement=None), real)
    assert bad_pack.status_code == 422
    no_map = _post(api, _event(run_id, u.id, "INITIAL_PURCHASE", product="mystery_sku", entitlement="mystery"), real)
    assert no_map.status_code == 422
    ghost = _post(api, _event(run_id, uuid.uuid4(), "INITIAL_PURCHASE"), real)
    assert ghost.status_code == 404
    assert _snap(seed, u) == settled

    test_ev = _post(api, {"event": {"id": f"uat-{run_id}-{uuid.uuid4()}", "type": "TEST"}}, real)
    assert test_ev.status_code == 200 and test_ev.json()["status"] == "ignored"
    assert _post(api, {"nope": 1}, real).status_code == 400
    assert _snap(seed, u) == settled


@pytest.mark.uat("UAT-BILL-006")
def test_plan_matrix(seed, admin):
    expected = {
        "floor_pass": ("floor_pass", 13, 8),
        "trader": ("trader", 150, 8),
        "floor_manager": ("floor_manager", 500, 25),
    }
    for plan, (eff, allowance, room_cost) in expected.items():
        u = seed.user(plan=plan)
        m = u.get(f"/v1/mandate/{u.id}").json()
        d = seed.detail(u)
        assert m["plan"] == eff, plan
        assert m["credit_allowance"] == allowance, plan
        assert m["room_cost"] == room_cost, plan
        assert m["credit_balance"] >= 0
        assert d["credit_balance"] == m["credit_balance"], plan
        assert d["effective_plan"] == eff

    t = seed.user(plan="floor_pass")
    r = admin.post(f"/v1/admin/users/{t.id}/trial", json={"days": 7, "note": "CR263 UAT trial"})
    assert r.status_code == 200
    m = t.get(f"/v1/mandate/{t.id}").json()
    assert m["plan"] == "trial_trader"
    assert m["credit_allowance"] == 150
    assert m["room_cost"] == 8
    assert m["trial_expires_at"]
    assert seed.detail(t)["trial_active"] is True

    bare = seed.user(plan="trial_trader")
    mb = bare.get(f"/v1/mandate/{bare.id}").json()
    assert mb["plan"] == "floor_pass"
    assert mb["credit_allowance"] == 13
    assert seed.detail(bare)["effective_plan"] == "floor_pass"


@pytest.mark.uat("UAT-BILL-007")
def test_credits_never_negative(seed, admin):
    u = seed.user(plan="floor_pass")
    r = admin.post(f"/v1/admin/users/{u.id}/credits", json={"delta": -100000, "note": "CR263 UAT clamp"})
    assert r.status_code == 200
    assert r.json()["credit_balance"] == 0
    assert seed.detail(u)["credit_balance"] == 0
    m = u.get(f"/v1/mandate/{u.id}").json()
    assert m["credit_balance"] >= 0
    assert admin.post(f"/v1/admin/users/{u.id}/credits", json={"delta": 0, "note": "CR263 UAT"}).status_code == 400
