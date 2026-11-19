"""UAT area: bug reports, AMI help library & telemetry (CR263, cases/support.yaml).

Three real bug reports are filed per run (SUPP-001, SUPP-002, SUPP-014), all prefixed
"[CR263 UAT - ignore]" because they land in the triage queue a monitor reads.
Every other bug-report call is invalid on purpose so it stores nothing. The
per-IP limiter (5/hour) keys on the real socket peer (DEF464 - forwarded headers
are ignored), so the cases that are not about the limit send the admin-secret
exemption header (DEF490) and SUPP-004 reads the Mac's bucket as it finds it.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from client import exempt_headers

UAT_TITLE = "[CR263 UAT - ignore] automated API check"


def _form(**fields) -> dict:
    """Multipart text parts - the shape the iPhone reporter sends."""
    return {k: (None, str(v)) for k, v in fields.items()}


GOOD = dict(category="other", title=UAT_TITLE, app_version="uat", platform="ios")


def _close_out(admin, report_id: str) -> None:
    """Resolve the report at once so /bug-monitor (which reads status='open')
    never files a DEF for it — the nightly would otherwise feed it two a day."""
    r = admin.post(f"/v1/admin/bugs/{report_id}/resolve", json={"note": "CR263 UAT automated check — no action needed."})
    assert r.status_code == 200, r.text


@pytest.mark.uat("UAT-SUPP-001")
def test_signed_in_bug_report(seed):
    u = seed.user(plan="floor_pass")
    r = u.post("/v1/feedback/bug", files=_form(**GOOD, steps="CR263 UAT run, safe to ignore"),
               headers=exempt_headers())
    assert r.status_code == 201, r.text
    body = r.json()
    assert uuid.UUID(body["id"]) and body["status"] == "open" and body["created_at"]
    assert body["attachment_path"] is None
    assert u.get("/v1/feedback/updates").json() == []
    _close_out(seed.admin, body["id"])


@pytest.mark.uat("UAT-SUPP-002")
def test_anonymous_bug_report(api, admin):
    r = api.post("/v1/feedback/bug", files=_form(**{**GOOD, "platform": "android_gms"}),
                 headers=exempt_headers())
    assert r.status_code == 201, r.text
    assert uuid.UUID(r.json()["id"]) and r.json()["status"] == "open"
    _close_out(admin, r.json()["id"])


@pytest.mark.uat("UAT-SUPP-003")
def test_missing_fields_and_bad_attachment_refused(api):
    ip = exempt_headers()
    assert api.post("/v1/feedback/bug", files=_form(title="x"), headers=ip).status_code == 422
    assert api.post("/v1/feedback/bug", files=_form(**{**GOOD, "title": ""}), headers=ip).status_code == 422
    r = api.post("/v1/feedback/bug", files={**_form(**GOOD), "file": ("a.txt", b"hello", "text/plain")},
                 headers=ip)
    assert r.status_code == 415, r.text


@pytest.mark.uat("UAT-SUPP-011")
def test_unknown_category_or_platform_is_a_client_error(api):
    ip = exempt_headers()
    bad_category = api.post("/v1/feedback/bug", files=_form(**{**GOOD, "category": "nonsense"}), headers=ip)
    bad_platform = api.post("/v1/feedback/bug", files=_form(**{**GOOD, "platform": "palm"}), headers=ip)
    assert bad_category.status_code == 422, (bad_category.status_code, bad_category.text)
    assert bad_platform.status_code == 422, (bad_platform.status_code, bad_platform.text)


@pytest.mark.uat("UAT-SUPP-004")
def test_bug_report_rate_limit_is_per_ip(api):
    """Reads the Mac's own bucket in whatever state earlier runs left it: POST
    invalid reports (no exemption header) until the first 429. Per-IP key
    separation is covered by the DEF464 unit tests; here we prove the live
    route enforces the budget and that a spoofed forwarded header is no way out."""
    statuses = []
    for _ in range(6):
        r = api.post("/v1/feedback/bug", files=_form(title="x"))
        statuses.append(r.status_code)
        if r.status_code == 429:
            break
    assert statuses[-1] == 429, statuses
    assert statuses[:-1] == [422] * (len(statuses) - 1), statuses
    assert "rate_limit_exceeded" in r.text, r.text

    spoof = {"X-Forwarded-For": "100.64.7.7", "cf-connecting-ip": "100.64.7.7"}
    again = api.post("/v1/feedback/bug", files=_form(title="x"), headers=spoof)
    assert again.status_code == 429 and "rate_limit_exceeded" in again.text, (again.status_code, again.text)


@pytest.mark.uat("UAT-SUPP-005")
def test_resolution_feed_is_private(seed, api):
    u = seed.user(plan="floor_pass")
    ok = u.get("/v1/feedback/updates")
    assert ok.status_code == 200 and ok.json() == []
    assert api.get("/v1/feedback/updates").status_code == 401
    ghost = uuid.uuid4()
    assert u.post(f"/v1/feedback/{ghost}/ack").status_code == 404
    assert api.post(f"/v1/feedback/{ghost}/ack").status_code == 401


def _events(n=2):
    now = datetime.now(timezone.utc).isoformat()
    return [{"event_id": str(uuid.uuid4()), "event_type": t, "occurred_at": now, "locale": "en", "count": 1}
            for t in ("app_open", "firm_open", "lesson_open")[:n]]


@pytest.fixture(scope="module")
def telemetry_user(seed):
    return seed.user(plan="floor_pass")


@pytest.mark.uat("UAT-SUPP-006")
def test_telemetry_ingest_is_idempotent_and_validated(telemetry_user, api):
    u = telemetry_user
    batch = {"events": _events(2), "user_id": str(uuid.uuid4())}
    first = u.post("/v1/telemetry/events", json=batch)
    assert first.status_code == 200, first.text
    assert first.json() == {"accepted": 2, "duplicates": 0}
    replay = u.post("/v1/telemetry/events", json=batch)
    assert replay.json() == {"accepted": 0, "duplicates": 2}

    bad = _events(1)
    bad[0]["event_type"] = "not_a_real_event"
    r = u.post("/v1/telemetry/events", json={"events": bad})
    assert r.status_code == 422 and "app_open" in r.text
    assert u.post("/v1/telemetry/events", json={"events": []}).status_code == 422
    assert api.post("/v1/telemetry/events", json={"events": _events(1)}).status_code == 401


@pytest.mark.uat("UAT-SUPP-007")
def test_segments_are_admin_only(telemetry_user, admin, api):
    u = telemetry_user
    seed_batch = u.post("/v1/telemetry/events", json={"events": _events(1)})
    assert seed_batch.status_code == 200
    now = datetime.now(timezone.utc)
    window = {"since": (now - timedelta(hours=1)).isoformat(), "until": (now + timedelta(hours=1)).isoformat()}

    for client in (api, u):
        r = client.get("/v1/telemetry/segments", params=window)
        assert r.status_code == 403, r.text
        assert "users" not in r.json()

    ok = admin.get("/v1/telemetry/segments", params=window)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert {"users", "bounce", "convene", "depth", "locales", "dropped_events"} <= set(body)
    assert body["users"] >= 1

    inverted = admin.get("/v1/telemetry/segments",
                         params={"since": window["until"], "until": window["since"]})
    assert inverted.status_code == 422


@pytest.mark.uat("UAT-SUPP-008")
def test_help_library_is_static_and_well_formed(api):
    cats = api.get("/v1/ai_coach/categories")
    assert cats.status_code == 200 and cats.json()
    seen = set()
    first = None
    for cat in cats.json():
        r = api.get(f"/v1/ai_coach/by_category/{cat}")
        assert r.status_code == 200
        body = r.json()
        assert body["items"] and body["total"] == len(body["items"]), cat
        for qa in body["items"]:
            assert qa["id"] not in seen, qa["id"]
            seen.add(qa["id"])
            assert qa["question"].strip() and qa["short_answer"].strip() and qa["long_answer"].strip(), qa["id"]
            first = first or qa

    hit = api.get("/v1/ai_coach/search", params={"q": "stop loss"})
    assert hit.status_code == 200
    hits = hit.json()
    assert hits["total"] == len(hits["hits"]) > 0
    assert any(h["qa"]["id"] == "qa_beg_what_is_stop_loss" for h in hits["hits"])
    assert all(h["score"] > 0 for h in hits["hits"])
    one = api.get(f"/v1/ai_coach/by_id/{hits['hits'][0]['qa']['id']}")
    assert one.status_code == 200 and one.json() == hits["hits"][0]["qa"]

    assert api.get("/v1/ai_coach/search", params={"q": ""}).status_code == 422
    assert api.get("/v1/ai_coach/search", params={"q": "x" * 201}).status_code == 422
    assert api.get("/v1/ai_coach/search", params={"q": "stop", "limit": 0}).status_code == 422
    assert api.get("/v1/ai_coach/by_id/qa_does_not_exist").status_code == 404
    none = api.get("/v1/ai_coach/search", params={"q": "zzqxjwv"})
    assert none.status_code == 200 and none.json()["hits"] == []


@pytest.mark.uat("UAT-SUPP-014")
def test_bug_report_stores_trace_ids_and_refuses_malformed(seed):
    u = seed.user(plan="floor_pass")
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    r = u.post("/v1/feedback/bug", files=_form(**GOOD, trace_ids=",".join(ids)),
               headers=exempt_headers())
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]
    try:
        detail = seed.admin.get(f"/v1/admin/bugs/{report_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["trace_ids"] == ",".join(ids)
    finally:
        _close_out(seed.admin, report_id)

    ip = exempt_headers()
    for bad in ("not-a-uuid", ",".join(str(uuid.uuid4()) for _ in range(6))):
        # Title left empty as well: even if trace_ids validation regressed,
        # nothing could enter the triage queue.
        resp = u.post("/v1/feedback/bug",
                      files=_form(**{**GOOD, "title": "", "trace_ids": bad}), headers=ip)
        assert resp.status_code == 422, resp.text
        assert any("trace_ids" in str(e.get("loc")) for e in resp.json()["detail"]), resp.text
