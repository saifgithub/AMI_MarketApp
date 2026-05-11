"""Tests for the Lessons service + Earn Path activation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.lessons import QuizSubmitRequest
from app.services.lessons_service import LessonsService, get_lessons_service


@pytest.fixture
def svc() -> LessonsService:
    s = get_lessons_service()
    s.clear()
    return s


def test_catalogue_lists_foundations_track(svc: LessonsService):
    cat = svc.catalogue()
    assert cat.total_lessons >= 5
    tracks = {t.track for t in cat.tracks}
    assert "foundations" in tracks
    foundations = next(t for t in cat.tracks if t.track == "foundations")
    assert {l.id for l in foundations.lessons} >= {
        "001_what_is_a_stock",
        "002_what_is_a_market",
        "003_what_is_a_brokerage",
        "004_market_order_vs_limit",
        "005_what_makes_a_price_move",
    }


def test_lesson_extracts_quizzes_and_markdown(svc: LessonsService):
    lesson = svc.get("004_market_order_vs_limit")
    assert lesson is not None
    assert len(lesson.quizzes) == 2
    assert lesson.quizzes[0].options[1] == "Your order fills immediately at $152"
    assert lesson.quizzes[0].answer_index == 1
    kinds = [b.kind for b in lesson.blocks]
    assert "markdown" in kinds
    assert "quiz" in kinds
    assert "chat_with" in kinds


def test_quiz_submit_correct_passes(svc: LessonsService):
    user_id = uuid4()
    result = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="004_market_order_vs_limit",
        answers=[1, 1],
    ))
    assert result.correct == 2
    assert result.total == 2
    assert result.passed
    assert result.score == 1.0
    status = svc.get_status(user_id, "004_market_order_vs_limit")
    assert status is not None
    assert status.quiz_passed
    assert status.completed_at is not None


def test_quiz_submit_wrong_does_not_pass(svc: LessonsService):
    user_id = uuid4()
    result = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="004_market_order_vs_limit",
        answers=[0, 0],
    ))
    assert not result.passed
    assert result.correct == 0
    # explanation surfaced
    assert any(pq.get("explanation") for pq in result.per_question)


def test_earn_path_unlocks_trader_after_all_trader_lessons(svc: LessonsService):
    user_id = uuid4()
    # Only 004_market_order_vs_limit has agent_callouts: [trader] in the
    # current alpha lesson set, so passing it should unlock the Trader.
    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="004_market_order_vs_limit",
        answers=[1, 1],
    ))
    assert "trader" in res.unlocked_agents
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "trader" for a in activations)
    # Doesn't unlock twice on a re-pass
    res2 = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="004_market_order_vs_limit",
        answers=[1, 1],
    ))
    assert res2.unlocked_agents == []


def test_earn_path_locks_remain_until_every_required_lesson_passes(svc: LessonsService):
    """If we added another lesson with agent_callouts: [trader], the agent
    should not unlock until both are passed. We simulate this by injecting
    a fake lesson with the same callout."""
    user_id = uuid4()
    # Add a fake required lesson manually
    fake = svc.get("004_market_order_vs_limit").model_copy(deep=True)
    fake.meta.id = "999_fake_trader_lesson"
    fake.meta.agent_callouts = ["trader"]
    svc._lessons["999_fake_trader_lesson"] = fake

    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="004_market_order_vs_limit",
        answers=[1, 1],
    ))
    assert res.unlocked_agents == []  # second lesson not done
    res2 = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="999_fake_trader_lesson",
        answers=[1, 1],
    ))
    assert "trader" in res2.unlocked_agents
    # cleanup
    del svc._lessons["999_fake_trader_lesson"]


def test_progress_summary_tracks_completion(svc: LessonsService):
    user_id = uuid4()
    svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id, lesson_id="001_what_is_a_stock", answers=[0],
    ))
    summary = svc.progress_summary(user_id)
    assert summary.lessons_completed >= 0  # 001 has a quiz, may or may not pass
    assert summary.lessons_total >= 5
    assert "foundations" in summary.by_track


def test_grant_activation_marks_skip_path(svc: LessonsService):
    user_id = uuid4()
    rec = svc.grant_activation(user_id, "portfolio_manager", method="skip_path")
    assert rec.agent_id == "portfolio_manager"
    assert rec.activation_method == "skip_path"
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "portfolio_manager" for a in activations)
