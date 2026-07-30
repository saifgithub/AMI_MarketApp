"""DEF177 (security review C2) — /v1/llm/translate and /v1/llm/status must
reject an unauthenticated caller.

Live-confirmed 2026-07-30: `/status` returned 200 and `/translate` returned
422 (schema error, not 401) from the open internet with no Cloudflare
Access in front of api-alpha — an anonymous, unrate-limited proxy onto
the live LLM gateway. Both routes are operator tooling (only
scripts/translate_arb.py calls them; no mobile caller) and are now gated
behind the same static ADMIN_SECRET bearer as /v1/admin/*.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.llm import router as llm_router
from app.core.config import settings


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(llm_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_status_rejects_missing_admin_secret(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "admin_secret", "sekrit")
    r = client.get("/v1/llm/status")
    assert r.status_code == 403


def test_status_rejects_wrong_admin_secret(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "admin_secret", "sekrit")
    r = client.get("/v1/llm/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


def test_translate_rejects_missing_admin_secret(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "admin_secret", "sekrit")
    r = client.post(
        "/v1/llm/translate",
        json={"system_prompt": "x", "user_message": "y"},
    )
    assert r.status_code == 403


def test_llm_router_503s_when_admin_secret_unset(monkeypatch, client: TestClient):
    """Loudly refuses rather than failing open when ADMIN_SECRET is unset."""
    monkeypatch.setattr(settings, "admin_secret", "")
    r = client.get("/v1/llm/status")
    assert r.status_code == 503


def test_status_accepts_correct_admin_secret(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "admin_secret", "sekrit")
    with patch("app.api.llm.get_llm_gateway") as mock_gw:
        mock_gw.return_value.status.return_value = {"active_provider": "mock"}
        r = client.get(
            "/v1/llm/status", headers={"Authorization": "Bearer sekrit"},
        )
    assert r.status_code == 200


def test_translate_accepts_correct_admin_secret(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "admin_secret", "sekrit")

    async def _fake_stream(*args, **kwargs):
        yield "hola"

    with patch("app.api.llm.get_llm_gateway") as mock_gw:
        mock_gw.return_value.stream_chat = _fake_stream
        mock_gw.return_value.status.return_value = {"active_provider": "mock"}
        r = client.post(
            "/v1/llm/translate",
            json={"system_prompt": "translate", "user_message": "hello"},
            headers={"Authorization": "Bearer sekrit"},
        )
    assert r.status_code == 200
    assert r.json()["text"] == "hola"
