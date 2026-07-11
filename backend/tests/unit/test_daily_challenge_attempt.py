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


# ── CR004: persistence + already_attempted + reputation ────────────────────


def test_second_attempt_returns_stored_result(client: TestClient) -> None:
    """A repeat submission — even with a different answer — returns the
    FIRST attempt's stored result with already_attempted=true."""
    _, token = _make_user_and_token()
    r1 = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 0},  # wrong
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["correct"] is False
    assert r1.json()["already_attempted"] is False

    r2 = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 1},  # the exploit: retry with the right answer
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["already_attempted"] is True
    assert body["correct"] is False  # stored result, not the re-grade
    assert body["selected_option"] == 0


def test_attempt_awards_reputation(client: TestClient) -> None:
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import ReputationEventRow

    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    with get_session() as s:
        types = sorted(
            e.event_type for e in s.execute(
                select(ReputationEventRow).where(
                    ReputationEventRow.user_id == user_id
                )
            ).scalars().all()
        )
    assert types == ["challenge_attempted", "challenge_correct"]


def test_second_attempt_journals_once(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    for _ in range(2):
        client.post(
            "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
            json={"selected_option": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
    entries, _total, _retention = get_journal_store().list_for_user(
        user_id, entry_type="daily_challenge",
    )
    assert len(entries) == 1


def test_today_carries_my_attempt_when_authed(client: TestClient, monkeypatch) -> None:
    """GET /today returns my_attempt after the user has answered."""
    from datetime import date as _date

    from app.services.daily_challenge_service import DailyChallengeService

    # Pin "today" to the fixture challenge's date.
    monkeypatch.setattr(
        DailyChallengeService, "today",
        lambda self: (self.get_by_id("dc_2026_06_01_aapl"), _date(2026, 6, 1)),
    )
    _, token = _make_user_and_token()
    r = client.get(
        "/v1/daily_challenge/today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["my_attempt"] is None

    client.post(
        "/v1/daily_challenge/dc_2026_06_01_aapl/attempt",
        json={"selected_option": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.get(
        "/v1/daily_challenge/today",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json()
    assert body["my_attempt"] == {
        "selected_option": 1,
        "correct": True,
        "correct_option": 1,
        "explanation": "Premium multiple.",
        "attempted_at": body["my_attempt"]["attempted_at"],
    }
    # Unauthed callers still get the public shape, my_attempt null.
    r = client.get("/v1/daily_challenge/today")
    assert r.status_code == 200
    assert r.json()["my_attempt"] is None
    # DEF042 — the pre-attempt public shape never carries answer/explanation.
    assert "answer" not in r.json()["challenge"]
    assert "explanation" not in r.json()["challenge"]
