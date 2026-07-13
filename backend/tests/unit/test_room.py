"""DEF051 regression: Convene the Room must resolve the user's real sim-portfolio
state server-side, never trust a client-suppliable portfolio_value/
current_drawdown_pct override.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import router as room_router
from app.api.room import get_room_runner
from app.db import get_session
from app.db.models import SimPortfolioRow
from app.services.auth_service import AuthService


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(room_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


class _FakeRunner:
    """Records the kwargs stream_room resolves and hands to the runner —
    exactly the surface DEF051 broke — without running a real LLM-backed Room."""

    def __init__(self) -> None:
        self.captured: dict | None = None

    async def start_run(self, **kwargs):
        self.captured = kwargs
        return uuid4()

    def is_active(self, run_id) -> bool:
        return False

    def get_run(self, run_id):
        return None


def test_stream_room_ignores_spoofed_body_uses_real_sim_state(app: FastAPI, client: TestClient):
    """A user with a real, seeded 50% drawdown must have that real state passed
    to the runner — even when the request body lies about it."""
    user_id, token = _new_user()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=uuid4(),
            user_id=user_id,
            name="Main",
            starting_capital=10_000.0,
            current_cash=5_000.0,
        ))

    fake = _FakeRunner()
    app.dependency_overrides[get_room_runner] = lambda: fake
    try:
        r = client.post(
            "/v1/room/stream",
            json={
                "user_id": str(user_id),
                "ticker": "AAPL",
                "locale": "en",
                "portfolio_value": 999_999.0,
                "current_drawdown_pct": 0.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert fake.captured is not None
    assert fake.captured["portfolio_value"] == 5_000.0
    assert fake.captured["current_drawdown_pct"] == 50.0


def test_stream_room_fresh_user_gets_real_starting_capital(app: FastAPI, client: TestClient):
    """A brand-new user with no seeded portfolio needs no special-cased
    fallback — SimEngine.ensure_portfolio() already auto-creates one at the
    real starting capital ($10k, not the old fake $100k default)."""
    user_id, token = _new_user()

    fake = _FakeRunner()
    app.dependency_overrides[get_room_runner] = lambda: fake
    try:
        r = client.post(
            "/v1/room/stream",
            json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert fake.captured is not None
    assert fake.captured["portfolio_value"] == 10_000.0
    assert fake.captured["current_drawdown_pct"] == 0.0
