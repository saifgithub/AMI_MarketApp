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


# ──────────────────────────────────────────────────────────────────────────
# DEF428 round 2, MINOR-1 — `submit_answer` used to forward `req.step`
# straight to `process_answer` with no check against `session.current_step`,
# so a client could post a step ahead of the session's own (e.g. skipping
# Q6 straight to Q7). `max_drawdown_pct` would then be absent, and
# `_build_readback_summary`'s `.get("max_drawdown_pct", 30)` fabricated a
# 30% mandate that looked like a real answer. The shipped mobile client
# always posts the session's own current step, so this guards a
# misbehaving/adversarial client rather than normal use.
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_answer_rejects_a_step_ahead_of_the_sessions_current_step(
    client: TestClient,
) -> None:
    """A client stuck on Q6 posting Q7's step must get a clear 4xx, not have
    the session silently advanced with no drawdown answer recorded."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
    await get_session_store().create(session)

    resp = client.post(
        "/v1/onboarding/answer",
        json={
            "session_id": str(session.id),
            "step": ConversationStep.Q7_CONSTRAINTS.value,
            "answer": "no hard rules",
        },
    )

    assert resp.status_code == 409
    stored = await get_session_store().get(session.id)
    assert stored is not None
    assert stored.current_step == ConversationStep.Q6_MAX_DRAWDOWN, (
        "the session must not advance on a rejected step-mismatch"
    )
    assert "max_drawdown_pct" not in stored.answers


@pytest.mark.asyncio
async def test_submit_answer_accepts_the_sessions_own_current_step(
    client: TestClient,
) -> None:
    """The matching-step case (the only one the shipped client ever sends)
    must keep working exactly as before this guard."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
    await get_session_store().create(session)

    resp = client.post(
        "/v1/onboarding/answer",
        json={
            "session_id": str(session.id),
            "step": ConversationStep.Q6_MAX_DRAWDOWN.value,
            "answer": "20%",
        },
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["next_step"] == ConversationStep.Q7_CONSTRAINTS.value
    stored = await get_session_store().get(session.id)
    assert stored is not None
    assert stored.answers["max_drawdown_pct"] == 20
