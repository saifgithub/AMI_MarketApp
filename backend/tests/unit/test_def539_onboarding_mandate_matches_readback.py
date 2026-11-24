"""DEF539 (AT:B1) — the mandate saved after the Concierge interview must be the
one the readback showed.

UAT-ONB-043 (build 133): readback "Risk 1/5 - moderate, Max drawdown 20%",
yet YOU > SETTINGS showed Risk 3/5 Balanced, drawdown 30%. Root cause: the
interview's mandate was persisted only at account claim, so a user who skipped
the claim prompt was left on `get_or_default()` while the compliance floor
enforced it. These tests drive the real HTTP flow (start -> answers -> readback
-> confirm), skip the claim, and compare the stored mandate with the readback.
"""

from __future__ import annotations

import asyncio
import re
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.api.onboarding import router as onboarding_router
from app.schemas.onboarding import ConversationStep
from app.services.auth_service import AuthService
from app.services.concierge_engine import (
    RISK_LEVEL_LABELS,
    risk_level_label,
    session_to_mandate_dict,
)
from app.services.mandate_store import get_mandate_store
from app.services.session_store import get_session_store


@pytest.fixture
def client() -> TestClient:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(onboarding_router)
    a.include_router(mandate_router)
    return TestClient(a)


def _new_user() -> tuple[UUID, dict[str, str]]:
    u, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return u.id, {"Authorization": f"Bearer {token}"}


# The AMI-DL-27 transcript: long-term wealth, most cautious scenario answers,
# a 20% drawdown, liquid-only.
_TRANSCRIPT = [
    (ConversationStep.Q1_GOAL, "Build long-term wealth"),
    (ConversationStep.Q2_HORIZON, "3–10 years"),
    (ConversationStep.Q3_SCENARIO_DRAWDOWN, "Sell everything"),
    (ConversationStep.Q4_SCENARIO_REGRET, "Losing in feels worse"),
    (ConversationStep.Q5_SCENARIO_CONCENTRATION, "10% (cautious)"),
    (ConversationStep.Q6_MAX_DRAWDOWN, "20%"),
    (ConversationStep.Q7_CONSTRAINTS, "ONLY liquid names (no microcaps)"),
]


def _run_interview(client: TestClient) -> tuple[str, dict, str]:
    sid = client.post(
        "/v1/onboarding/start",
        json={"locale": "en", "timezone": "Asia/Riyadh", "age_confirmed": True},
    ).json()["session_id"]
    body: dict = {}
    for step, answer in _TRANSCRIPT:
        r = client.post(
            "/v1/onboarding/answer",
            json={"session_id": sid, "step": step.value, "answer": answer},
        )
        assert r.status_code == 200, r.text
        body = r.json()
    assert body["next_step"] == ConversationStep.READBACK.value
    return sid, body["readback_summary"], body["concierge_reply"]["content"]


def test_skipping_the_claim_still_persists_exactly_what_the_readback_showed(
    client: TestClient,
) -> None:
    user_id, headers = _new_user()
    assert get_mandate_store().get(user_id) is None

    sid, summary, readback_text = _run_interview(client)
    # A non-default profile, so equality with the defaults (3 / 30) cannot pass by accident.
    assert summary["risk_score"] != 3
    assert summary["max_drawdown_pct"] == 20

    m =re.search(r"Risk: (\d)/5 — ([^.]+)\.\s+Max drawdown (\d+)%", readback_text)
    assert m, readback_text
    assert int(m.group(1)) == summary["risk_score"]
    assert m.group(2) == risk_level_label(summary["risk_score"])
    assert int(m.group(3)) == summary["max_drawdown_pct"]

    # Confirm with a Bearer token, then NEVER claim an account.
    r = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": sid, "confirm": "confirm"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # What Settings reads (GET /v1/mandate) is the readback, not the defaults.
    got = client.get(f"/v1/mandate/{user_id}", headers=headers)
    assert got.status_code == 200, got.text
    stored = got.json()
    assert stored["risk_score"] == summary["risk_score"]
    assert stored["max_drawdown_pct"] == summary["max_drawdown_pct"] == 20
    assert stored["primary_goal"] == summary["primary_goal"] == "long_term_wealth"
    assert stored["horizon"] == summary["horizon"]
    assert stored["compliance"]["liquid_only"] is True
    assert r.json()["mandate_preview"]["risk_score"] == stored["risk_score"]
    assert get_mandate_store().get(user_id) is not None


def test_confirm_does_not_clobber_an_existing_mandate_without_restart(
    client: TestClient,
) -> None:
    user_id, headers = _new_user()
    existing = get_mandate_store().get_or_default(user_id).model_copy(
        update={"max_drawdown_pct": 50},
    )
    get_mandate_store().upsert(user_id, existing)
    version = get_mandate_store().get(user_id).version

    sid, _, _ = _run_interview(client)
    r = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": sid, "confirm": "confirm"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    after = get_mandate_store().get(user_id)
    assert after.version == version
    assert after.max_drawdown_pct == 50


def test_saved_mandate_is_built_from_the_frozen_readback_not_a_rebuild(
    client: TestClient,
) -> None:
    """A later rebuild from `answers` must not be able to change what is saved."""
    sid, summary, _ = _run_interview(client)
    session = asyncio.run(get_session_store().get(UUID(sid)))
    assert session.readback_summary == summary

    session.answers["max_drawdown_pct"] = 99
    saved = session_to_mandate_dict(session, user_id="x")
    assert saved["max_drawdown_pct"] == summary["max_drawdown_pct"] == 20
    assert saved["risk_score"] == summary["risk_score"]


def test_risk_label_map_covers_1_to_5_and_1_is_not_moderate() -> None:
    assert set(RISK_LEVEL_LABELS) == {1, 2, 3, 4, 5}
    assert len(set(RISK_LEVEL_LABELS.values())) == 5
    assert risk_level_label(1) == "capital preservation"
    assert risk_level_label(3) == "balanced"
    assert risk_level_label(5) == "highest risk tolerance"
    assert "moderate" not in RISK_LEVEL_LABELS.values()
    for bad in (0, 6, -1):
        with pytest.raises(ValueError):
            risk_level_label(bad)
