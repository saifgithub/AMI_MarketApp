"""DEF060 (AT:R59) — claim must persist the mandate the Concierge interview
built, not discard it.

Before this fix, `/v1/onboarding/readback/confirm` only ever returned a
mandate *preview* to the client; nothing persisted it, so every claimed user
ended up with the generic default mandate (`MandateStore.get_or_default`)
regardless of what they told the Concierge. The fix hydrates a real mandate
from the completed `OnboardingSession` at claim time, keyed off the existing
BL13 `onboarding_session_id` binding.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.core.config import settings
from app.schemas.onboarding import ConversationStep, OnboardingSession
from app.services.auth_service import AuthService
from app.services.mandate_store import get_mandate_store
from app.services.session_store import get_session_store


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(mandate_router)
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
        completed=True,
        current_step=ConversationStep.COMPLETE,
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
            "daily_briefing": {
                "enabled": True,
                "time_local": "07:00",
                "timezone": "America/New_York",
                "voice_id": None,
                "delivery_channels": ["push", "in_app"],
                "language": "en",
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


def _claim_with_session(
    client: TestClient, token: str, session_id: UUID, email: str
) -> str:
    """Runs a magic-link claim carrying `onboarding_session_id`. Returns the
    claimed user's fresh Bearer token."""
    monkeypatch_env_local = settings.env
    settings.env = "local"
    try:
        r_start = client.post(
            "/v1/auth/magic_link/start",
            json={"email": email},
            headers={"Authorization": f"Bearer {token}"},
        )
        code = r_start.json()["debug_code"]
        r = client.post(
            "/v1/auth/magic_link/verify",
            json={
                "email": email,
                "code": code,
                "onboarding_session_id": str(session_id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        return r.json()["token"]
    finally:
        settings.env = monkeypatch_env_local


def test_claim_persists_mandate_from_completed_onboarding_session(
    client: TestClient,
) -> None:
    user_id, token = _new_user()
    session = _completed_session()
    asyncio.run(get_session_store().create(session))

    claimed_token = _claim_with_session(
        client, token, session.id, "def060-a@example.com"
    )

    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {claimed_token}"},
    )
    assert r.status_code == 200
    mandate = r.json()

    # Reflects the session's real answers, not the generic default (which
    # has compliance.halal=False, max_drawdown_pct=30, primary_goal derived
    # from hydrate_brief_mandate's own defaults).
    assert mandate["primary_goal"] == "retirement"
    assert mandate["horizon"] == "very_long"
    assert mandate["max_drawdown_pct"] == 20
    assert mandate["compliance"]["halal"] is True
    assert mandate["compliance"]["no_tobacco_alcohol_gambling"] is True
    assert mandate["daily_briefing"]["enabled"] is True
    assert mandate["risk_quotes"] == [
        "Hold and wait",
        "Losing in feels worse",
        "10% (cautious)",
    ]


def test_claim_falls_back_to_default_when_session_incomplete(
    client: TestClient,
) -> None:
    """A session that never reached readback confirmation (completed=False)
    must not seed a mandate — the user gets the ordinary default, same as
    claiming with no onboarding session at all."""
    user_id, token = _new_user()
    session = OnboardingSession(current_step=ConversationStep.Q3_SCENARIO_DRAWDOWN)
    asyncio.run(get_session_store().create(session))

    claimed_token = _claim_with_session(
        client, token, session.id, "def060-b@example.com"
    )

    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {claimed_token}"},
    )
    assert r.status_code == 200
    mandate = r.json()
    # get_or_default's synthetic mandate — halal defaults False.
    assert mandate["compliance"]["halal"] is False


def test_claim_does_not_clobber_an_existing_mandate(client: TestClient) -> None:
    """If a mandate row already exists for the claimed user_id (edge case —
    re-claim, or a mandate created some other way before claim completes),
    hydration must not overwrite it."""
    user_id, token = _new_user()

    # Pre-seed a mandate for this user before claim.
    pre_existing = get_mandate_store().get_or_default(user_id)
    pre_existing = pre_existing.model_copy(
        update={"compliance": pre_existing.compliance.model_copy(update={"halal": True})}
    )
    get_mandate_store().upsert(user_id, pre_existing)

    session = _completed_session(
        answers={
            **_completed_session().answers,
            "compliance": {**_completed_session().answers["compliance"], "halal": False},
        }
    )
    asyncio.run(get_session_store().create(session))

    claimed_token = _claim_with_session(
        client, token, session.id, "def060-c@example.com"
    )

    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {claimed_token}"},
    )
    assert r.status_code == 200
    # Still the pre-existing mandate's value (halal=True), not the session's
    # (halal=False) — hydration was skipped because a row already existed.
    assert r.json()["compliance"]["halal"] is True
