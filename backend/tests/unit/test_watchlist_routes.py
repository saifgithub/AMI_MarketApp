"""Tests for the /v1/watchlist routes' quote enrichment (CR025, AT:R56).

Route-level coverage didn't exist before this CR — `test_watchlist_store.py`
only covers the store. Conftest's `_isolated_db` autouse fixture already pins
`MockWalkProvider` for every test, so no market-data setup is needed here.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.watchlist import router
from app.services.auth_service import AuthService
from app.services.watchlist_store import get_watchlist_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def test_get_watchlist_returns_real_day_change_pct(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    get_watchlist_store().add(user_id, "AAPL")

    r = client.get(
        f"/v1/watchlist/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["price"] is not None
    assert isinstance(items[0]["day_change_pct"], float)
    assert items[0]["price_source"] == "mock_walk"


def test_add_to_watchlist_returns_real_day_change_pct(client: TestClient) -> None:
    user_id, token = _make_user_and_token()

    r = client.post(
        f"/v1/watchlist/{user_id}",
        json={"ticker": "MSFT"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["price"] is not None
    assert isinstance(body["day_change_pct"], float)
    assert body["price_source"] == "mock_walk"
