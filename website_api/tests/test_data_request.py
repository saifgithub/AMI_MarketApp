"""Data-request (privacy) intake tests — store + 30-day SLA, validation, rate limit."""

from datetime import datetime, timezone

from app.db.session import get_session
from app.models import DataRequest


def _rows():
    """Materialize rows to plain dicts inside the session (avoid detached access)."""
    with get_session() as s:
        return [
            {
                "request_type": r.request_type,
                "status": r.status,
                "due_at": r.due_at,
            }
            for r in s.query(DataRequest).all()
        ]


def _as_utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_data_request_deletion_stored(client):
    r = client.post(
        "/data-request",
        json={"email": "gone@user.co", "request_type": "deletion", "details": "delete everything"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["request_type"] == "deletion"
    assert rows[0]["status"] == "received"
    # 30-day SLA in the future
    assert _as_utc(rows[0]["due_at"]) > datetime.now(timezone.utc)


def test_data_request_type_normalised(client):
    r = client.post("/data-request", json={"email": "a@b.co", "request_type": "ACCESS"})
    assert r.status_code == 200
    assert _rows()[0]["request_type"] == "access"


def test_data_request_invalid_type(client):
    r = client.post("/data-request", json={"email": "a@b.co", "request_type": "hack"})
    assert r.status_code == 422


def test_data_request_invalid_email(client):
    r = client.post("/data-request", json={"email": "nope", "request_type": "deletion"})
    assert r.status_code == 422


def test_data_request_rate_limited(client):
    body = {"email": "a@b.co", "request_type": "deletion"}
    codes = [client.post("/data-request", json=body).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
