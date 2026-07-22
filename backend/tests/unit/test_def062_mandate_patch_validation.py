"""DEF062 guard: PATCH /v1/mandate/{user_id} must reject out-of-schema updates.

`MandateStore.patch()` used to merge `updates` via `current.model_copy(update=updates)`,
which Pydantic v2 explicitly does not validate — an out-of-range `max_drawdown_pct`
(declared `Literal[10, 20, 30, 50, 100]`) or `risk_score` (declared 1-5) would persist
silently and then feed the safety floor's deterministic compliance math uncorrupted-looking
but wrong. This must now raise instead of persisting.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from uuid import uuid4

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.services.auth_service import AuthService
from app.services.mandate_store import MandateStore


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def test_patch_endpoint_returns_422_for_out_of_range_max_drawdown_pct(client: TestClient):
    user_id, headers = _new_user()
    resp = client.patch(f"/v1/mandate/{user_id}", json={"max_drawdown_pct": 999}, headers=headers)
    assert resp.status_code == 422


def test_patch_rejects_out_of_range_max_drawdown_pct():
    store = MandateStore()
    user_id = uuid4()
    with pytest.raises(ValidationError):
        store.patch(user_id, {"max_drawdown_pct": 999})
    # must not have persisted the corrupt value
    assert store.get_or_default(user_id).max_drawdown_pct != 999


def test_patch_rejects_out_of_range_risk_score():
    store = MandateStore()
    user_id = uuid4()
    with pytest.raises(ValidationError):
        store.patch(user_id, {"risk_score": 99})
    assert store.get_or_default(user_id).risk_score != 99


def test_patch_still_accepts_valid_updates():
    store = MandateStore()
    user_id = uuid4()
    updated = store.patch(user_id, {"max_drawdown_pct": 20, "risk_score": 4})
    assert updated.max_drawdown_pct == 20
    assert updated.risk_score == 4
