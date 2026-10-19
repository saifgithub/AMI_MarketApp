"""UAT area: decision journal, trash & the You tab (CR263, cases/journal.yaml)."""

import uuid

import pytest

LESSON = "281_what_is_a_market"


def _pass_lesson(u, lesson_id=LESSON):
    wrong = u.post("/v1/lessons/quiz", json={"user_id": u.id, "lesson_id": lesson_id, "answers": []})
    assert wrong.status_code == 200
    key = [q["correct_index"] for q in wrong.json()["per_question"]]
    ok = u.post("/v1/lessons/quiz", json={"user_id": u.id, "lesson_id": lesson_id, "answers": key})
    assert ok.status_code == 200 and ok.json()["passed"] is True


def _list(u, **params):
    r = u.get(f"/v1/journal/{u.id}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _lesson_entry(u):
    entries = [e for e in _list(u)["entries"] if e["entry_type"] == "lesson_complete"]
    assert len(entries) == 1, entries
    return entries[0]


@pytest.mark.uat("UAT-JRNL-001")
def test_retention_window_follows_plan(seed):
    u = seed.user(plan="floor_pass")
    _pass_lesson(u)
    fp = _list(u)
    assert fp["retention_days"] == 30
    assert fp["total"] == len(fp["entries"]) >= 1

    seed.set_plan(u, "trader")
    tr = _list(u)
    assert tr["retention_days"] is None
    assert tr["total"] == len(tr["entries"]) >= 1
    assert {e["id"] for e in fp["entries"]} <= {e["id"] for e in tr["entries"]}


@pytest.mark.uat("UAT-JRNL-002")
def test_lesson_completion_is_journalled(seed):
    u = seed.user(plan="floor_pass")
    _pass_lesson(u)
    entry = _lesson_entry(u)
    assert entry["deleted_at"] is None
    assert entry["payload"]["score"] == 1.0
    assert "lesson" in entry["tags"]
    title = entry["title"]
    assert title.startswith("Completed lesson")

    typed = _list(u, entry_type="lesson_complete")
    assert [e["id"] for e in typed["entries"]] == [entry["id"]]
    assert _list(u, entry_type="room_run")["entries"] == []
    needle = title.split("—", 1)[-1].strip().split()[0]
    assert entry["id"] in [e["id"] for e in _list(u, q=needle)["entries"]]

    one = u.get(f"/v1/journal/{u.id}/entry/{entry['id']}")
    assert one.status_code == 200 and one.json()["id"] == entry["id"]
    assert u.get(f"/v1/journal/{u.id}/entry/{uuid.uuid4()}").status_code == 404


@pytest.mark.uat("UAT-JRNL-003")
def test_note_tags_outcome_persist(seed):
    u = seed.user(plan="floor_pass")
    _pass_lesson(u)
    entry = _lesson_entry(u)
    path = f"/v1/journal/{u.id}/entry/{entry['id']}"
    r = u.post(f"{path}/note", json={"note": "UAT note", "tags": ["uat", "review"], "outcome": "win"})
    assert r.status_code == 200
    for got in (r.json(), u.get(path).json(), _lesson_entry(u)):
        assert got["user_note"] == "UAT note"
        assert set(got["tags"]) >= {"uat", "review"} or got["tags"] == ["uat", "review"]
        assert got["outcome"] == "win"
    assert u.post(f"/v1/journal/{u.id}/entry/{uuid.uuid4()}/note", json={"note": "x"}).status_code == 404


@pytest.mark.uat("UAT-JRNL-004")
def test_delete_trash_restore_round_trip(seed):
    u = seed.user(plan="trader")
    _pass_lesson(u)
    entry = _lesson_entry(u)
    eid = entry["id"]
    path = f"/v1/journal/{u.id}/entry/{eid}"

    assert u.delete(path).status_code == 204
    assert eid not in [e["id"] for e in _list(u)["entries"]]
    trash = u.get(f"/v1/journal/{u.id}/trash")
    assert trash.status_code == 200 and trash.json()["retention_days"] is None
    gone = [e for e in trash.json()["entries"] if e["id"] == eid]
    assert len(gone) == 1 and gone[0]["deleted_at"]

    assert u.post(f"{path}/restore").status_code == 204
    back = [e for e in _list(u)["entries"] if e["id"] == eid]
    assert len(back) == 1 and back[0]["deleted_at"] is None
    assert eid not in [e["id"] for e in u.get(f"/v1/journal/{u.id}/trash").json()["entries"]]

    ghost = f"/v1/journal/{u.id}/entry/{uuid.uuid4()}"
    assert u.delete(ghost).status_code == 404
    assert u.post(f"{ghost}/restore").status_code == 404


@pytest.mark.uat("UAT-JRNL-005")
def test_journal_is_owner_only_and_unforgeable(seed, api):
    a = seed.user(plan="floor_pass")
    b = seed.user(plan="floor_pass")
    _pass_lesson(a)
    eid = _lesson_entry(a)["id"]
    base = f"/v1/journal/{a.id}"
    assert b.get(base).status_code == 403
    assert b.get(f"{base}/trash").status_code == 403
    assert b.get(f"{base}/entry/{eid}").status_code == 403
    assert b.post(f"{base}/entry/{eid}/note", json={"note": "hijack"}).status_code == 403
    assert b.delete(f"{base}/entry/{eid}").status_code == 403
    assert b.post(f"{base}/entry/{eid}/restore").status_code == 403
    assert api.get(base).status_code == 401
    kept = _lesson_entry(a)
    assert kept["user_note"] is None and kept["deleted_at"] is None

    forged = {"user_id": a.id, "entry_type": "lesson_complete", "title": "forged"}
    r = b.post("/v1/journal", json=forged)
    assert r.status_code in (404, 405), r.text
    assert _list(b)["entries"] == []
