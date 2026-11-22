"""DEF367 — close the Brief propose + rollback wire surfaces (AT:B1).

`backend/scripts/wire_contract/verify.py` calls a route -> Dart-model surface
UNVERIFIED when no test drives it through a `TestClient` and gets a real 2xx
JSON body (conftest's wire-capture hook records it). These tests drive the real
Brief flow end to end so the capture holds one `BriefProposal` and one
`UserOverlay` to compare against the keys `api_client.dart` reads:

  POST /v1/brief/propose   -> BriefProposal
  POST /v1/brief/rollback  -> UserOverlay

Test-only: no product code changes. The engine's mock-proposal branch (no real
LLM provider in the unit suite) produces the proposal deterministically.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.brief import router as brief_router
from app.services.auth_service import AuthService
from app.services.overlay_store import get_overlay_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(brief_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _brief_to_accepted(client: TestClient, user_id, headers, text: str) -> dict:
    started = client.post(
        "/v1/brief/start",
        json={"agent_id": "bear_researcher", "user_id": str(user_id)},
        headers=headers,
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["session"]["id"]

    proposed = client.post(
        "/v1/brief/propose",
        json={
            "session_id": session_id,
            "history": [{"role": "user", "content": text}],
        },
        headers=headers,
    )
    assert proposed.status_code == 200, proposed.text
    proposal = proposed.json()

    accepted = client.post(
        "/v1/brief/accept",
        json={"session_id": session_id, "proposal_id": proposal["id"]},
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["ok"] is True
    return proposal


def test_propose_returns_a_proposal_the_client_can_parse(client: TestClient) -> None:
    get_overlay_store().clear()
    user_id, headers = _new_user()

    proposal = _brief_to_accepted(client, user_id, headers, "Weigh liquidity more.")

    assert proposal["refused"] is False
    for key in ("id", "session_id", "plain_english", "overlay_addition",
                "full_overlay_preview"):
        assert key in proposal, key
    assert "Weigh liquidity more." in proposal["overlay_addition"]


def test_rollback_returns_the_restored_overlay(client: TestClient) -> None:
    get_overlay_store().clear()
    user_id, headers = _new_user()
    _brief_to_accepted(client, user_id, headers, "First briefing note.")
    _brief_to_accepted(client, user_id, headers, "Second briefing note.")

    r = client.post(
        "/v1/brief/rollback",
        json={"user_id": str(user_id), "agent_id": "bear_researcher", "to_version": 1},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    overlay = r.json()
    assert overlay["version"] == 1
    for key in ("id", "user_id", "agent_id", "content", "plain_english",
                "created_at"):
        assert key in overlay, key
