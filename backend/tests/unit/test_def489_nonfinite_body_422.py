"""DEF489: a JSON body containing a non-finite number (`1e999` -> inf) must
return 422, not 500.

FastAPI's default 422 handler echoes each error's `input`; `inf` cannot be
serialised by `JSONResponse`, so the validation failure itself became a 500.
Ordinary validation errors must keep the exact `{"detail": [...]}` body the
mobile client already parses.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import AuthService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _user_and_headers() -> tuple[str, dict]:
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_infinity_in_a_wrongly_typed_field_returns_422_not_500(client: TestClient):
    user_id, headers = _user_and_headers()
    # `threshold_type` is a string field; 1e999 parses to inf and is echoed
    # back in the error's `input`.
    raw = b'{"ticker": "AAPL", "threshold_type": 1e999, "threshold_price": 150.0}'
    r = client.post(f"/v1/price_alerts/{user_id}", content=raw, headers=headers)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail
    entry = next(e for e in detail if e["loc"][-1] == "threshold_type")
    assert entry["input"] == "inf"


def test_negative_infinity_is_stringified_too(client: TestClient):
    user_id, headers = _user_and_headers()
    raw = b'{"ticker": -1e999, "threshold_type": "stop", "threshold_price": 150.0}'
    r = client.post(f"/v1/price_alerts/{user_id}", content=raw, headers=headers)
    assert r.status_code == 422, r.text
    entry = next(e for e in r.json()["detail"] if e["loc"][-1] == "ticker")
    assert entry["input"] == "-inf"


def test_ordinary_validation_error_body_is_unchanged(client: TestClient):
    """Byte-compatible with FastAPI's default handler: only `detail`, and each
    entry exactly what pydantic produced."""
    user_id, headers = _user_and_headers()
    raw = json.dumps({"ticker": "AAPL", "threshold_type": "stop"}).encode()
    r = client.post(f"/v1/price_alerts/{user_id}", content=raw, headers=headers)
    assert r.status_code == 422, r.text
    body = r.json()
    assert list(body) == ["detail"]
    assert body["detail"] == [
        {
            "type": "missing",
            "loc": ["body", "threshold_price"],
            "msg": "Field required",
            "input": {"ticker": "AAPL", "threshold_type": "stop"},
        }
    ]
