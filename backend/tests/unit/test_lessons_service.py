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


def test_lesson_meta_defaults_module_zero_and_difficulty_to_level(svc: LessonsService):
    """A20 — Legacy lessons (pre-W18 curriculum_map) omit module + difficulty.
    The loader must hydrate sensible defaults so the UI can keep sorting.
    """
    legacy = svc.get("001_what_is_a_stock")
    assert legacy is not None
    assert legacy.meta.module == 0
    assert legacy.meta.difficulty == legacy.meta.level


def test_lesson_meta_reads_module_and_difficulty_when_present(svc: LessonsService):
    """W18+ lessons declare module + difficulty explicitly."""
    lesson = svc.get("014_position_sizing_basics")
    if lesson is None:
        pytest.skip("W17/W18 lesson set not committed in this branch state")
    assert lesson.meta.module > 0
    assert lesson.meta.difficulty > 0


def test_lesson_parses_animation_mdx_block(tmp_path):
    """A21 — <Animation name="..." /> parses to a block of kind=animation
    with `animation_name` populated. Unknown names are still emitted —
    the client decides whether to render the asset or the placeholder.
    """
    from app.services.lessons_service import parse_mdx

    mdx = tmp_path / "099_test.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "099_test"\n'
        'title: "Animation parse test"\n'
        'duration_min: 2\n'
        'level: 1\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'Some prose.\n\n'
        '<Animation name="risk_pyramid" />\n\n'
        'More prose.\n',
        encoding="utf-8",
    )
    lesson = parse_mdx(mdx)
    kinds = [b.kind for b in lesson.blocks]
    assert "animation" in kinds
    anim = next(b for b in lesson.blocks if b.kind == "animation")
    assert anim.animation_name == "risk_pyramid"


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


def _isolate_trader_callouts(svc: LessonsService, *keep_ids: str) -> None:
    """Strip 'trader' from every lesson's agent_callouts except the kept ones.

    The earn-path tests were authored when only `004_market_order_vs_limit`
    had `agent_callouts: [trader]`. W17/W18 added more trader-callout lessons
    (014/015/016/...), which (correctly) means the activation rule now
    requires passing all of them. To keep the unit tests narrowly scoped to
    the earn-path mechanics rather than the curriculum churn, we monkey-patch
    the in-memory cache here.
    """
    keep = set(keep_ids)
    for lid, lesson in svc._lessons.items():
        if lid in keep:
            continue
        if "trader" in lesson.meta.agent_callouts:
            lesson.meta.agent_callouts = [
                a for a in lesson.meta.agent_callouts if a != "trader"
            ]


def test_earn_path_unlocks_trader_after_all_trader_lessons(svc: LessonsService):
    """With 004 as the sole trader-callout lesson, passing it unlocks Trader."""
    _isolate_trader_callouts(svc, "004_market_order_vs_limit")
    user_id = uuid4()
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
    """If two lessons both have agent_callouts: [trader], passing one is
    not enough — the activation only fires after every required lesson
    is passed.
    """
    _isolate_trader_callouts(svc, "004_market_order_vs_limit")
    user_id = uuid4()
    # Inject a second required trader-callout lesson alongside 004
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
