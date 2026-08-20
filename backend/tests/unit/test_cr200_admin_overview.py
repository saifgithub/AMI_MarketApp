"""CR200 — /v1/admin/overview: every block present, per-block degradation.

The contract under test: a failing dependency turns into an {"error": …}
block INSIDE a 200 payload — the endpoint never 500s over a probe, and one
dead block never blanks the others (CR040 degrade-loudly).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_overview
from app.api.admin_overview import router as overview_router
from app.core.config import settings

_SECRET = "test-admin-secret-abc123"
_HDR = {"Authorization": f"Bearer {_SECRET}"}

_BLOCKS = (
    "ready", "build", "llm", "llm_cache", "release_floor",
    "market_data", "bugs", "config",
)


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(overview_router)
    return TestClient(app, raise_server_exceptions=False)


def test_all_blocks_present(client: TestClient) -> None:
    r = client.get("/v1/admin/overview", headers=_HDR)
    assert r.status_code == 200
    data = r.json()
    for block in _BLOCKS:
        assert block in data, f"missing block {block}"
    assert data["build"]["env"] == settings.env
    assert "open" in data["bugs"]
    assert data["config"]["settings_total"] > 0


def test_failing_probe_degrades_to_error_block(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> dict:
        raise RuntimeError("redis on fire")

    monkeypatch.setattr(admin_overview, "_ready_block", boom)
    r = client.get("/v1/admin/overview", headers=_HDR)
    assert r.status_code == 200
    data = r.json()
    assert "redis on fire" in data["ready"]["error"]
    # The other blocks are unaffected.
    assert "error" not in data["build"]
    assert "open" in data["bugs"]


def test_requires_admin(client: TestClient) -> None:
    assert client.get("/v1/admin/overview").status_code == 403
