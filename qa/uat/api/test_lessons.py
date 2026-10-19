"""UAT area: lessons, quizzes, Agent Academy unlocks & glossary (CR263, cases/lessons.yaml)."""

import uuid

import pytest

GATEWAY_AGENT = "fundamentals_analyst"


def _quiz(u, lesson_id, answers):
    r = u.post("/v1/lessons/quiz", json={"user_id": u.id, "lesson_id": lesson_id, "answers": answers})
    assert r.status_code == 200, r.text
    return r.json()


def _answer_key(u, lesson_id):
    """Submitting no answers grades every question wrong and reveals the key."""
    first = _quiz(u, lesson_id, [])
    assert first["passed"] is False
    return [q["correct_index"] for q in first["per_question"]], first


def _pass(u, lesson_id):
    key, _ = _answer_key(u, lesson_id)
    res = _quiz(u, lesson_id, key)
    assert res["passed"] is True, res
    return res


def _by_lesson(u):
    r = u.get(f"/v1/lessons/progress/{u.id}/by_lesson")
    assert r.status_code == 200
    return {s["lesson_id"]: s for s in r.json()}


def _journal(u):
    r = u.get(f"/v1/journal/{u.id}")
    assert r.status_code == 200
    return r.json()["entries"]


@pytest.mark.uat("UAT-LESS-001")
def test_catalogue_anonymous_and_consistent(api):
    r = api.get("/v1/lessons")
    assert r.status_code == 200
    cat = r.json()
    lessons = [l for t in cat["tracks"] for l in t["lessons"]]
    assert cat["total_lessons"] == len(lessons) >= 100
    ids = [l["id"] for l in lessons]
    assert len(ids) == len(set(ids))
    for l in lessons:
        assert l["title"] and l["track"] and l["code"], l
    assert "foundations" in {t["track"] for t in cat["tracks"]}


@pytest.mark.uat("UAT-LESS-002")
def test_lesson_body_has_no_answer_key(api):
    r = api.get("/v1/lessons/280_what_is_a_stock")
    assert r.status_code == 200
    assert "answer_index" not in r.text
    body = r.json()
    assert body["meta"]["id"] == "280_what_is_a_stock"
    assert any(b["kind"] == "markdown" and b["markdown"] for b in body["blocks"])
    assert body["quizzes"] and all(q["options"] for q in body["quizzes"])
    for locale in ("ar", "ms", "zz"):
        rl = api.get("/v1/lessons/280_what_is_a_stock", params={"locale": locale})
        assert rl.status_code == 200, (locale, rl.text)
        assert rl.json()["meta"]["id"] == "280_what_is_a_stock"
        assert "answer_index" not in rl.text
    assert api.get("/v1/lessons/does_not_exist").status_code == 404


@pytest.mark.uat("UAT-LESS-003")
def test_start_lesson_records_progress(seed):
    u = seed.user(plan="floor_pass")
    p = u.get(f"/v1/lessons/progress/{u.id}").json()
    assert p["lessons_completed"] == 0 and p["lessons_total"] > 0
    assert p["agents_unlocked"] == []
    assert _by_lesson(u) == {}
    r = u.post("/v1/lessons/start", json={"user_id": u.id, "lesson_id": "281_what_is_a_market"})
    assert r.status_code == 200
    st = _by_lesson(u)["281_what_is_a_market"]
    assert st["started_at"] and st["quiz_attempts"] == 0 and st["quiz_passed"] is False
    bad = u.post("/v1/lessons/start", json={"user_id": u.id, "lesson_id": "does_not_exist"})
    assert bad.status_code == 404


@pytest.mark.uat("UAT-LESS-004")
def test_wrong_and_partial_answers_never_pass(seed):
    u = seed.user(plan="floor_pass")
    lesson_id = "281_what_is_a_market"
    quiz = u.get(f"/v1/lessons/{lesson_id}").json()["quizzes"]
    assert len(quiz) >= 2, "partial-answer check needs a multi-question quiz"
    key, first = _answer_key(u, lesson_id)
    assert first["score"] < 1.0 and first["unlocked_agents"] == []
    assert all(q["explanation"] is not None for q in first["per_question"])

    partial = list(key)
    partial[0] = (key[0] + 1) % len(quiz[0]["options"])
    res = _quiz(u, lesson_id, partial)
    assert res["passed"] is False and 0.0 < res["score"] < 1.0
    assert res["unlocked_agents"] == []

    st = _by_lesson(u)[lesson_id]
    assert st["quiz_attempts"] == 2 and st["quiz_passed"] is False and st["completed_at"] is None
    assert u.get(f"/v1/lessons/progress/{u.id}").json()["lessons_completed"] == 0
    assert u.get(f"/v1/lessons/activations/{u.id}").json() == []
    assert not [e for e in _journal(u) if e["entry_type"] == "lesson_complete"]

    ok = _quiz(u, lesson_id, key)
    assert ok["passed"] is True and ok["score"] == 1.0
    st = _by_lesson(u)[lesson_id]
    assert st["quiz_attempts"] == 3 and st["quiz_passed"] is True and st["completed_at"]
    assert [e for e in _journal(u) if e["entry_type"] == "lesson_complete"]


@pytest.mark.uat("UAT-LESS-005")
def test_five_gateways_unlock_agent_on_floor_pass(seed):
    u = seed.user(plan="floor_pass")
    assert u.plan == "floor_pass"

    def req():
        rows = u.get(f"/v1/lessons/requirements/{u.id}").json()
        return next(r for r in rows if r["agent_id"] == GATEWAY_AGENT)

    gates = [g["lesson_id"] for g in req()["required"]]
    assert len(gates) == 5

    for lesson_id in gates[:4]:
        assert _pass(u, lesson_id)["unlocked_agents"] == []
    r4 = req()
    assert r4["unlocked"] is False and r4["passed_count"] == 4 and r4["remaining_count"] == 1
    assert u.get(f"/v1/lessons/activations/{u.id}").json() == []

    last = gates[4]
    _key, failed = _answer_key(u, last)
    assert failed["passed"] is False and failed["unlocked_agents"] == []
    assert req()["unlocked"] is False
    assert u.get(f"/v1/lessons/activations/{u.id}").json() == []

    done = _quiz(u, last, _key)
    assert done["passed"] is True
    assert done["unlocked_agents"] == [GATEWAY_AGENT]

    acts = u.get(f"/v1/lessons/activations/{u.id}").json()
    assert [a["agent_id"] for a in acts] == [GATEWAY_AGENT]
    assert acts[0]["activation_method"] == "earn_path"
    assert acts[0]["triggering_lesson_id"] == last
    r5 = req()
    assert r5["unlocked"] is True and r5["remaining_count"] == 0
    assert u.get(f"/v1/lessons/progress/{u.id}").json()["agents_unlocked"] == [GATEWAY_AGENT]
    assert [e for e in _journal(u) if e["entry_type"] == "agent_unlock"]

    again = _quiz(u, last, _key)
    assert again["passed"] is True and again["unlocked_agents"] == []
    assert len(u.get(f"/v1/lessons/activations/{u.id}").json()) == 1


@pytest.mark.uat("UAT-LESS-006")
def test_every_agent_has_five_gateways_and_starts_locked(seed):
    u = seed.user(plan="floor_pass")
    rows = u.get(f"/v1/lessons/requirements/{u.id}").json()
    assert len(rows) == 12
    assert len({r["agent_id"] for r in rows}) == 12
    for r in rows:
        assert r["unlocked"] is False
        assert len(r["required"]) == 5, r["agent_id"]
        assert r["passed_count"] == 0 and r["remaining_count"] == 5
        assert all(g["title"] and g["code"] for g in r["required"])


@pytest.mark.uat("UAT-LESS-007")
def test_progress_routes_are_owner_only(seed, api):
    a = seed.user(plan="floor_pass")
    b = seed.user(plan="floor_pass")
    for path in ("", "/by_lesson"):
        assert b.get(f"/v1/lessons/progress/{a.id}{path}").status_code == 403
        assert api.get(f"/v1/lessons/progress/{a.id}{path}").status_code == 401
    assert b.get(f"/v1/lessons/requirements/{a.id}").status_code == 403
    assert b.get(f"/v1/lessons/activations/{a.id}").status_code == 403
    assert api.get(f"/v1/lessons/requirements/{a.id}").status_code == 401
    assert api.get(f"/v1/lessons/activations/{a.id}").status_code == 401
    body = {"user_id": a.id, "lesson_id": "281_what_is_a_market"}
    assert b.post("/v1/lessons/start", json=body).status_code == 403
    assert b.post("/v1/lessons/quiz", json={**body, "answers": []}).status_code == 403
    assert api.post("/v1/lessons/start", json=body).status_code == 401
    assert _by_lesson(a) == {}
    grant = b.post("/v1/lessons/activations/grant",
                   json={"user_id": b.id, "agent_id": GATEWAY_AGENT, "method": "founder_grant"})
    assert grant.status_code in (404, 405)
    assert b.get(f"/v1/lessons/activations/{b.id}").json() == []


@pytest.mark.uat("UAT-LESS-008")
def test_glossary_catalogue_and_terms(api):
    first_entry = None
    for locale in ("en", "ar", "ms"):
        r = api.get(f"/v1/glossary/{locale}")
        assert r.status_code == 200, (locale, r.text)
        cat = r.json()
        entries = [e for c in cat["categories"] for e in c["entries"]]
        assert entries and cat["total_terms"] == len(entries)
        assert len({e["id"] for e in entries}) == len(entries)
        for e in entries:
            assert e["term"].strip() and e["definition"].strip() and e["category"].strip(), e["id"]
        if locale == "en":
            first_entry = entries[0]
    one = api.get(f"/v1/glossary/en/{first_entry['id']}")
    assert one.status_code == 200 and one.json() == first_entry
    assert api.get("/v1/glossary/en/not_a_real_term_xyz").status_code == 404
