"""UAT area: onboarding interview & mandate creation (CR263, cases/onboarding.yaml).

The Concierge is deterministic (no LLM), so every case here is free to run.
Sessions are anonymous and in-memory on Alpha; only the restart cases touch a
UAT user's mandate.
"""

import uuid

import pytest

STEPS = ["q1_goal", "q2_horizon", "q3_scenario_drawdown", "q4_scenario_regret",
         "q5_scenario_concentration", "q6_max_drawdown", "q7_constraints"]

DEFAULT_ANSWERS = {
    "q1_goal": "I want to learn to trade",
    "q2_horizon": "5 to 10 years",
    "q3_scenario_drawdown": "I would hold and wait",
    "q4_scenario_regret": "I'd hate missing a rally",
    "q5_scenario_concentration": "I'm comfortable with a few big positions",
    "q6_max_drawdown": "20%",
    "q7_constraints": "halal only, long only",
}


def _start(api, **body):
    r = api.post("/v1/onboarding/start", json=body or {"locale": "en", "timezone": "Asia/Riyadh"})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def _answer(api, sid, step, text):
    return api.post("/v1/onboarding/answer", json={"session_id": sid, "step": step, "answer": text})


def _walk(api, sid, **overrides):
    """Answer all seven questions; returns the final AnswerResponse JSON."""
    answers = {**DEFAULT_ANSWERS, **overrides}
    last = None
    for step in STEPS:
        r = _answer(api, sid, step, answers[step])
        assert r.status_code == 200, f"{step}: {r.status_code} {r.text}"
        last = r.json()
    return last


def _confirm(client, sid, **extra):
    return client.post("/v1/onboarding/readback/confirm",
                       json={"session_id": sid, "confirm": "confirm", **extra})


@pytest.mark.uat("UAT-ONB-001")
def test_start_needs_no_account(api):
    r = api.post("/v1/onboarding/start", json={"locale": "en", "timezone": "Asia/Riyadh"})
    assert r.status_code == 201
    j = r.json()
    assert j["session_id"]
    assert j["welcome_message"]["step"] == "welcome"
    assert j["welcome_message"]["author"] == "concierge"
    assert "Concierge" in j["welcome_message"]["content"]
    assert "12" in j["welcome_message"]["content"]
    assert j["first_question"]["step"] == "q1_goal"
    assert len(j["first_question"]["chips"]) >= 2


@pytest.mark.uat("UAT-ONB-002")
def test_session_can_be_reread(api):
    sid = _start(api, locale="en", timezone="Asia/Riyadh")
    g = api.get(f"/v1/onboarding/{sid}")
    assert g.status_code == 200
    j = g.json()
    assert j["current_step"] == "q1_goal"
    assert j["completed"] is False
    assert j["messages"][0]["step"] == "welcome"
    assert (j["locale"], j["timezone"]) == ("en", "Asia/Riyadh")
    missing = api.get(f"/v1/onboarding/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "session not found or expired"
    assert api.get("/v1/onboarding/xyz").status_code == 422


@pytest.mark.uat("UAT-ONB-003")
def test_seven_questions_walk_to_a_faithful_readback(api):
    sid = _start(api)
    seen = []
    last = None
    for step in STEPS:
        r = _answer(api, sid, step, DEFAULT_ANSWERS[step])
        assert r.status_code == 200, r.text
        last = r.json()
        seen.append(last["next_step"])
        assert last["concierge_reply"]["author"] == "concierge"
    assert seen == STEPS[1:] + ["readback"]
    rb = last["readback_summary"]
    assert rb["primary_goal"] == "learning_to_trade"
    assert rb["max_drawdown_pct"] == 20
    assert rb["compliance"]["halal"] is True
    assert rb["compliance"]["long_only"] is True
    assert 1 <= rb["risk_score"] <= 5
    assert rb["risk_quotes"] == [DEFAULT_ANSWERS[s] for s in STEPS[2:5]]
    text = last["concierge_reply"]["content"]
    assert "Learning To Trade" in text
    assert "20%" in text
    assert "halal" in text.lower()


@pytest.mark.uat("UAT-ONB-004")
def test_unreadable_drawdown_is_reasked_not_defaulted(api):
    sid = _start(api)
    for step in STEPS[:5]:
        assert _answer(api, sid, step, DEFAULT_ANSWERS[step]).status_code == 200
    for junk in ("banana", "$10,000", "0.5%", "150%"):
        r = _answer(api, sid, "q6_max_drawdown", junk)
        assert r.status_code == 200
        assert r.json()["next_step"] == "q6_max_drawdown", junk
        assert "percentage" in r.json()["concierge_reply"]["content"].lower()
        s = api.get(f"/v1/onboarding/{sid}").json()
        assert s["current_step"] == "q6_max_drawdown"
        assert "max_drawdown_pct" not in s["answers"], junk
    ok = _answer(api, sid, "q6_max_drawdown", "20%")
    assert ok.json()["next_step"] == "q7_constraints"
    done = _answer(api, sid, "q7_constraints", "no hard rules").json()
    assert done["readback_summary"]["max_drawdown_pct"] == 20


@pytest.mark.uat("UAT-ONB-005")
@pytest.mark.parametrize("typed,stored", [("45%", 45), ("12.5%", 12), ("no cap", 100)])
def test_free_text_drawdown_is_honoured_exactly(api, typed, stored):
    sid = _start(api)
    final = _walk(api, sid, q6_max_drawdown=typed, q7_constraints="no hard rules")
    assert final["readback_summary"]["max_drawdown_pct"] == stored


@pytest.mark.uat("UAT-ONB-006")
def test_answers_must_match_the_current_question(api):
    sid = _start(api)
    skip = _answer(api, sid, "q6_max_drawdown", "20%")
    assert skip.status_code == 409
    assert "q1_goal" in skip.json()["detail"]
    s = api.get(f"/v1/onboarding/{sid}").json()
    assert s["current_step"] == "q1_goal"
    assert "max_drawdown_pct" not in s["answers"]
    assert _answer(api, sid, "nope", "x").status_code == 422
    assert _answer(api, str(uuid.uuid4()), "q1_goal", "x").status_code == 404


@pytest.mark.uat("UAT-ONB-007")
@pytest.mark.parametrize("text,long_only,liquid_only", [
    ("no hard rules", True, True),
    ("I want to short sometimes", False, True),
    ("long only, though I want to short sometimes", True, True),
])
def test_constraints_never_loosen_defaults_by_omission(api, text, long_only, liquid_only):
    sid = _start(api)
    c = _walk(api, sid, q7_constraints=text)["readback_summary"]["compliance"]
    assert c["long_only"] is long_only
    assert c["liquid_only"] is liquid_only


@pytest.mark.uat("UAT-ONB-008")
def test_confirm_without_account_persists_nothing(api, seed):
    bystander = seed.anon_user()
    before = bystander.get(f"/v1/mandate/{bystander.id}").json()
    sid = _start(api)
    _walk(api, sid)
    for extra in ({}, {"restart": True}):
        r = _confirm(api, sid, **extra)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["completed"] is True
        assert j["final_step"] == "complete"
        assert j["follow_up_message"]["author"] == "concierge"
        assert j["mandate_preview"]["user_id"] == "anonymous-pending-claim"
        assert j["mandate_preview"]["max_drawdown_pct"] == 20
    after = bystander.get(f"/v1/mandate/{bystander.id}").json()
    assert (after["version"], after["max_drawdown_pct"]) == (before["version"], before["max_drawdown_pct"])
    assert bystander.get(f"/v1/mandate/{bystander.id}/versions").json()["versions"] == []


@pytest.mark.uat("UAT-ONB-009")
def test_authenticated_restart_replaces_the_mandate(api, seed):
    u = seed.user(plan="trader")
    default = u.get(f"/v1/mandate/{u.id}").json()
    assert (default["max_drawdown_pct"], default["compliance"]["halal"]) == (30, False)
    sid = _start(api, locale="ar", timezone="Asia/Riyadh")
    final = _walk(api, sid)
    assert final["readback_summary"]["locale"] == "ar"
    r = _confirm(u, sid, restart=True)
    assert r.status_code == 200, r.text
    m = u.get(f"/v1/mandate/{u.id}").json()
    assert m["max_drawdown_pct"] == 20
    assert m["compliance"]["halal"] is True
    assert m["primary_goal"] == "learning_to_trade"
    assert m["locale"] == "ar"
    assert 1 <= m["risk_score"] <= 5
    assert m["plan"] == "trader"
    assert m["credit_balance"] == default["credit_balance"]


@pytest.mark.uat("UAT-ONB-010")
def test_signed_in_confirm_without_restart_leaves_mandate_alone(api, seed):
    u = seed.user(plan="trader")
    patched = u.patch(f"/v1/mandate/{u.id}", json={"max_drawdown_pct": 40}).json()
    sid = _start(api)
    _walk(api, sid, q6_max_drawdown="10%")
    r = _confirm(u, sid)
    assert r.status_code == 200
    after = u.get(f"/v1/mandate/{u.id}").json()
    assert after["max_drawdown_pct"] == 40
    assert after["version"] == patched["version"]


@pytest.mark.uat("UAT-ONB-011")
def test_readback_edit_is_not_implemented_and_harmless(api):
    sid = _start(api)
    _walk(api, sid)
    r = api.post("/v1/onboarding/readback/confirm",
                 json={"session_id": sid, "confirm": "edit", "edits": {"max_drawdown_pct": 10}})
    assert r.status_code == 501
    assert "restart" in r.json()["detail"].lower()
    s = api.get(f"/v1/onboarding/{sid}").json()
    assert s["completed"] is False
    assert s["current_step"] == "readback"
    assert s["answers"]["max_drawdown_pct"] == 20


@pytest.mark.uat("UAT-ONB-012")
def test_confirm_validates_inputs(api):
    missing = api.post("/v1/onboarding/readback/confirm",
                       json={"session_id": str(uuid.uuid4()), "confirm": "confirm"})
    assert missing.status_code == 404
    sid = _start(api)
    bad = api.post("/v1/onboarding/readback/confirm", json={"session_id": sid, "confirm": "maybe"})
    assert bad.status_code == 422


@pytest.mark.uat("UAT-ONB-013")
@pytest.mark.xfail(strict=True, reason=(
    "FINDING: POST /v1/onboarding/readback/confirm on a session with no drawdown answer returns "
    "409 but has already saved completed=True / current_step=complete (api/onboarding.py saves the "
    "session before session_to_mandate_dict raises), so the session can no longer be answered "
    "(every /answer is then 409 'session is on complete'). Live 2026-10-19."))
def test_failed_confirm_does_not_strand_the_session(api):
    sid = _start(api)
    r = _confirm(api, sid)
    assert r.status_code == 409
    assert "max_drawdown" in r.json()["detail"]
    s = api.get(f"/v1/onboarding/{sid}").json()
    assert s["completed"] is False
    assert s["current_step"] == "q1_goal"
    assert _answer(api, sid, "q1_goal", "retirement").status_code == 200
