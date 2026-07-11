"""DEF048 (AT:R54) — /v1/onboarding/readback/confirm edit-path regression.

The edit branch used to apply + persist edits to session.answers before
raising 501, so a client told "this failed" had actually already had its
session mutated. Covers that the session is left untouched on the 501.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.onboarding import router
from app.schemas.onboarding import ConversationStep, OnboardingSession
from app.services.session_store import get_session_store


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_readback_edit_returns_501_without_mutating_session(client: TestClient) -> None:
    session = OnboardingSession(
        current_step=ConversationStep.READBACK,
        answers={"goal": "growth"},
    )
    await get_session_store().create(session)

    resp = client.post(
        "/v1/onboarding/readback/confirm",
        json={
            "session_id": str(session.id),
            "confirm": "edit",
            "edits": {"goal": "capital_preservation"},
        },
    )

    assert resp.status_code == 501
    stored = await get_session_store().get(session.id)
    assert stored is not None
    assert stored.answers == {"goal": "growth"}
    assert stored.completed is False
