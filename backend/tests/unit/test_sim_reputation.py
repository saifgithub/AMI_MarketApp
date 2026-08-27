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



def test_a_patched_mandate_reaches_the_submit_path(client: TestClient):
    """DEF321's canary, re-aimed — and the reason it needed re-aiming matters.

    This test was `test_buy_without_stop_or_target_awards_nothing`, and its
    final line asserted `_events(user_id, "trade_disciplined") == []`. CR109
    slice 7 deleted every `reputation_service.award()` call site, so nothing
    can write that event any more and the assertion became **vacuous** — it
    would have passed forever, on any build, proving nothing.

    That mattered more than a normally-dead assertion, because this is the test
    DEF321 tracks. Its intermittent failure was never the reputation line: it
    was `status_code == 200` failing with *"position size 68.8% exceeds
    single-name cap 3.0%"* — the route resolving a DIFFERENT mandate from the
    one patched immediately above, where `3.0` is a risk-tier preset. That
    assertion is still live and is what the run log is counting, so the canary
    is kept and narrowed to exactly it rather than deleted with the awards.
    """
    user_id, token = _make_user_and_token()
    get_mandate_store().patch(user_id, {"single_name_cap_pct": 100.0})
    assert get_mandate_store().get(user_id).single_name_cap_pct == 100.0, (
        "the store did not take the patch — the flake is upstream of the route"
    )
    r = _submit(client, user_id, token, stop=90.0)  # no target
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
