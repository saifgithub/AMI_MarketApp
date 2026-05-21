"""Tests for POST /v1/daily_challenge/{cid}/attempt (BL10).

Covers: happy paths (correct + wrong), 404 on unknown id, 400 on out-of-range
option, journal entry materializes with the expected payload.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.daily_challenge import router as dc_router
from app.api.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.services.daily_challenge_service import (
    DailyChallengeService,
    get_daily_challenge_service,
)
from app.services.journal_store import get_journal_store


_FIXTURE = [
    {
        "id": "dc_2026_06_01_aapl",
        "type": "predict_the_call",
        "difficulty": 2,
        "locale": "en",
        "scenario": "AAPL P/E elevated.",
        "question": "Cheap or expensive?",
        "options": ["Cheap", "Expensive", "Fair"],
        "answer": 1,
        "explanation": "Premium multiple.",
        "related_lesson": "039",
        "related_agent": "fundamentals_analyst",
        "tags": ["valuation"],
    },
]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(json.dumps(_FIXTURE), encoding="utf-8")
    svc = DailyChallengeService(content_dir=d)

    app = FastAPI()
    app.include_router(dc_router)
    app.dependency_overrides[get_daily_challenge_service] = lambda: svc
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def test_attempt_correct_returns_win_and_explanation(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True
    assert body["correct_option"] == 1
    assert body["explanation"] == "Premium multiple."
    assert body["related_lesson"] == "039"
    assert body["related_agent"] == "fundamentals_analyst"


def test_attempt_wrong_returns_correct_option(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is False
    assert body["correct_option"] == 1


def test_attempt_unknown_challenge_returns_404(client: TestClient) -> None:
    _, token = _make_user_and_token()
    r = client.post(
        "/v1/daily_challenge/dc_does_not_exist/attempt",
        json={"selected_option": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_attempt_out_of_range_option_returns_400(client: TestClient) -> None:
    _, token = _make_user_and_token()
    # Challenge has 3 options; option 9 is out of range.
    r = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 9},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_attempt_writes_journal_entry(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    entries, _total, _retention = get_journal_store().list_for_user(
        user_id, entry_type="daily_challenge",
    )
    assert len(entries) == 1
    e = entries[0]
    assert e.payload["challenge_id"] == "dc_2026_06_01_aapl"
    assert e.payload["correct"] is True
    assert e.payload["selected_option"] == 1
    assert e.outcome == "win"
    assert "correct" in e.tags
