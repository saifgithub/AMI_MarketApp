"""Tests for the /v1/price_alerts routes (CR027 §4)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.price_alerts import router
from app.services.auth_service import AuthService
from app.services.price_alert_store import get_price_alert_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_price_alert(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "aapl", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["status"] == "active"


def test_create_rejects_unknown_ticker(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "ZZZNOTREAL", "threshold_type": "stop", "threshold_price": 1.0},
        headers=_auth(token),
    )
    assert r.status_code == 422, r.text


def test_list_price_alerts(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "AAPL", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(token),
    )
    r = client.get(f"/v1/price_alerts/{user_id}", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["ticker"] == "AAPL"


def test_list_price_alerts_filtered_by_status(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    created = client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "AAPL", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(token),
    ).json()
    client.delete(f"/v1/price_alerts/{user_id}/{created['id']}", headers=_auth(token))

    active = client.get(f"/v1/price_alerts/{user_id}?status=active", headers=_auth(token)).json()
    cancelled = client.get(f"/v1/price_alerts/{user_id}?status=cancelled", headers=_auth(token)).json()
    assert active["total"] == 0
    assert cancelled["total"] == 1


def test_cancel_price_alert(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    created = client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "AAPL", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(token),
    ).json()
    r = client.delete(f"/v1/price_alerts/{user_id}/{created['id']}", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_cancel_unknown_alert_is_404(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.delete(
        f"/v1/price_alerts/{user_id}/00000000-0000-0000-0000-000000000000",
        headers=_auth(token),
    )
    assert r.status_code == 404


def test_cancel_already_cancelled_alert_is_409(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    created = client.post(
        f"/v1/price_alerts/{user_id}",
        json={"ticker": "AAPL", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(token),
    ).json()
    client.delete(f"/v1/price_alerts/{user_id}/{created['id']}", headers=_auth(token))
    r = client.delete(f"/v1/price_alerts/{user_id}/{created['id']}", headers=_auth(token))
    assert r.status_code == 409, r.text


def test_cannot_access_another_users_price_alerts(client: TestClient) -> None:
    owner_id, owner_token = _make_user_and_token()
    _other_id, other_token = _make_user_and_token()
    get_price_alert_store()  # ensure schema initialised
    client.post(
        f"/v1/price_alerts/{owner_id}",
        json={"ticker": "AAPL", "threshold_type": "stop", "threshold_price": 150.0},
        headers=_auth(owner_token),
    )
    r = client.get(f"/v1/price_alerts/{owner_id}", headers=_auth(other_token))
    assert r.status_code == 403
