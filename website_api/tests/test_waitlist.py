"""Waitlist endpoint tests — sqlite tempfile (fixtures in conftest.py)."""


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
    r = client.post("/waitlist", json={"email": "user@example.com"})
    assert r.json() == {"ok": True, "new": False}
