"""UAT area: Floor tab & home shell (CR263, cases/floor.yaml)."""

import pytest


@pytest.fixture(scope="module")
def pair(seed):
    return seed.user(plan="floor_pass"), seed.user(plan="floor_pass")


@pytest.mark.uat("UAT-FLOOR-001")
def test_sector_watch_empty_state(pair, api):
    a, b = pair
    r = a.get(f"/v1/sector-watch/{a.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "empty"
    assert body["tickers_considered"] == 0
    assert body["sector"] is None and body["leader"] is None and body["headline"] is None
    assert b.get(f"/v1/sector-watch/{a.id}").status_code == 404  # CR183: does not confirm the id exists
    assert api.get(f"/v1/sector-watch/{a.id}").status_code == 401


@pytest.mark.uat("UAT-FLOOR-002")
def test_cold_start_reads_all_succeed(pair):
    u, _ = pair
    journal = u.get(f"/v1/journal/{u.id}")
    assert journal.status_code == 200
    assert journal.json()["entries"] == [] and journal.json()["retention_days"] == 30

    by_lesson = u.get(f"/v1/lessons/progress/{u.id}/by_lesson")
    assert by_lesson.status_code == 200 and by_lesson.json() == []

    reqs = u.get(f"/v1/lessons/requirements/{u.id}")
    assert reqs.status_code == 200
    assert len(reqs.json()) == 12 and not any(r["unlocked"] for r in reqs.json())

    today = u.get("/v1/daily_challenge/today")
    assert today.status_code == 200 and today.json()["my_attempt"] is None

    assert u.get("/v1/messages").json() == []
    assert u.get(f"/v1/notifications/{u.id}/unread_count").json() == {"unread": 0}
    assert u.get(f"/v1/sector-watch/{u.id}").status_code == 200
