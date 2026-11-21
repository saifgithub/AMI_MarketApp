"""DEF518: Brief history reports the edit cap from the user's server-side plan.

`GET /v1/brief/history` used to take the plan from a client query param defaulting to
'trial_trader', which the app never sends. So a Floor Pass user's History screen showed
`edits_remaining = null` (unlimited), while `accept()` enforced the Floor Pass cap from
`users.plan` (DEF179). The two must read the same source.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.brief import router as brief_router
from app.db import get_session
from app.db.models import User as UserRow
from app.services.auth_service import AuthService
from app.services.overlay_store import LIFETIME_EDIT_CAP_BY_PLAN
from app.schemas.mandate import Plan


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(brief_router)
    return TestClient(app, raise_server_exceptions=False)


def _user_on(plan: str):
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(UserRow).where(UserRow.id == user.id)).scalar_one()
        row.plan = plan
        s.commit()
    return user.id, {"Authorization": f"Bearer {token}"}


def _remaining(client: TestClient, user_id, headers, **params):
    r = client.get(f"/v1/brief/history/{user_id}/market_analyst", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()["edits_remaining"]


def test_floor_pass_history_shows_the_floor_pass_cap_without_a_plan_param(client):
    user_id, headers = _user_on("floor_pass")
    assert _remaining(client, user_id, headers) == LIFETIME_EDIT_CAP_BY_PLAN[Plan.FLOOR_PASS]


def test_a_client_supplied_plan_cannot_change_the_reported_cap(client):
    user_id, headers = _user_on("floor_pass")
    assert _remaining(client, user_id, headers, plan="floor_manager") == (
        LIFETIME_EDIT_CAP_BY_PLAN[Plan.FLOOR_PASS]
    )


def test_an_uncapped_plan_still_reports_unlimited(client):
    uncapped = [p for p, cap in LIFETIME_EDIT_CAP_BY_PLAN.items() if cap is None]
    if not uncapped:
        pytest.skip("every plan is capped")
    user_id, headers = _user_on(uncapped[0].value)
    assert _remaining(client, user_id, headers) is None
