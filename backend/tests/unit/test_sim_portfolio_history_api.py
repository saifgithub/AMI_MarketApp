"""CR109 slice 1 — GET /v1/sim/portfolio/{user_id}/history.

The wire contract: the stored NAV series, each point carrying its own
`price_source` (CR040 — a mock-priced point must be visible to the client),
plus the chain-linked `twr_pct` for the window.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services.auth_service import AuthService
from app.services.portfolio_nav_daily import run_portfolio_nav_snapshot_tick
from app.services.sim_engine import get_sim_engine


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def test_history_returns_the_stored_series_with_basis_and_twr(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    get_sim_engine().ensure_portfolio(user_id)
    stats = run_portfolio_nav_snapshot_tick(trading_day=lambda: date(2026, 8, 3))
    assert stats["written"] == 1

    r = client.get(
        f"/v1/sim/portfolio/{user_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == str(user_id)
    assert len(body["points"]) == 1
    point = body["points"][0]
    assert point["as_of_date"] == "2026-08-03"
    assert point["nav"] == pytest.approx(10_000.0)
    assert point["cash"] == pytest.approx(10_000.0)
    # `cash`, not `mock`. This portfolio holds nothing — nav == cash — so no
    # price was fetched and none could be simulated. It previously read `mock`
    # because `aggregate_source([])` answers `mock_walk` for an empty ticker
    # list, which is right for the LIVE pill and wrong as a scoring input:
    # `games_scoring_pass` VOIDs any run containing a `mock` day, so every run
    # whose first order queued overnight was void before it began. See
    # test_cr109_empty_book_not_void.py. Do not flip this back to `mock`.
    assert point["price_source"] == "cash"
    assert point["capital_event"] == "open"
    assert body["twr_pct"] is None, "one point — nothing to compound yet"


def test_history_forbids_reading_another_users_portfolio(client: TestClient) -> None:
    _user_id, token = _make_user_and_token()
    other_id, _other_token = _make_user_and_token()

    r = client.get(
        f"/v1/sim/portfolio/{other_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_history_is_empty_before_any_tick_has_run(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    get_sim_engine().ensure_portfolio(user_id)

    r = client.get(
        f"/v1/sim/portfolio/{user_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []
    assert body["twr_pct"] is None
