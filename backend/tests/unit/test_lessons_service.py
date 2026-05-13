"""Tests for the Lessons service + Earn Path activation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.lessons import QuizSubmitRequest
from app.services.lessons_service import LessonsService, get_lessons_service


# Stable handle for the "Market Orders vs Limit Orders" lesson — content
# (quiz + chat_with blocks) controlled so parsing / quiz / earn-path
# tests can pin to it. The lesson lives in the "Legacy bonus" track per
# the magical-edison-18bf91 content pass: frontmatter id matches the
# filename (`283_*`), and the M1-M12 foundations were regenerated as
# fresh lessons in the `001_*..077_*` range. LessonsService keys by
# frontmatter id, so this constant must too.
LEGACY_MARKET_ORDER_LESSON = "283_market_order_vs_limit"


@pytest.fixture
def svc() -> LessonsService:
    s = get_lessons_service()
    s.clear()
    return s


def test_catalogue_lists_foundations_track(svc: LessonsService):
    """Foundations track exists and carries enough lessons for the UI."""
    cat = svc.catalogue()
    assert cat.total_lessons >= 5
    tracks = {t.track for t in cat.tracks}
    assert "foundations" in tracks
    foundations = next(t for t in cat.tracks if t.track == "foundations")
    assert len(foundations.lessons) >= 5
    # The renumbered pre-W18 lessons stay reachable so the parsing tests
    # below still resolve.
    assert LEGACY_MARKET_ORDER_LESSON in {l.id for l in foundations.lessons}


def test_lesson_meta_defaults_module_zero_and_difficulty_to_level(tmp_path):
    """A20 — Legacy lessons (pre-W18 curriculum_map) omit module + difficulty.
    The loader hydrates module=0 and difficulty=level so the UI can sort
    consistently. We test against a temp MDX with the legacy frontmatter
    shape rather than a committed lesson — the committed legacy lessons
    have been renumbered, and the W18 set declares module explicitly.
    """
    from app.services.lessons_service import parse_mdx

    mdx = tmp_path / "999_legacy_test.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "999_legacy_test"\n'
        'title: "Legacy frontmatter"\n'
        'duration_min: 3\n'
        'level: 2\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'Body.\n',
        encoding="utf-8",
    )
    lesson = parse_mdx(mdx)
    assert lesson.meta.module == 0
    assert lesson.meta.difficulty == lesson.meta.level == 2


def test_lesson_meta_reads_module_and_difficulty_when_present(svc: LessonsService):
    """W18+ lessons declare module + difficulty explicitly."""
    # Find any lesson the loader returns with module > 0 — the W18 set
    # populates module on every new lesson. If none exist (only the
    # renumbered legacy lessons committed), skip — A20's defaulting is
    # covered by the test above.
    candidates = [m for m in svc.all_meta() if m.module > 0]
    if not candidates:
        pytest.skip("W17/W18 lesson set not committed in this branch state")
    lesson = svc.get(candidates[0].id)
    assert lesson is not None
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


def test_lesson_inlines_term_tokens_into_prose(tmp_path):
    """`<Term id="…"/>` is substituted to a `{{term:…}}` inline token
    inside the surrounding markdown block, NOT promoted to a separate
    block. This lets the client render the term as an inline chip via
    Text.rich/WidgetSpan within the paragraph flow.
    """
    from app.services.lessons_service import parse_mdx

    mdx = tmp_path / "098_term_test.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "098_term_test"\n'
        'title: "Term parse test"\n'
        'duration_min: 2\n'
        'level: 1\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'Open your <Term id="ami_watchlist" /> and pick a name.\n',
        encoding="utf-8",
    )
    lesson = parse_mdx(mdx)
    kinds = [b.kind for b in lesson.blocks]
    # No term blocks emitted — tokens ride inside prose.
    assert "term" not in kinds
    md_blocks = [b for b in lesson.blocks if b.kind == "markdown"]
    assert any("{{term:ami_watchlist}}" in (b.markdown or "") for b in md_blocks)
    # Surrounding prose is preserved on either side of the token.
    joined = " ".join(b.markdown or "" for b in md_blocks)
    assert "Open your" in joined and "and pick a name" in joined


def test_lesson_inlines_multiple_terms_in_one_sentence(tmp_path):
    """Two `<Term>` tags in the same sentence both become tokens within
    a single markdown block — no vertical-list breakage."""
    from app.services.lessons_service import parse_mdx

    mdx = tmp_path / "099_multi_term.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "099_multi_term"\n'
        'title: "Multi term"\n'
        'duration_min: 2\n'
        'level: 1\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'A <Term id="long"/> position uses a <Term id="stop_loss"/> below entry.\n',
        encoding="utf-8",
    )
    lesson = parse_mdx(mdx)
    md_blocks = [b.markdown or "" for b in lesson.blocks if b.kind == "markdown"]
    # Exactly one prose block holds both tokens.
    assert len(md_blocks) == 1
    body = md_blocks[0]
    assert "{{term:long}}" in body
    assert "{{term:stop_loss}}" in body


def test_lesson_extracts_quizzes_and_markdown(svc: LessonsService):
    lesson = svc.get(LEGACY_MARKET_ORDER_LESSON)
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
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=[1, 1],
    ))
    assert result.correct == 2
    assert result.total == 2
    assert result.passed
    assert result.score == 1.0
    status = svc.get_status(user_id, LEGACY_MARKET_ORDER_LESSON)
    assert status is not None
    assert status.quiz_passed
    assert status.completed_at is not None


def test_quiz_submit_wrong_does_not_pass(svc: LessonsService):
    user_id = uuid4()
    result = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
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
    _isolate_trader_callouts(svc, LEGACY_MARKET_ORDER_LESSON)
    user_id = uuid4()
    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=[1, 1],
    ))
    assert "trader" in res.unlocked_agents
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "trader" for a in activations)
    # Doesn't unlock twice on a re-pass
    res2 = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=[1, 1],
    ))
    assert res2.unlocked_agents == []


def test_earn_path_locks_remain_until_every_required_lesson_passes(svc: LessonsService):
    """If two lessons both have agent_callouts: [trader], passing one is
    not enough — the activation only fires after every required lesson
    is passed.
    """
    _isolate_trader_callouts(svc, LEGACY_MARKET_ORDER_LESSON)
    user_id = uuid4()
    # Inject a second required trader-callout lesson alongside 004
    fake = svc.get(LEGACY_MARKET_ORDER_LESSON).model_copy(deep=True)
    fake.meta.id = "999_fake_trader_lesson"
    fake.meta.agent_callouts = ["trader"]
    svc._lessons["999_fake_trader_lesson"] = fake

    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
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
        user_id=user_id, lesson_id=LEGACY_MARKET_ORDER_LESSON, answers=[1, 1],
    ))
    summary = svc.progress_summary(user_id)
    assert summary.lessons_completed >= 1
    assert summary.lessons_total >= 5
    assert "foundations" in summary.by_track


def test_grant_activation_marks_skip_path(svc: LessonsService):
    user_id = uuid4()
    rec = svc.grant_activation(user_id, "portfolio_manager", method="skip_path")
    assert rec.agent_id == "portfolio_manager"
    assert rec.activation_method == "skip_path"
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "portfolio_manager" for a in activations)
