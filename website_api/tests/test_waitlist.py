"""Waitlist endpoint tests — sqlite tempfile, no Postgres required."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _sqlite_db(tmp_path):
    db_file = tmp_path / "test_website.db"
    os.environ["WEBSITE_TEST_DATABASE_URL"] = f"sqlite:///{db_file}"
    # Reset engine so the fixture URL is picked up
    import app.db.session as sess
    sess._engine = None
    sess._SessionLocal = None
    yield
    sess._engine = None
    sess._SessionLocal = None
    del os.environ["WEBSITE_TEST_DATABASE_URL"]


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_join_waitlist_new(client):
    r = client.post("/waitlist", json={"email": "test@example.com", "source": "marketing_site"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "new": True}


def test_join_waitlist_duplicate(client):
    client.post("/waitlist", json={"email": "dupe@example.com"})
    r = client.post("/waitlist", json={"email": "dupe@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "new": False}


def test_join_waitlist_invalid_email(client):
    r = client.post("/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_join_waitlist_normalises_email(client):
    client.post("/waitlist", json={"email": "  User@Example.COM  "})
    # Second POST with normalised form should be a duplicate, not a new entry
    r = client.post("/waitlist", json={"email": "user@example.com"})
    assert r.json() == {"ok": True, "new": False}
