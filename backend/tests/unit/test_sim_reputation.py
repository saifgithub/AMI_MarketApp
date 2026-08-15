"""CR004 — sim route reputation hooks: reset cooldown + disciplined-trade award.

The reset route gets a 24h cooldown (portfolio created_at IS the last-reset
time); a buy submitted with stop AND target that clears the mandate check
awards `trade_disciplined` once per trade.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.sim import router as sim_router
from app.db import get_session
from app.db.models import ReputationEventRow, SimPortfolioRow
from app.services.auth_service import AuthService
from app.services.mandate_store import get_mandate_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _submit(client, user_id, token, **overrides):
    body = {
        "user_id": str(user_id),
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
    }
    body.update(overrides)
    return client.post(
        "/v1/sim/submit", json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


def _events(user_id, event_type):
    with get_session() as s:
        return s.execute(
            select(ReputationEventRow).where(
                ReputationEventRow.user_id == user_id,
                ReputationEventRow.event_type == event_type,
            )
        ).scalars().all()


def test_reset_within_24h_of_portfolio_creation_returns_429(client: TestClient):
    user_id, token = _make_user_and_token()
    # Any portfolio access creates it fresh → created_at ≈ now.
    r = client.get(
        f"/v1/sim/portfolio/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    r = client.post(
        f"/v1/sim/portfolio/{user_id}/reset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 429
    assert r.json()["detail"] == "reset_cooldown"
    assert int(r.headers["Retry-After"]) > 0


def test_reset_after_cooldown_succeeds(client: TestClient):
    user_id, token = _make_user_and_token()
    client.get(
        f"/v1/sim/portfolio/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with get_session() as s:
        row = s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
        ).scalar_one()
        row.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
    r = client.post(
        f"/v1/sim/portfolio/{user_id}/reset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text


def test_disciplined_buy_awards_points_once(client: TestClient):
    user_id, token = _make_user_and_token()
    # CR129/DEF187: a fresh anonymous mandate's single-name cap now resolves
    # to the risk-tier preset (3.0% at the default risk_score=3), not the
    # pre-CR129 flat 50% backstop — 1 share of AAPL against a $10k default
    # portfolio is ~3-4% and would be rejected on concentration, not the
    # disciplined-trade behaviour this test actually exercises. Pin it
    # permissive, same fix as test_sim_engine.py's non-concentration tests.
    get_mandate_store().patch(user_id, {"single_name_cap_pct": 100.0})
    # DEF312: `target=200.0` was BELOW the mock walk's AAPL (measured $273.77),
    # so this fixture had been buying with a target already through the market —
    # `bracket_hit` would have booked it as a win on the next sweep. It passed
    # only because nothing checked the bracket's side and this test never calls
    # `evaluate_outcomes`. Pinned wide rather than to a number, so the walk
    # drifting cannot silently invert it again.
    r = _submit(client, user_id, token, stop=1.0, target=100_000.0)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    events = _events(user_id, "trade_disciplined")
    assert len(events) == 1
    assert events[0].points == 2


def test_buy_without_stop_or_target_awards_nothing(client: TestClient):
    user_id, token = _make_user_and_token()
    get_mandate_store().patch(user_id, {"single_name_cap_pct": 100.0})
    r = _submit(client, user_id, token, stop=90.0)  # no target
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert _events(user_id, "trade_disciplined") == []
