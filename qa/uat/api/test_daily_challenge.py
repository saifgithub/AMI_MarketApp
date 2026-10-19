"""UAT area: daily challenge & reminder (CR263, cases/daily_challenge.yaml)."""

import pytest

GIVEAWAYS = {"answer", "explanation"}


def _today(client):
    r = client.get("/v1/daily_challenge/today")
    assert r.status_code == 200, r.text
    return r.json()


def _attempt(u, cid, option):
    return u.post(f"/v1/daily_challenge/{cid}/attempt", json={"selected_option": option})


def _challenge_entries(u):
    r = u.get(f"/v1/journal/{u.id}")
    assert r.status_code == 200
    return [e for e in r.json()["entries"] if e["entry_type"] == "daily_challenge"]


@pytest.mark.uat("UAT-DAILY-001")
def test_today_hides_the_answer(api):
    body = _today(api)
    ch = body["challenge"]
    assert body["date"] and ch["id"] and ch["scenario"] and ch["question"]
    assert len(ch["options"]) >= 2
    assert not GIVEAWAYS & set(ch)
    assert body["my_attempt"] is None

    by_id = api.get(f"/v1/daily_challenge/by_id/{ch['id']}")
    assert by_id.status_code == 200 and not GIVEAWAYS & set(by_id.json())
    by_date = api.get(f"/v1/daily_challenge/by_date/{body['date']}")
    assert by_date.status_code == 200 and not GIVEAWAYS & set(by_date.json()["challenge"])
    everything = api.get("/v1/daily_challenge/all")
    assert everything.status_code == 200
    items = everything.json()["items"]
    assert items and everything.json()["total"] == len(items)
    assert all(not GIVEAWAYS & set(i) for i in items)

    assert api.get("/v1/daily_challenge/by_date/not-a-date").status_code == 400
    assert api.get("/v1/daily_challenge/by_id/dc_does_not_exist").status_code == 404


@pytest.mark.uat("UAT-DAILY-002")
def test_attempt_recorded_once(seed):
    u = seed.user(plan="floor_pass")
    cid = _today(u)["challenge"]["id"]
    first = _attempt(u, cid, 0)
    assert first.status_code == 200, first.text
    f = first.json()
    assert f["already_attempted"] is False and f["selected_option"] == 0
    assert f["explanation"] and isinstance(f["correct"], bool)
    assert f["correct"] == (f["correct_option"] == 0)

    second = _attempt(u, cid, 1)
    assert second.status_code == 200
    s = second.json()
    assert s["already_attempted"] is True
    assert s["selected_option"] == 0
    assert s["correct"] == f["correct"] and s["correct_option"] == f["correct_option"]

    mine = _today(u)["my_attempt"]
    assert mine["selected_option"] == 0 and mine["correct"] == f["correct"]
    assert mine["correct_option"] == f["correct_option"] and mine["explanation"]
    assert len(_challenge_entries(u)) == 1


@pytest.mark.uat("UAT-DAILY-003")
def test_wrong_answer_recorded_and_bad_attempts_refused(seed, api):
    probe = seed.user(plan="floor_pass")
    ch = _today(probe)["challenge"]
    cid, n = ch["id"], len(ch["options"])
    correct_option = _attempt(probe, cid, 0).json()["correct_option"]

    u = seed.user(plan="floor_pass")
    wrong = (correct_option + 1) % n
    r = _attempt(u, cid, wrong)
    assert r.status_code == 200
    assert r.json()["correct"] is False and r.json()["correct_option"] == correct_option
    entries = _challenge_entries(u)
    assert len(entries) == 1
    assert "wrong" in entries[0]["tags"] and entries[0]["outcome"] == "loss"
    assert entries[0]["payload"]["correct"] is False

    fresh = seed.user(plan="floor_pass")
    assert _attempt(fresh, cid, n).status_code == 400
    assert _attempt(fresh, "dc_does_not_exist", 0).status_code == 404
    assert api.post(f"/v1/daily_challenge/{cid}/attempt", json={"selected_option": 0}).status_code == 401
    assert _today(fresh)["my_attempt"] is None
    assert _challenge_entries(fresh) == []


@pytest.mark.uat("UAT-DAILY-004")
def test_reminder_preference(seed, api):
    u = seed.user(plan="floor_pass")
    r = u.put("/v1/daily_challenge/reminder",
              json={"daily_reminder_hour": 9, "timezone": "Asia/Kuala_Lumpur"})
    assert r.status_code == 200 and r.json() == {"daily_reminder_hour": 9, "timezone": "Asia/Kuala_Lumpur"}

    r = u.put("/v1/daily_challenge/reminder", json={"timezone": "Asia/Riyadh"})
    assert r.json() == {"daily_reminder_hour": 9, "timezone": "Asia/Riyadh"}

    r = u.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": None})
    assert r.json() == {"daily_reminder_hour": None, "timezone": "Asia/Riyadh"}

    assert u.put("/v1/daily_challenge/reminder", json={"timezone": "Mars/Olympus"}).status_code == 400
    assert u.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": 24}).status_code == 422
    assert api.put("/v1/daily_challenge/reminder", json={"daily_reminder_hour": 9}).status_code == 401
