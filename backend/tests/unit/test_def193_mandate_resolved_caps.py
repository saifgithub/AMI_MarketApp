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


# ── CR129 close-out: ALL seven limits are resolved, not just the two caps ───
#
# CR129-BE made every risk limit resolve from `risk_score`, and CR129-MOBILE
# is specified to render "Following your risk profile — <resolved number>".
# It was blocked on exactly this gap: `resolved` carried 2 of the 7. These
# pin the other five, with the same discipline as above — against the SHARED
# functions the safety floor enforces with (risk_limits.py), never against
# re-derived constants.

from app.trading_math.risk_limits import (  # noqa: E402
    resolved_max_open_positions,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_max_trades_per_week,
    resolved_post_loss_cooldown_hours,
)

_CR129_FIELDS = (
    "max_open_positions", "post_loss_cooldown_hours",
    "max_trades_per_day", "max_trades_per_week", "max_open_risk_pct",
)


def test_all_seven_limits_are_resolved_and_never_null(client: TestClient):
    user_id, headers = _new_user()
    body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    for field in _CR129_FIELDS:
        assert body[field] is None, f"raw {field}: no explicit override yet"
        assert body["resolved"][field] is not None, (
            f"resolved.{field} must carry the enforced preset — a null here "
            "is the DEF193 gap again, one field over"
        )


def test_the_five_cr129_limits_match_the_shared_computation(client: TestClient):
    """The safety floor resolves each limit with these exact arguments
    (safety_floor.py:500-590); the GET must go through the same functions so
    the two can never disagree about what is enforced."""
    user_id, headers = _new_user()
    body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    score = body["risk_score"]
    drawdown = body["max_drawdown_pct"]

    resolved = body["resolved"]
    assert resolved["max_open_positions"] == resolved_max_open_positions(score, None)
    assert resolved["post_loss_cooldown_hours"] == pytest.approx(
        resolved_post_loss_cooldown_hours(score, None)
    )
    assert resolved["max_trades_per_day"] == resolved_max_trades_per_day(score, None)
    assert resolved["max_trades_per_week"] == resolved_max_trades_per_week(score, None)
    assert resolved["max_open_risk_pct"] == pytest.approx(
        resolved_max_open_risk_pct(score, drawdown, None)
    )


def test_an_explicit_override_wins_in_the_resolved_view(client: TestClient):
    """Same contract as the sector-cap override test above — and "off stays
    expressible": an explicit cooldown of 0 resolves to 0, never back to the
    preset."""
    user_id, headers = _new_user()
    client.patch(
        f"/v1/mandate/{user_id}",
        json={"max_trades_per_day": 9, "post_loss_cooldown_hours": 0},
        headers=headers,
    )
    body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    assert body["resolved"]["max_trades_per_day"] == 9
    assert body["resolved"]["post_loss_cooldown_hours"] == 0


def test_resolved_open_risk_tracks_the_users_own_drawdown(client: TestClient):
    """`max_open_risk_pct` is a risk-tier FRACTION of the user's own
    `max_drawdown_pct` (risk_limits.py), so the resolved number must move
    when the user moves their drawdown ceiling — stamping it from a constant
    would freeze exactly the per-user half of the derivation."""
    user_id, headers = _new_user()
    before = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    # 10 rather than an arithmetic half: `max_drawdown_pct` is a
    # Literal[10, 20, 30, 50, 100], so anything off the menu 422s and the
    # test would silently measure an unchanged mandate.
    r = client.patch(
        f"/v1/mandate/{user_id}", json={"max_drawdown_pct": 10}, headers=headers,
    )
    assert r.status_code == 200, r.text
    after = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    assert before["max_drawdown_pct"] != 10, "precondition: the ceiling moved"
    assert after["resolved"]["max_open_risk_pct"] == pytest.approx(
        resolved_max_open_risk_pct(after["risk_score"], 10.0, None)
    )
    assert (
        after["resolved"]["max_open_risk_pct"]
        != before["resolved"]["max_open_risk_pct"]
    )
