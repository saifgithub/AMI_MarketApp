"""DEF193 guard: the mandate GET stamps the RESOLVED (enforced) value for each
preset-backed cap, and it must agree with `GET /v1/portfolio/sector-allocation`'s
`max_allowed` — the whole point of the defect (two endpoints disagreeing about
whether a preset-backed cap is knowable).

`sector_cap_pct` / `single_name_cap_pct` are `None` until a user explicitly
overrides them, but a real, binding preset still applies underneath
(`app.trading_math.sizing.resolved_sector_cap_pct` /
`resolved_single_name_cap_pct` — the one place each cap is computed, CR046).
Before this fix, `GET /v1/mandate/{id}` echoed the raw (possibly-null) stored
value; the client had to choose between fabricating a number or hiding one.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.dependencies import get_current_user
from app.api.mandate import router as mandate_router
from app.api.portfolio import get_sector_map, router as portfolio_router
from app.services.auth_service import AuthService
from app.services.sector_allocation import SectorMap
from app.services.sim_engine import SimEngine, get_sim_engine
from app.trading_math.sizing import (
    resolved_sector_cap_pct,
    resolved_single_name_cap_pct,
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    app.include_router(portfolio_router)
    app.dependency_overrides[get_sim_engine] = lambda: SimEngine()
    app.dependency_overrides[get_sector_map] = lambda: SectorMap(mapping={})
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def test_mandate_get_carries_resolved_sub_object_never_null(client: TestClient):
    user_id, headers = _new_user()
    resp = client.get(f"/v1/mandate/{user_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sector_cap_pct"] is None  # no explicit override — the DEF193 gap
    assert body["single_name_cap_pct"] is None
    resolved = body["resolved"]
    assert resolved is not None
    assert resolved["sector_cap_pct"] is not None
    assert resolved["single_name_cap_pct"] is not None


def test_resolved_sector_cap_matches_default_risk_tier_preset(client: TestClient):
    user_id, headers = _new_user()
    resp = client.get(f"/v1/mandate/{user_id}", headers=headers)
    body = resp.json()
    # default concentration_tolerance=3 -> 40.0 percentage points (DEFAULT_CONCENTRATION_TOLERANCE_CAPS)
    assert body["resolved"]["sector_cap_pct"] == pytest.approx(40.0)
    # default risk_score=3 -> 3.0% (DEFAULT_RISK_TIER_CAPS)
    assert body["resolved"]["single_name_cap_pct"] == pytest.approx(3.0)


def test_resolved_sector_cap_pct_matches_portfolio_endpoint_max_allowed(client: TestClient):
    """The shared assertion that IS the fix: `GET /v1/mandate` and
    `GET /v1/portfolio/sector-allocation` must report the SAME number for the
    same user, just in each field's own units (percentage points vs a 0-1
    fraction)."""
    user_id, headers = _new_user()
    mandate_body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    portfolio_body = client.get(
        f"/v1/portfolio/sector-allocation/{user_id}", headers=headers,
    ).json()

    resolved_pct = mandate_body["resolved"]["sector_cap_pct"]
    max_allowed_fraction = portfolio_body["compliance"]["max_allowed"]
    assert resolved_pct == pytest.approx(max_allowed_fraction * 100.0)


def test_resolved_sector_cap_pct_honours_explicit_override_and_still_matches_portfolio(
    client: TestClient,
):
    user_id, headers = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"sector_cap_pct": 55.0}, headers=headers)

    mandate_body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    assert mandate_body["sector_cap_pct"] == 55.0
    assert mandate_body["resolved"]["sector_cap_pct"] == pytest.approx(55.0)

    portfolio_body = client.get(
        f"/v1/portfolio/sector-allocation/{user_id}", headers=headers,
    ).json()
    assert portfolio_body["compliance"]["max_allowed"] == pytest.approx(0.55)


def test_resolved_single_name_cap_pct_matches_the_shared_computation(client: TestClient):
    """No second live endpoint serves the single-name cap directly, so this
    pins the mandate response against the SAME shared function
    (`app.trading_math.sizing.resolved_single_name_cap_pct`) that
    `safety_floor.single_name_cap_pct` also calls — the one place this number
    is computed, per CR046."""
    user_id, headers = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"risk_score": 5}, headers=headers)
    body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()

    expected = resolved_single_name_cap_pct(5, None)
    assert body["resolved"]["single_name_cap_pct"] == pytest.approx(expected)


def test_resolved_values_never_computed_client_side_hard_coded(client: TestClient):
    """CR046 guard: the resolved figures must move when the SERVER-SIDE preset
    table would move them (via `risk_score`/`concentration_tolerance`), not
    stay pinned to a hard-coded constant."""
    user_id, headers = _new_user()
    before = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    client.patch(
        f"/v1/mandate/{user_id}",
        json={
            "risk_score": 1,
            "risk_components": {
                "drawdown_response": 1, "regret_asymmetry": -1, "concentration_tolerance": 1,
            },
        },
        headers=headers,
    )
    after = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    assert after["resolved"]["sector_cap_pct"] != before["resolved"]["sector_cap_pct"]
    assert after["resolved"]["single_name_cap_pct"] != before["resolved"]["single_name_cap_pct"]
    assert after["resolved"]["sector_cap_pct"] == pytest.approx(
        resolved_sector_cap_pct(1, None)
    )
    assert after["resolved"]["single_name_cap_pct"] == pytest.approx(
        resolved_single_name_cap_pct(1, None)
    )
