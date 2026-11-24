"""UAT area: decision journal, trash & the You tab (CR263, cases/journal.yaml)."""

import re
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


def _trader_with_room_to_trade(seed):
    u = seed.user(plan="trader")
    r = u.patch(f"/v1/mandate/{u.id}", json={
        "single_name_cap_pct": 40.0, "sector_cap_pct": 100.0,
        "max_trades_per_day": 100, "max_trades_per_week": 200,
        "max_open_positions": 50, "post_loss_cooldown_hours": 0,
    })
    assert r.status_code == 200, r.text
    return u


def _order(u, ticker, side, quantity):
    return u.post("/v1/sim/submit", json={
        "user_id": u.id, "ticker": ticker, "side": side, "quantity": quantity})


def _trade_entries(u):
    return sorted(_list(u, entry_type="sim_trade")["entries"], key=lambda e: e["created_at"])


@pytest.mark.uat("UAT-JRNL-013")
def test_selling_a_us_position_journals_a_closed_entry(seed):
    u = _trader_with_room_to_trade(seed)
    assert _order(u, "MSFT", "buy", 2).json()["ok"] is True
    sell = _order(u, "MSFT", "sell", 2).json()
    assert sell["ok"] is True, sell
    exit_px = sell["trade"]["entry_price"]

    entries = _trade_entries(u)
    closed = [e for e in entries if "closed" in e["tags"]]
    assert len(closed) == 1, [e["title"] for e in entries]
    e = closed[0]
    assert re.fullmatch(r"Closed MSFT \(MANUAL\) — [+-]\$[\d,]+\.\d\d", e["title"]), e["title"]
    assert e["summary"] == f"Sold 2 at ${exit_px:,.2f}.", e["summary"]
    t = e["payload"]["trade"]
    assert t["status"] == "closed" and abs(t["closed_price"] - exit_px) <= 0.005, t
    lots = u.get(f"/v1/sim/lots/{u.id}/MSFT").json()
    assert abs(t["realised_pnl"] - lots["totals"]["realised_pnl"]) <= 0.02, (t, lots["totals"])
    assert not [x for x in entries if "$-" in x["title"] or "$+" in x["title"]]


@pytest.mark.uat("UAT-JRNL-014")
def test_bursa_fill_is_journaled_in_ringgit_when_the_switch_is_on(seed, bursa_on):
    u = _trader_with_room_to_trade(seed)
    buy = _order(u, "1155.KL", "buy", 100)
    if not bursa_on:
        assert buy.status_code == 422, buy.text
        assert [e for e in _trade_entries(u) if e["ticker"] == "1155.KL"] == []
        return
    assert buy.status_code == 200, buy.text
    res = buy.json()
    entries = [e for e in _trade_entries(u) if e["ticker"] == "1155.KL"]
    if res.get("resting"):
        assert entries == [], "a resting Bursa order must not be journaled before it fills"
        return
    assert res["ok"] is True, res
    assert len(entries) == 1, [e["title"] for e in entries]
    opened = entries[0]
    assert re.fullmatch(r"BUY 100 1155\.KL @ RM[\d,]+\.\d\d", opened["title"]), opened["title"]
    assert "$" not in opened["title"] + opened["summary"], opened

    sell = _order(u, "1155.KL", "sell", 100).json()
    assert sell["ok"] is True, sell
    closed = [e for e in _trade_entries(u) if e["ticker"] == "1155.KL" and "closed" in e["tags"]]
    assert len(closed) == 1
    assert re.fullmatch(
        r"Closed 1155\.KL \(MANUAL\) — [+-]RM[\d,]+\.\d\d", closed[0]["title"],
    ), closed[0]["title"]
    assert closed[0]["summary"].startswith("Sold 100 at RM")
