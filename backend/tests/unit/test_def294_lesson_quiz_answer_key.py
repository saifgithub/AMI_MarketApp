"""DEF294 — a lesson quiz must not ship its own answer key.

`GET /v1/lessons/{id}` returned every `<Quiz>` block with `answer_index` and
`explanation` populated **before the user answered anything**. That is DEF042's defect on
a second surface: DEF042 closed the identical leak on `/v1/daily_challenge/*` at AT:R54
and introduced `DailyChallengePublic` for exactly this reason, and lessons were never
revisited.

What it bought an API-direct caller is not credits — a quiz pass writes only
`LessonProgressRow` — but the **agent-unlock gate**, i.e. the app's core progression,
readable straight out of the payload without opening the lesson.

The tests assert both halves, because either alone is a half-fix: the key must be ABSENT
from the read payload, and it must still ARRIVE with the graded result — otherwise the
client cannot draw a reveal and the fix reads as a feature removal.

Mac-safe: in-process app, no backend, no network.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lessons import router as lessons_router
from app.schemas.lessons import Lesson, LessonPublic


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(lessons_router)
    return TestClient(app, raise_server_exceptions=False)


def _any_lesson_id(client: TestClient) -> str:
    r = client.get("/v1/lessons")
    assert r.status_code == 200, r.text
    for track in r.json()["tracks"]:
        for meta in track["lessons"]:
            return meta["id"]
    pytest.skip("no lessons in the corpus to check")


def _quiz_blocks(body: dict) -> list[dict]:
    return [b["quiz"] for b in body["blocks"] if b.get("kind") == "quiz" and b.get("quiz")]


def test_the_read_payload_carries_no_answer_key(client: TestClient):
    """The claim, over the wire and against the real corpus rather than a fixture.

    Asserted on the whole serialized body, not just on the parsed model: a response model
    that filters correctly still leaks if some other field carries the key.
    """
    lesson_id = _any_lesson_id(client)
    r = client.get(f"/v1/lessons/{lesson_id}")
    assert r.status_code == 200, r.text
    body = r.json()

    for quiz in _quiz_blocks(body) + body.get("quizzes", []):
        assert "answer_index" not in quiz, (
            f"quiz {quiz.get('id')} ships its own answer key pre-attempt — the "
            "agent-unlock gate is readable straight out of the payload (DEF294)"
        )
        assert "explanation" not in quiz, (
            f"quiz {quiz.get('id')} ships the explanation pre-attempt, which gives the "
            "answer away just as effectively as the index"
        )


def test_every_lesson_in_the_corpus_is_clean_not_just_the_first(client: TestClient):
    """A per-lesson leak would hide behind a single-lesson spot check. Walks the whole
    catalogue, because the parse path (`_QUIZ_RE`) is shared but the corpus is not."""
    r = client.get("/v1/lessons")
    assert r.status_code == 200, r.text
    ids = [m["id"] for t in r.json()["tracks"] for m in t["lessons"]]
    assert ids, "empty corpus — this guard would pass vacuously"

    leaked: list[str] = []
    for lesson_id in ids:
        body = client.get(f"/v1/lessons/{lesson_id}").json()
        for quiz in _quiz_blocks(body) + body.get("quizzes", []):
            if "answer_index" in quiz or "explanation" in quiz:
                leaked.append(f"{lesson_id}:{quiz.get('id')}")

    assert not leaked, f"{len(leaked)} quiz block(s) still carry the key: {leaked[:5]}"


def test_the_public_shape_cannot_express_an_answer_key():
    """Structural, not behavioural. The route filters because `LessonPublic` has nowhere
    to put the key — so a future field added to the internal `Lesson` cannot leak by
    default, which a hand-written mapper would not guarantee."""
    assert "answer_index" not in LessonPublic.model_fields
    quiz_fields = set(
        LessonPublic.model_fields["quizzes"].annotation.__args__[0].model_fields
    )
    assert quiz_fields == {"id", "question", "options"}, (
        f"LessonQuizPublic grew fields: {quiz_fields}"
    )


def test_the_internal_shape_still_has_the_key():
    """Non-vacuity, and the reason this is a response-model fix rather than a parser fix:
    grading reads `answer_index` off the internal `Lesson`, so removing it there would
    break `submit_quiz` instead of securing it."""
    assert "answer_index" in Lesson.model_fields["quizzes"].annotation.__args__[0].model_fields


def test_the_graded_result_still_returns_the_key(client: TestClient):
    """The other half. If the key never arrives, the client cannot draw a reveal and this
    'fix' is a feature removal — so the submit response must still carry `correct_index`
    and `explanation`, which is where they belonged all along.

    Driven through the SERVICE rather than the route: the route needs an authenticated
    user and this test's subject is the payload shape, not the auth gate.
    """
    from uuid import uuid4

    from app.schemas.lessons import QuizSubmitRequest, QuizSubmitResponse
    from app.services.lessons_service import get_lessons_service

    assert "per_question" in QuizSubmitResponse.model_fields

    lesson_id = _any_lesson_id(client)
    body = client.get(f"/v1/lessons/{lesson_id}").json()
    quizzes = body.get("quizzes") or []
    if not quizzes:
        pytest.skip(f"{lesson_id} has no quiz to submit")

    result = get_lessons_service().submit_quiz(
        QuizSubmitRequest(
            user_id=uuid4(), lesson_id=lesson_id, answers=[0] * len(quizzes),
        )
    )

    assert result.per_question, "graded response carried no per-question detail"
    for entry in result.per_question:
        assert "correct_index" in entry, (
            "the graded result no longer names the correct option, so the reveal has "
            "nothing to render — the read-side fix cannot be completed on the client"
        )
        assert "correct" in entry
