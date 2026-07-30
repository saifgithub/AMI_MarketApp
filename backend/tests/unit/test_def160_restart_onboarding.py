"""DEF160 (AT:R65) — "Restart onboarding" must actually replace the mandate
for an authenticated user who already has one.

Before this fix, `/v1/onboarding/readback/confirm` never accepted an
authenticated caller at all — a signed-in user retaking the interview got a
built-and-dropped mandate preview, same as day one, and their old mandate
kept governing every agent. The fix adds an explicit `restart` flag on the
request that, paired with a valid Bearer token, authorises `confirm_readback`
to upsert the produced mandate for `current_user.id` directly.

This is a *distinct* operation from DEF060's claim-time bind
(`_bind_onboarding_session` in auth.py), which still refuses to hydrate a
mandate on session_id replay once one exists. That guard is exercised here
too (acceptance 2) to prove the fix for one case didn't reopen the other.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.onboarding import router as onboarding_router
from app.core.config import settings
from app.schemas.onboarding import ConversationStep, OnboardingSession
from app.services.auth_service import AuthService
from app.services.mandate_store import get_mandate_store
from app.services.session_store import get_session_store


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(onboarding_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def _completed_session(**overrides) -> OnboardingSession:
    defaults = dict(
        locale="en",
        timezone="America/New_York",
        current_step=ConversationStep.READBACK,
        answers={
            "primary_goal_raw": "Save for retirement",
            "primary_goal": "retirement",
            "horizon_raw": "10+ years",
            "horizon": "very_long",
            "path": "long_horizon",
            "q3_drawdown_quote": "Hold and wait",
            "q4_regret_quote": "Losing in feels worse",
            "q5_concentration_quote": "10% (cautious)",
            "max_drawdown_pct": 20,
            "compliance": {
                "halal": True,
                "esg_lite": False,
                "no_tobacco_alcohol_gambling": True,
                "no_fossil_fuels": False,
                "long_only": True,
                "liquid_only": True,
                "ticker_blocklist": [],
                "ticker_allowlist": None,
                "custom_constraints": [],
            },
        },
        risk_components_partial={
            "drawdown_response": 3,
            "regret_asymmetry": -1,
            "concentration_tolerance": 1,
        },
    )
    defaults.update(overrides)
    return OnboardingSession(**defaults)


def test_authenticated_restart_replaces_existing_mandate(client: TestClient) -> None:
    """Acceptance 1: a FAILS-against-current-code test — an authenticated
    user who already has an (edited) mandate completes a restarted
    interview, confirms with `restart=True`, and their stored mandate is
    replaced with the interview's answers."""
    user_id, token = _new_user()

    # Give the user a real, edited mandate first (e.g. via Settings).
    original = get_mandate_store().get_or_default(user_id)
    original = original.model_copy(
        update={
            "compliance": original.compliance.model_copy(update={"halal": False}),
            "max_drawdown_pct": 50,
        }
    )
    get_mandate_store().upsert(user_id, original)
    original_version = get_mandate_store().get(user_id).version

    session = _completed_session()
    asyncio.run(get_session_store().create(session))

    resp = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": str(session.id), "confirm": "confirm", "restart": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    replaced = get_mandate_store().get(user_id)
    assert replaced is not None
    assert replaced.compliance.halal is True  # from the restarted session
    assert replaced.max_drawdown_pct == 20  # from the restarted session, not 50
    # Acceptance 3: version bumped, auditable in history/journal replay.
    assert replaced.version == original_version + 1


def test_reauth_replaying_session_id_still_does_not_overwrite_edited_mandate(
    client: TestClient,
) -> None:
    """Acceptance 2 — the criterion that matters most: a re-auth replaying
    the SAME onboarding_session_id (no restart signal anywhere in that flow)
    must still leave an edited mandate alone. DEF060's guard in
    `_bind_onboarding_session` is untouched by this lane."""
    user_id, token = _new_user()

    pre_existing = get_mandate_store().get_or_default(user_id)
    pre_existing = pre_existing.model_copy(
        update={"compliance": pre_existing.compliance.model_copy(update={"halal": True})}
    )
    get_mandate_store().upsert(user_id, pre_existing)

    session = _completed_session(
        current_step=ConversationStep.COMPLETE,
        completed=True,
        answers={
            **_completed_session().answers,
            "compliance": {**_completed_session().answers["compliance"], "halal": False},
        },
    )
    asyncio.run(get_session_store().create(session))

    monkeypatch_env_local = settings.env
    settings.env = "local"
    try:
        r_start = client.post(
            "/v1/auth/magic_link/start",
            json={"email": "def160-reauth@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        code = r_start.json()["debug_code"]
        r = client.post(
            "/v1/auth/magic_link/verify",
            json={
                "email": "def160-reauth@example.com",
                "code": code,
                "onboarding_session_id": str(session.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
    finally:
        settings.env = monkeypatch_env_local

    # Still the pre-existing mandate's value (halal=True) — replay must not
    # have hydrated the session's (halal=False).
    stored = get_mandate_store().get(user_id)
    assert stored.compliance.halal is True


def test_restart_omitted_behaves_exactly_as_before(client: TestClient) -> None:
    """Acceptance 4: a request that omits `restart` (the default False)
    never persists — same as today, even when a valid Bearer is present."""
    user_id, token = _new_user()
    original = get_mandate_store().get_or_default(user_id)
    original = original.model_copy(
        update={"compliance": original.compliance.model_copy(update={"halal": True})}
    )
    get_mandate_store().upsert(user_id, original)
    original_version = get_mandate_store().get(user_id).version

    session = _completed_session()
    asyncio.run(get_session_store().create(session))

    resp = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": str(session.id), "confirm": "confirm"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    unchanged = get_mandate_store().get(user_id)
    assert unchanged.version == original_version
    assert unchanged.compliance.halal is True


def test_restart_true_without_auth_does_not_persist_anything(client: TestClient) -> None:
    """`restart=True` with no Bearer token can't do anything — the signal
    only takes effect paired with authentication. Preserves the anonymous-
    first path: an anon caller completes the interview normally."""
    session = _completed_session()
    asyncio.run(get_session_store().create(session))

    resp = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": str(session.id), "confirm": "confirm", "restart": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completed"] is True
    assert body["mandate_preview"]["user_id"] == "anonymous-pending-claim"
