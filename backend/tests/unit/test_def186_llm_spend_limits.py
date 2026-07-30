"""DEF186 (security review H6 + H9 aggregate half) — unmetered,
unrate-limited LLM spend on 1-on-1 and Brief; unauthenticated bug-upload
disk-fill.

Lane acceptance #8: "1-on-1 and Brief are rate-limited; bug-upload
requires a session or is size- and rate-bounded. Name the limits you
chose and why." (Full credit-spend metering per the review's broader
H6 fix description is a pricing/product decision outside this security
batch's scope — see the lane hand-off for the disclosure.)

Limits chosen:
  - one_on_one/message: 12/min per bearer-authenticated user_id.
  - brief/message (and the deprecated /v1/coach/message shim, which
    calls the SAME function): 12/min per bearer-authenticated user_id.
  - feedback/bug: 5/hour per IP (unauthenticated by design; can't key
    by user).
  - OneOnOneMessageRequest/BriefMessageRequest: user_message capped at
    8,000 chars, history capped at 100 turns.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.brief import router as brief_router
from app.api.coach import router as coach_router
from app.api.feedback import router as feedback_router
from app.api.one_on_one import router as one_on_one_router
from app.services.auth_service import AuthService
from app.services.rate_limit import (
    brief_message_rate_limit,
    bug_upload_rate_limit,
    one_on_one_message_rate_limit,
)


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(one_on_one_router)
    a.include_router(brief_router)
    a.include_router(coach_router)
    a.include_router(feedback_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_limiters():
    one_on_one_message_rate_limit.reset()
    brief_message_rate_limit.reset()
    bug_upload_rate_limit.reset()
    yield
    one_on_one_message_rate_limit.reset()
    brief_message_rate_limit.reset()
    bug_upload_rate_limit.reset()


def _new_user() -> str:
    auth = AuthService()
    _, token, _ = auth.ensure_anonymous(device_user_id=None)
    return token


def test_one_on_one_message_is_rate_limited_per_user(client: TestClient):
    token = _new_user()
    fake_session_id = str(uuid4())
    statuses = []
    for _ in range(15):
        r = client.post(
            "/v1/agents/one_on_one/message",
            json={"session_id": fake_session_id, "user_message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses, statuses
    # The limit fires BEFORE any session/LLM work — proven by the fact it
    # fires even against a session_id that doesn't exist.
    assert statuses.index(429) <= 12


def test_one_on_one_message_limit_is_per_user_not_shared(client: TestClient):
    token_a = _new_user()
    token_b = _new_user()
    fake_session_id = str(uuid4())
    # Burn user A's budget.
    for _ in range(12):
        client.post(
            "/v1/agents/one_on_one/message",
            json={"session_id": fake_session_id, "user_message": "hi"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    r_a = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": fake_session_id, "user_message": "hi"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_a.status_code == 429
    # User B is unaffected.
    r_b = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": fake_session_id, "user_message": "hi"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_b.status_code != 429


def test_brief_message_is_rate_limited_per_user(client: TestClient):
    token = _new_user()
    fake_session_id = str(uuid4())
    statuses = []
    for _ in range(15):
        r = client.post(
            "/v1/brief/message",
            json={"session_id": fake_session_id, "user_message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses, statuses


def test_deprecated_coach_message_shim_inherits_the_same_rate_limit(client: TestClient):
    """The /v1/coach/message shim calls brief_message() directly — it must
    not be a way to dodge the limiter just wired into /v1/brief/message."""
    token = _new_user()
    fake_session_id = str(uuid4())
    # Burn the budget via /v1/brief/message.
    for _ in range(12):
        client.post(
            "/v1/brief/message",
            json={"session_id": fake_session_id, "user_message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
    r = client.post(
        "/v1/coach/message",
        json={"session_id": fake_session_id, "user_message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 429


def test_one_on_one_user_message_max_length_enforced(client: TestClient):
    token = _new_user()
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": str(uuid4()), "user_message": "x" * 8_001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_one_on_one_history_length_capped(client: TestClient):
    token = _new_user()
    history = [{"role": "user", "content": "hi"}] * 101
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": str(uuid4()), "user_message": "hi", "history": history},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_brief_user_message_max_length_enforced(client: TestClient):
    token = _new_user()
    r = client.post(
        "/v1/brief/message",
        json={"session_id": str(uuid4()), "user_message": "x" * 8_001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_bug_upload_is_rate_limited_per_ip(client: TestClient, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    form = {
        "category": "ui_glitch",
        "title": "t",
        "app_version": "0.1.0+5",
        "platform": "ios",
    }
    statuses = []
    for _ in range(8):
        r = client.post("/v1/feedback/bug", data=form)
        statuses.append(r.status_code)
    assert 429 in statuses, statuses
