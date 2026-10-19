"""UAT area: mandate, risk limits, compliance & Settings (CR263, cases/mandate_settings.yaml).

Live-Alpha. Compliance cases use `/v1/sim/preview` (a dry run: same safety-floor
check as submit, nothing persisted) and one refused `/v1/sim/submit`. No LLM is
spent. Tickers: MO = tobacco (screened out of the Halal universe), XOM = fossil
fuel (Halal-permitted), KO = neutral.
"""

import math
import time
import uuid

import pytest

SEVEN = ["sector_cap_pct", "single_name_cap_pct", "post_loss_cooldown_hours",
         "max_open_positions", "max_trades_per_day", "max_trades_per_week", "max_open_risk_pct"]


@pytest.fixture
def trader(seed):
    return seed.user(plan="trader")


def _mid(u):
    return f"/v1/mandate/{u.id}"


def _patch(u, body):
    r = u.patch(_mid(u), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _get(u):
    r = u.get(_mid(u))
    assert r.status_code == 200, r.text
    return r.json()


def _preview(u, ticker, qty=1):
    r = u.post("/v1/sim/preview", json={"user_id": u.id, "ticker": ticker, "side": "buy", "quantity": qty})
    assert r.status_code == 200, r.text
    return r.json()


def _preset(u):
    return _get(u)["day_trader_preset"]["overrides"]


@pytest.mark.uat("UAT-MAND-001")
def test_default_mandate_with_live_plan_state(trader):
    m = _get(trader)
    assert (m["version"], m["risk_score"], m["max_drawdown_pct"]) == (1, 3, 30)
    c = m["compliance"]
    assert c["long_only"] is True and c["liquid_only"] is True
    for off in ("halal", "esg_lite", "no_tobacco_alcohol_gambling", "no_fossil_fuels", "derivatives_allowed"):
        assert c[off] is False, off
    assert c["ticker_blocklist"] == [] and c["ticker_allowlist"] is None
    assert m["plan"] == "trader"
    assert m["credit_balance"] > 0 and m["credit_balance"] == m["credit_allowance"]
    assert m["room_cost"] is not None and m["credits_reset_at"]
    assert set(SEVEN) <= set(m["resolved"])
    assert all(m["resolved"][k] is not None for k in SEVEN)
    assert set(m["day_trader_preset"]["overrides"]) == set(SEVEN)
    assert m["day_trader_preset"]["disclosure"].strip()
    assert trader.get(_mid(trader) + "/versions").json()["versions"] == []


@pytest.mark.uat("UAT-MAND-002")
def test_mandate_is_private_to_its_owner(api, seed, trader):
    intruder = seed.anon_user()
    mid = _mid(trader)
    before = _get(trader)
    attempts = [
        intruder.get(mid),
        intruder.patch(mid, json={"max_drawdown_pct": 99}),
        intruder.get(mid + "/versions"),
        intruder.get(mid + "/versions/1"),
        intruder.post(mid + "/rollback/1"),
        intruder.get(mid + "/audit"),
    ]
    for r in attempts:
        assert r.status_code == 403, (r.request.url, r.text)
        assert r.json()["detail"] == "access denied"
    assert api.get(mid).status_code == 401
    from client import new_client
    with new_client("garbage") as bad:
        assert bad.get(mid).status_code == 401
    assert trader.get("/v1/mandate/not-a-uuid").status_code == 422
    after = _get(trader)
    assert (after["version"], after["max_drawdown_pct"]) == (before["version"], before["max_drawdown_pct"])


@pytest.mark.uat("UAT-MAND-003")
def test_patch_merges_bumps_version_and_keeps_other_fields(trader):
    # The unsaved default reads as version 1, and the first edit persists as version 1.
    a = _patch(trader, {"max_drawdown_pct": 20})
    assert a["version"] >= 1 and a["max_drawdown_pct"] == 20
    b = _patch(trader, {"compliance": {"halal": True}})
    assert b["version"] == a["version"] + 1
    assert b["compliance"]["halal"] is True
    assert b["compliance"]["long_only"] is True and b["compliance"]["liquid_only"] is True
    before_rc = b["risk_components"]
    c = _patch(trader, {"risk_components": {"concentration_tolerance": 5}})
    assert c["version"] == b["version"] + 1
    assert c["risk_components"]["concentration_tolerance"] == 5
    assert c["risk_components"]["drawdown_response"] == before_rc["drawdown_response"]
    assert c["risk_components"]["regret_asymmetry"] == before_rc["regret_asymmetry"]
    assert c["max_drawdown_pct"] == 20 and c["compliance"]["halal"] is True
    got = _get(trader)
    assert got["version"] == c["version"]
    assert got["risk_components"] == c["risk_components"] and got["compliance"] == c["compliance"]


@pytest.mark.uat("UAT-MAND-004")
def test_invalid_values_rejected_and_mandate_untouched(trader):
    _patch(trader, {"max_drawdown_pct": 25})
    before = _get(trader)
    bad = [{"risk_score": 9}, {"max_drawdown_pct": 0}, {"max_drawdown_pct": 101},
           {"max_drawdown_pct": "abc"}, {"primary_goal": "get_rich"}]
    for body in bad:
        r = trader.patch(_mid(trader), json=body)
        assert r.status_code == 422, (body, r.text)
        assert next(iter(body)) in r.text
    after = _get(trader)
    assert after["version"] == before["version"]
    assert after["max_drawdown_pct"] == 25 and after["risk_score"] == before["risk_score"]


@pytest.mark.uat("UAT-MAND-005")
def test_entitlement_fields_cannot_be_patched(seed, trader):
    before = _get(trader)
    admin_before = seed.detail(trader)
    r = trader.patch(_mid(trader), json={"plan": "floor_manager", "credit_balance": 99999,
                                         "credit_allowance": 99999})
    assert r.status_code == 200, r.text
    after = _get(trader)
    assert after["plan"] == "trader"
    assert after["credit_balance"] == before["credit_balance"]
    assert after["credit_allowance"] == before["credit_allowance"]
    admin_after = seed.detail(trader)
    assert admin_after["plan"] == "trader"
    assert admin_after["credit_balance"] == admin_before["credit_balance"]


@pytest.mark.uat("UAT-MAND-006")
def test_history_newest_first_with_plain_english_summaries(trader):
    _patch(trader, {"max_drawdown_pct": 20})
    _patch(trader, {"risk_score": 4})
    _patch(trader, {"locale": "ar"})
    vs = trader.get(_mid(trader) + "/versions").json()["versions"]
    nums = [v["version"] for v in vs]
    assert nums == sorted(nums, reverse=True) and len(nums) == 3
    assert [v["is_current"] for v in vs].count(True) == 1 and vs[0]["is_current"]
    summaries = {v["version"]: v["change_summary"] for v in vs}
    assert summaries[nums[2]] == "max drawdown 30% → 20%"
    assert summaries[nums[1]] == "risk score 3 → 4"
    assert summaries[nums[0]] == "locale En → Ar"


@pytest.mark.uat("UAT-MAND-007")
def test_historical_version_snapshot(trader):
    first = _patch(trader, {"max_drawdown_pct": 20})["version"]
    _patch(trader, {"max_drawdown_pct": 40})
    snap = trader.get(f"{_mid(trader)}/versions/{first}")
    assert snap.status_code == 200
    assert snap.json()["max_drawdown_pct"] == 20 and snap.json()["version"] == first
    assert _get(trader)["max_drawdown_pct"] == 40
    miss = trader.get(f"{_mid(trader)}/versions/999")
    assert miss.status_code == 404
    assert miss.json()["detail"] == "mandate version 999 not found for this user"


@pytest.mark.uat("UAT-MAND-008")
def test_rollback_restores_values_as_new_version_and_keeps_history(trader):
    a = _patch(trader, {"max_drawdown_pct": 20})["version"]
    b = _patch(trader, {"max_drawdown_pct": 40, "compliance": {"halal": True}})["version"]
    r = trader.post(f"{_mid(trader)}/rollback/{a}")
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["version"] == b + 1
    assert new["max_drawdown_pct"] == 20 and new["compliance"]["halal"] is False
    cur = _get(trader)
    assert cur["version"] == new["version"] and cur["max_drawdown_pct"] == 20
    assert cur["compliance"]["halal"] is False
    vb = trader.get(f"{_mid(trader)}/versions/{b}").json()
    assert vb["max_drawdown_pct"] == 40 and vb["compliance"]["halal"] is True
    assert trader.get(f"{_mid(trader)}/versions/{a}").json()["max_drawdown_pct"] == 20
    hist = trader.get(_mid(trader) + "/versions").json()["versions"]
    assert hist[0]["version"] == new["version"] and hist[0]["is_current"]
    assert hist[0]["change_summary"] == f"Rolled back to v{a}."
    assert [h["version"] for h in hist if h["is_current"]] == [new["version"]]


@pytest.mark.uat("UAT-MAND-009")
def test_rollback_to_unknown_version_404(trader):
    _patch(trader, {"max_drawdown_pct": 20})
    before = _get(trader)
    r = trader.post(f"{_mid(trader)}/rollback/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "mandate version 999 not found for this user"
    assert _get(trader)["version"] == before["version"]


@pytest.mark.uat("UAT-MAND-010")
@pytest.mark.xfail(strict=True, reason=(
    "DEF460 —  GET /v1/mandate/{id}/versions returns the SAME created_at for every version "
    "(MandateStore.upsert copies the first row's created_at onto each new version row), so the "
    "BL5 history cannot say when any edit happened; updated_at is the per-version time. "
    "Observed live 2026-10-19: 9 versions, one identical created_at."))
def test_each_version_has_its_own_timestamp(trader):
    _patch(trader, {"max_drawdown_pct": 20})
    time.sleep(2)
    _patch(trader, {"max_drawdown_pct": 40})
    vs = trader.get(_mid(trader) + "/versions").json()["versions"]
    assert len(vs) == 2
    assert vs[0]["created_at"] > vs[1]["created_at"]


@pytest.mark.uat("UAT-MAND-011")
def test_day_trader_preset_leaves_compliance_alone(trader):
    _patch(trader, {"compliance": {"halal": True}})
    overrides = _preset(trader)
    m = _patch(trader, overrides)
    res = m["resolved"]
    assert res["sector_cap_pct"] == 100 and res["single_name_cap_pct"] == 100
    assert res["post_loss_cooldown_hours"] == 0 and res["max_open_risk_pct"] == 100
    for k in ("max_open_positions", "max_trades_per_day", "max_trades_per_week"):
        assert res[k] == 999999, k
    assert m["compliance"]["halal"] is True
    newest = trader.get(_mid(trader) + "/versions").json()["versions"][0]
    assert newest["change_summary"].startswith("Day Trader preset applied")
    back = _patch(trader, {k: None for k in SEVEN})
    assert back["resolved"]["single_name_cap_pct"] == 3.0
    assert back["resolved"]["sector_cap_pct"] == 40.0
    assert back["resolved"]["max_open_positions"] != 999999


@pytest.mark.uat("UAT-MAND-012")
def test_explicit_limits_override_profile_and_null_returns(trader):
    base = _get(trader)["resolved"]
    m = _patch(trader, {"sector_cap_pct": 25, "single_name_cap_pct": 10,
                        "max_open_positions": 8, "max_trades_per_day": 2})
    assert (m["sector_cap_pct"], m["single_name_cap_pct"], m["max_open_positions"], m["max_trades_per_day"]) \
        == (25, 10, 8, 2)
    assert (m["resolved"]["sector_cap_pct"], m["resolved"]["single_name_cap_pct"],
            m["resolved"]["max_open_positions"], m["resolved"]["max_trades_per_day"]) == (25, 10, 8, 2)
    summary = trader.get(_mid(trader) + "/versions").json()["versions"][0]["change_summary"]
    assert "sector cap following your risk profile → 25%" in summary
    assert "single-name cap following your risk profile → 10%" in summary
    back = _patch(trader, {"sector_cap_pct": None, "single_name_cap_pct": None})
    assert back["resolved"]["sector_cap_pct"] == base["sector_cap_pct"]
    assert back["resolved"]["single_name_cap_pct"] == base["single_name_cap_pct"]


@pytest.mark.uat("UAT-MAND-013")
def test_raised_concentration_limit_changes_safety_floor_outcome(trader):
    probe = _preview(trader, "AAPL", 1)
    notional = probe["notional"]
    assert notional and notional > 0
    qty = max(1, math.ceil(0.06 * 10000 / notional))
    default = _preview(trader, "AAPL", qty)
    assert default["accepted"] is False
    assert default["compliance"]["blocked_by"] == "concentration"
    _patch(trader, _preset(trader))
    relaxed = _preview(trader, "AAPL", qty)
    assert relaxed["compliance"]["blocked_by"] != "concentration"
    assert relaxed["accepted"] is True, relaxed["compliance"]


@pytest.mark.uat("UAT-MAND-014")
def test_halal_blocks_a_non_compliant_ticker(trader):
    assert _preview(trader, "MO")["accepted"] is True
    _patch(trader, {"compliance": {"halal": True}})
    mo = _preview(trader, "MO")
    assert mo["accepted"] is False
    assert mo["compliance"]["blocked_by"] == "compliance"
    assert mo["compliance"]["sharia_verdict"]["status"] == "screened_out"
    assert any("AAOIFI" in v for v in mo["compliance"]["violations"])
    assert _preview(trader, "XOM")["accepted"] is True
    sub = trader.post("/v1/sim/submit", json={"user_id": trader.id, "ticker": "MO", "side": "buy", "quantity": 1})
    assert sub.status_code == 200, sub.text
    assert sub.json()["ok"] is False
    assert sub.json()["compliance"]["blocked_by"] == "compliance"
    pf = trader.get(f"/v1/sim/portfolio/{trader.id}").json()
    assert all(h.get("ticker") != "MO" for h in pf["holdings"])


@pytest.mark.uat("UAT-MAND-015")
def test_halal_still_binds_after_day_trader_preset(trader):
    _patch(trader, {"compliance": {"halal": True}})
    _patch(trader, _preset(trader))
    mo = _preview(trader, "MO")
    assert mo["accepted"] is False
    assert mo["compliance"]["blocked_by"] == "compliance"


@pytest.mark.uat("UAT-MAND-016")
def test_tobacco_and_fossil_filters(trader):
    _patch(trader, {"compliance": {"no_tobacco_alcohol_gambling": True, "no_fossil_fuels": True}})
    mo, xom, ko = _preview(trader, "MO"), _preview(trader, "XOM"), _preview(trader, "KO")
    assert mo["accepted"] is False and mo["compliance"]["blocked_by"] == "compliance"
    assert "tobacco" in " ".join(mo["compliance"]["violations"]).lower()
    assert xom["accepted"] is False and xom["compliance"]["blocked_by"] == "compliance"
    assert "fossil" in " ".join(xom["compliance"]["violations"]).lower()
    assert ko["accepted"] is True, ko["compliance"]


@pytest.mark.uat("UAT-MAND-017")
def test_blocklist_and_allowlist_enforced_and_normalised(trader):
    m = _patch(trader, {"compliance": {"ticker_blocklist": ["xom", "XOM"]}})
    assert m["compliance"]["ticker_blocklist"] == ["XOM"]
    x = _preview(trader, "XOM")
    assert x["accepted"] is False and x["compliance"]["blocked_by"] == "blocklist"
    _patch(trader, {"compliance": {"ticker_blocklist": []}})
    m = _patch(trader, {"compliance": {"ticker_allowlist": ["XOM"]}})
    assert m["compliance"]["ticker_allowlist"] == ["XOM"]
    assert _preview(trader, "XOM")["accepted"] is True
    ko = _preview(trader, "KO")
    assert ko["accepted"] is False and ko["compliance"]["blocked_by"] == "allowlist"
    m = _patch(trader, {"compliance": {"ticker_allowlist": None}})
    assert m["compliance"]["ticker_allowlist"] is None
    assert _preview(trader, "KO")["accepted"] is True


@pytest.mark.uat("UAT-MAND-018")
def test_do_nothing_ticker_rules_are_refused(trader):
    before = _get(trader)["version"]
    unknown = trader.patch(_mid(trader), json={"compliance": {"ticker_blocklist": ["ZZZZNOTREAL"]}})
    assert unknown.status_code == 422 and "ZZZZNOTREAL" in unknown.json()["detail"]
    for empty in ([], [""]):
        r = trader.patch(_mid(trader), json={"compliance": {"ticker_allowlist": empty}})
        assert r.status_code == 422, empty
        assert "send null" in r.json()["detail"]
    not_list = trader.patch(_mid(trader), json={"compliance": {"ticker_blocklist": "TSLA"}})
    assert not_list.status_code == 422
    assert _get(trader)["version"] == before


@pytest.mark.uat("UAT-MAND-019")
def test_identity_and_language_fields_save_with_history(trader):
    _patch(trader, {"display_name": "UAT Tester", "locale": "ms", "timezone": "Asia/Kuala_Lumpur"})
    m = _get(trader)
    assert (m["display_name"], m["locale"], m["timezone"]) == ("UAT Tester", "ms", "Asia/Kuala_Lumpur")
    s = trader.get(_mid(trader) + "/versions").json()["versions"][0]["change_summary"]
    assert "display name Trader → UAT Tester" in s
    assert "locale En → Ms" in s
    assert "timezone Utc → Asia/Kuala_Lumpur" in s


@pytest.mark.uat("UAT-MAND-020")
def test_holdings_audit_against_current_mandate(seed, trader):
    v = _patch(trader, {"max_drawdown_pct": 20})["version"]
    r = trader.get(_mid(trader) + "/audit")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["passed"] is True and a["violations"] == []
    assert a["mandate_version"] == v
    assert a["drawdown_breach"] is False and a["max_open_positions_breach"] is False
    other = seed.anon_user()
    assert other.get(_mid(trader) + "/audit").status_code == 403


@pytest.mark.uat("UAT-MAND-021")
def test_unknown_patch_fields_do_not_change_behaviour(trader):
    before = _get(trader)
    r = trader.patch(_mid(trader), json={"zzz": 1})
    assert r.status_code == 200
    after = _get(trader)
    for k in ("max_drawdown_pct", "risk_score", "compliance", "locale", "primary_goal", "plan", "resolved"):
        assert after[k] == before[k], k
    assert "zzz" not in after
