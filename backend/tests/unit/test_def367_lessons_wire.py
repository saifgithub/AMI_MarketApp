"""DEF367 — close the lessons + ai_coach wire surfaces (AT:R75).

`backend/scripts/wire_contract/verify.py` flags a route -> Dart-model surface
UNVERIFIED when no test exercises it through the HTTP boundary (conftest's
wire-capture hook). These tests do nothing but drive each route through a
real `TestClient` with a real 2xx JSON body, so the capture records a
response the gate can compare against the keys `api_client.dart` reads:

  GET  /v1/ai_coach/search                     -> CoachSearchHit
  GET  /v1/lessons/activations/$userId         -> AgentActivationRecord
  GET  /v1/lessons/progress/$userId            -> ProgressSummary
  GET  /v1/lessons/progress/$userId/by_lesson  -> LessonStatus
  GET  /v1/lessons/requirements/$userId        -> AgentUnlockRequirement
  POST /v1/lessons/quiz                        -> QuizResult

No product code changes here — test-only, per DEF367's lane brief. Three of
these six surfaces are hit with a real, non-empty 2xx body but still fail the
gate: `scripts/wire_contract/discover_pairs.py`'s extraction has two blind
spots (a `for (final e in ...)` list-comprehension it doesn't recognise as
`is_list`, and an envelope-key regex that doesn't match `data![...]` — only
`data?[...]`/`data[...]`) — see the DEF367-LESSONS hand-off for detail. Fixing
that is `scripts/wire_contract/` tooling, not a test, so it's out of this
lane's test-only scope; documented as a finding instead of worked around.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ai_coach import router as ai_coach_router
from app.api.lessons import router as lessons_router
from app.db import get_session
from app.db.models import AgentActivationRow
from app.services.auth_service import AuthService


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(lessons_router)
    a.include_router(ai_coach_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _any_lesson_id(client: TestClient) -> str:
    r = client.get("/v1/lessons")
    assert r.status_code == 200, r.text
    for track in r.json()["tracks"]:
        for meta in track["lessons"]:
            return meta["id"]
    pytest.skip("no lessons in the corpus to check")


def test_ai_coach_search_returns_hits(client: TestClient) -> None:
    r = client.get("/v1/ai_coach/search", params={"q": "risk", "limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "hits" in body
    if body["hits"]:
        hit = body["hits"][0]
        assert "qa" in hit and "score" in hit
        assert "id" in hit["qa"] and "question" in hit["qa"]


def test_lessons_progress_returns_summary(client: TestClient) -> None:
    user_id, token = _make_user_and_token()

    r = client.get(f"/v1/lessons/progress/{user_id}", headers=_auth_headers(token))

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == str(user_id)
    assert "lessons_completed" in body
    assert "lessons_total" in body
    assert "by_track" in body
    assert "agents_unlocked" in body


def test_lessons_progress_by_lesson_returns_status_list(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    lesson_id = _any_lesson_id(client)
    started = client.post(
        "/v1/lessons/start",
        json={"user_id": str(user_id), "lesson_id": lesson_id},
        headers=_auth_headers(token),
    )
    assert started.status_code == 200, started.text

    r = client.get(
        f"/v1/lessons/progress/{user_id}/by_lesson", headers=_auth_headers(token)
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["lesson_id"] == lesson_id
    assert body[0]["user_id"] == str(user_id)


def test_lessons_requirements_returns_unlock_list(client: TestClient) -> None:
    user_id, token = _make_user_and_token()

    r = client.get(
        f"/v1/lessons/requirements/{user_id}", headers=_auth_headers(token)
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    if body:
        req = body[0]
        assert "agent_id" in req
        assert "unlocked" in req
        assert "required" in req
        assert "passed_count" in req
        assert "remaining_count" in req


def test_lessons_activations_returns_activation_list(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    # A fresh user has no activations, and an empty list closes nothing for
    # the wire gate (it needs one real AgentActivationRecord object to check
    # the client's keys against) — so seed one directly, same pattern as
    # test_merge_service.py's AgentActivationRow fixtures.
    with get_session() as s:
        s.add(AgentActivationRow(
            user_id=user_id, agent_id="market_analyst",
            activation_method="founder_grant",
        ))
        s.flush()

    r = client.get(f"/v1/lessons/activations/{user_id}", headers=_auth_headers(token))

    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    record = body[0]
    assert record["agent_id"] == "market_analyst"
    assert record["activation_method"] == "founder_grant"
    assert "id" in record and "user_id" in record and "activated_at" in record


def test_lessons_quiz_submit_returns_graded_result(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    lesson_id = _any_lesson_id(client)

    body = client.get(f"/v1/lessons/{lesson_id}").json()
    quizzes = body.get("quizzes") or []
    if not quizzes:
        pytest.skip(f"{lesson_id} has no quiz to submit")

    r = client.post(
        "/v1/lessons/quiz",
        json={
            "user_id": str(user_id),
            "lesson_id": lesson_id,
            "answers": [0] * len(quizzes),
        },
        headers=_auth_headers(token),
    )

    assert r.status_code == 200, r.text
    result = r.json()
    assert result["lesson_id"] == lesson_id
    assert "correct" in result
    assert "total" in result
    assert "passed" in result
    assert "score" in result
    assert "per_question" in result
    assert "unlocked_agents" in result
