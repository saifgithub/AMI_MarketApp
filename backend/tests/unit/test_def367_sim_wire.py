"""DEF367 — close the resting-order wire surfaces on /v1/sim (AT:B1).

`backend/scripts/wire_contract/verify.py` calls a route -> Dart-model surface
UNVERIFIED when no test drives it through a `TestClient` and gets a real 2xx
JSON body that carries the shape the client parses. The suite already hit
`POST /v1/sim/submit` 20 times, but only ever on the market-fill branch, so the
`resting: true` branch (the only one that emits `order`) was never observed.

  POST /v1/sim/submit                              -> SimSubmitResult (resting)
  GET  /v1/sim/orders/$userId                      -> SimRestingOrder
  POST /v1/sim/orders/$userId/$orderId/cancel      -> RestingOrderCancelResult
  POST /v1/sim/trades/$userId/close                -> SimTrade (under `trade`)

`SimSubmitResult` reads `short` on the sell-to-open branch as well, so a short
is opened through the route too (borrow rate pinned off the network).

Test-only: no product code changes. The limit is $1, which rests against any
real or mock mark, so the order is resting by construction.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services.auth_service import AuthService
from app.services.mandate_store import get_mandate_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _rest_a_buy_limit(client: TestClient, user_id, headers) -> dict:
    r = client.post(
        "/v1/sim/submit",
        json={
            "user_id": str(user_id),
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 2,
            "order_type": "limit",
            "limit_price": 1.0,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_submit_limit_returns_the_resting_branch(client: TestClient) -> None:
    user_id, headers = _new_user()

    body = _rest_a_buy_limit(client, user_id, headers)

    assert body["ok"] is True, body["compliance"]
    assert body["resting"] is True
    assert body["trade"] is None
    assert body["order"]["id"]
    assert body["order"]["ticker"] == "AAPL"
    assert body["order"]["state"] == "working"
    assert "passed" in body["compliance"]


def test_orders_list_carries_the_resting_order(client: TestClient) -> None:
    user_id, headers = _new_user()
    placed = _rest_a_buy_limit(client, user_id, headers)["order"]

    r = client.get(f"/v1/sim/orders/{user_id}", headers=headers)

    assert r.status_code == 200, r.text
    orders = r.json()["orders"]
    assert [o["id"] for o in orders] == [placed["id"]]
    for key in ("id", "ticker", "side", "quantity", "order_type", "state"):
        assert key in orders[0], key


def test_cancel_returns_the_servers_verdict(client: TestClient) -> None:
    user_id, headers = _new_user()
    placed = _rest_a_buy_limit(client, user_id, headers)["order"]

    r = client.post(
        f"/v1/sim/orders/{user_id}/{placed['id']}/cancel", headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cancelled"] is True
    assert body["state"] == "cancelled"
    assert body["order"]["id"] == placed["id"]


def test_manual_close_returns_the_closed_trade_under_trade(client: TestClient) -> None:
    user_id, headers = _new_user()
    # The default risk-tier single-name cap (3%) is below one AAPL share on a
    # $10k book; this test is about the response shape, not the cap.
    get_mandate_store().patch(user_id, {"single_name_cap_pct": 100.0})
    opened = client.post(
        "/v1/sim/submit",
        json={"user_id": str(user_id), "ticker": "AAPL", "side": "buy", "quantity": 1},
        headers=headers,
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["ok"] is True, opened.json()["compliance"]["violations"]
    trade_id = opened.json()["trade"]["id"]

    r = client.post(
        f"/v1/sim/trades/{user_id}/close", json={"trade_id": trade_id}, headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["trade"]["id"] == trade_id
    assert body["trade"]["realised_pnl"] is not None
    assert "lot_close" in body["trade"] and body["trade"]["lot_close"] is None  # DEF552


def test_submit_sell_to_open_returns_the_short_branch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.short_borrow_rate._fetch_info", lambda ticker: {},
    )
    user_id, headers = _new_user()
    get_mandate_store().patch(user_id, {
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "compliance": {"long_only": False},
    })

    r = client.post(
        "/v1/sim/submit",
        json={"user_id": str(user_id), "ticker": "AAPL", "side": "sell", "quantity": 2},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, body["compliance"]["violations"]
    assert body["resting"] is False
    assert body["trade"] is None
    assert body["short"]["action"] == "short_open"
    assert body["short"]["ticker"] == "AAPL"
    assert body["short"]["quantity"] == 2
