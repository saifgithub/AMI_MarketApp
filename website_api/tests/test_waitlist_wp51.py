"""CR267 WP-51 — waitlist profile fields, consent, honeypot and the admin
batch-invite export. sqlite tempfile per test (fixtures in conftest.py)."""

import csv
import io

from sqlalchemy import select

ADMIN = {"X-Admin-Secret": "s3cret-test"}


def _entry(email):
    from app.db.session import get_session
    from app.models import WaitlistEntry

    with get_session() as s:
        row = s.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
        if row is not None:
            s.expunge(row)
        return row


def _admin_on(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "admin_secret", "s3cret-test")


def _signup(client, email, **extra):
    r = client.post("/waitlist", json={"email": email, "consent": True, **extra})
    assert r.json()["ok"] is True


def _export(client):
    r = client.get("/admin/waitlist/export", headers=ADMIN)
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.text)))


# ── public endpoint ───────────────────────────────────────────────────────


def test_signup_stores_profile_and_consent_timestamp(client):
    r = client.post(
        "/waitlist",
        json={"email": "Pat@Example.com", "name": " Pat ", "country": "MY", "platform": "ios", "consent": True},
    )
    assert r.json() == {"ok": True, "new": True}
    row = _entry("pat@example.com")
    assert (row.name, row.country, row.platform) == ("Pat", "MY", "ios")
    assert row.consent_at is not None and row.invited_at is None


def test_bad_email_is_not_stored(client):
    r = client.post("/waitlist", json={"email": "nope", "consent": True})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_missing_consent_is_refused_and_not_stored(client):
    r = client.post("/waitlist", json={"email": "noconsent@example.com"})
    assert r.status_code == 422 and r.json()["detail"] == "consent_required"
    r = client.post("/waitlist", json={"email": "noconsent@example.com", "consent": False})
    assert r.status_code == 422
    assert _entry("noconsent@example.com") is None


def test_honeypot_reports_success_but_stores_nothing(client):
    r = client.post(
        "/waitlist",
        json={"email": "bot@example.com", "consent": True, "website": "http://spam.example"},
    )
    assert r.status_code == 200 and r.json() == {"ok": True, "new": False}
    assert _entry("bot@example.com") is None


def test_unknown_platform_is_rejected(client):
    r = client.post(
        "/waitlist", json={"email": "p@example.com", "consent": True, "platform": "windows"}
    )
    assert r.status_code == 422


def test_blank_optional_fields_become_null(client):
    client.post(
        "/waitlist",
        json={"email": "blank@example.com", "consent": True, "name": "  ", "platform": ""},
    )
    row = _entry("blank@example.com")
    assert row.name is None and row.platform is None


def test_duplicate_is_idempotent_and_keeps_one_row(client, monkeypatch):
    _admin_on(monkeypatch)
    _signup(client, "dup@example.com", name="First")
    r = client.post("/waitlist", json={"email": "DUP@example.com", "consent": True, "name": "Second"})
    assert r.json() == {"ok": True, "new": False}
    assert _entry("dup@example.com").name == "First"
    assert len(_export(client)) == 1


def test_duplicate_backfills_a_legacy_row_without_overwriting(client):
    from app.db.session import get_session
    from app.models import WaitlistEntry

    with get_session() as s:
        s.add(WaitlistEntry(email="old@example.com", name="Original"))
    r = client.post(
        "/waitlist",
        json={"email": "old@example.com", "consent": True, "name": "Changed", "country": "AE"},
    )
    assert r.json() == {"ok": True, "new": False}
    row = _entry("old@example.com")
    assert row.consent_at is not None
    assert row.name == "Original" and row.country == "AE"


def test_rate_limit_returns_429_after_ten(client):
    codes = [
        client.post("/waitlist", json={"email": f"rl{i}@example.com", "consent": True}).status_code
        for i in range(15)
    ]
    assert codes[:10] == [200] * 10 and 429 in codes[10:]


def test_missing_columns_are_added_to_a_pre_existing_table(tmp_path):
    """A live `waitlist` table from before WP-51 must gain the new columns."""
    import os

    from sqlalchemy import create_engine, inspect, text

    import app.db.session as sess

    db = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE waitlist (id CHAR(36) PRIMARY KEY, email VARCHAR NOT NULL, "
            "source VARCHAR, created_at DATETIME NOT NULL, CONSTRAINT uq_waitlist_email UNIQUE (email))"
        ))
    eng.dispose()
    os.environ["WEBSITE_TEST_DATABASE_URL"] = f"sqlite:///{db}"
    sess._engine = None
    sess._SessionLocal = None
    cols = {c["name"] for c in inspect(sess._get_engine()).get_columns("waitlist")}
    assert {"name", "country", "platform", "consent_at", "invited_at", "invite_batch"} <= cols


# ── admin export / mark-invited ───────────────────────────────────────────


def test_admin_requires_the_secret(client, monkeypatch):
    _admin_on(monkeypatch)
    assert client.get("/admin/waitlist/export").status_code == 403
    assert client.get("/admin/waitlist/export", headers={"X-Admin-Secret": "wrong"}).status_code == 403
    assert client.post("/admin/waitlist/mark-invited", json={"ids": []}).status_code == 403


def test_admin_fails_closed_when_secret_unset(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "admin_secret", "")
    assert client.get("/admin/waitlist/export", headers={"X-Admin-Secret": ""}).status_code == 503
    assert client.get("/admin/waitlist/export", headers=ADMIN).status_code == 503


def test_export_lists_uninvited_signups_as_csv(client, monkeypatch):
    _admin_on(monkeypatch)
    _signup(client, "one@example.com", name="One", country="MY", platform="android")
    _signup(client, "two@example.com")
    r = client.get("/admin/waitlist/export", headers=ADMIN)
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert sorted(x["email"] for x in rows) == ["one@example.com", "two@example.com"]
    first = next(x for x in rows if x["email"] == "one@example.com")
    assert first["name"] == "One" and first["platform"] == "android"
    assert first["consent_at"] and first["id"]


def test_export_neutralises_spreadsheet_formulas(client, monkeypatch):
    _admin_on(monkeypatch)
    _signup(client, "f@example.com", name='=HYPERLINK("http://x")')
    assert _export(client)[0]["name"].startswith("'=")


def test_mark_invited_removes_rows_from_the_export(client, monkeypatch):
    _admin_on(monkeypatch)
    _signup(client, "a@example.com")
    _signup(client, "b@example.com")
    id_a = next(x["id"] for x in _export(client) if x["email"] == "a@example.com")

    r = client.post(
        "/admin/waitlist/mark-invited", headers=ADMIN, json={"ids": [id_a], "batch": "wave-1"}
    )
    assert r.json() == {"ok": True, "marked": 1}
    again = client.post(
        "/admin/waitlist/mark-invited", headers=ADMIN, json={"ids": [id_a], "batch": "wave-2"}
    )
    assert again.json()["marked"] == 0, "already-invited rows are not re-stamped"

    assert [x["email"] for x in _export(client)] == ["b@example.com"]
    row = _entry("a@example.com")
    assert row.invite_batch == "wave-1" and row.invited_at is not None


def test_mark_invited_rejects_malformed_ids(client, monkeypatch):
    _admin_on(monkeypatch)
    r = client.post("/admin/waitlist/mark-invited", headers=ADMIN, json={"ids": ["not-a-uuid"]})
    assert r.status_code == 422
