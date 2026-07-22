"""Tests for the Lessons service + Earn Path activation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.lessons import QuizSubmitRequest
from app.services.agent_gateways import AGENT_GATEWAYS
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


@pytest.fixture(autouse=True)
def _restore_gateways():
    """Undo any gateway pinning after each test.

    `get_lessons_service()` is a process singleton and `AGENT_GATEWAYS` is a
    module-level dict, so a test that repoints the trader gateway leaks into
    every test that runs after it — including
    test_lesson_corpus_integrity's "every agent has exactly GATEWAY_SIZE
    lessons", which would then pass or fail on file ordering alone.
    """
    original = {a: list(ids) for a, ids in AGENT_GATEWAYS.items()}
    svc = get_lessons_service()
    saved = {lid: list(l.meta.gates_agents) for lid, l in svc._lessons.items()}
    yield
    AGENT_GATEWAYS.clear()
    AGENT_GATEWAYS.update(original)
    for lid, gates in saved.items():
        lesson = svc._lessons.get(lid)
        if lesson is not None:
            lesson.meta.gates_agents = gates


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


def test_lesson_number_derived_from_id_prefix(tmp_path):
    """CR018 — the reference number is the numeric prefix of the id, derived at
    load time (no frontmatter field), stable per lesson. 0 when unprefixed."""
    from app.services.lessons_service import lesson_number, parse_mdx

    assert lesson_number("023_support_and_resistance") == 23
    assert lesson_number("001_what_is_a_stock") == 1
    assert lesson_number("292_edge_case") == 292
    assert lesson_number("no_numeric_prefix") == 0

    mdx = tmp_path / "042_number_test.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "042_number_test"\n'
        'title: "Number derivation"\n'
        'duration_min: 3\n'
        'level: 1\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'Body.\n',
        encoding="utf-8",
    )
    assert parse_mdx(mdx).meta.number == 42


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


def test_lesson_inlines_lesson_tokens_into_prose(tmp_path):
    """CR053 — `<Lesson id="…"/>` is substituted to a `{{lesson:…}}` inline
    token inside the surrounding markdown block, NOT promoted to a separate
    block. Mirrors `<Term>`'s treatment exactly.
    """
    from app.services.lessons_service import parse_mdx

    mdx = tmp_path / "097_lesson_ref_test.en.mdx"
    mdx.write_text(
        '---\n'
        'id: "097_lesson_ref_test"\n'
        'title: "Lesson ref parse test"\n'
        'duration_min: 2\n'
        'level: 1\n'
        'track: "foundations"\n'
        'topic: "test"\n'
        '---\n\n'
        'See <Lesson id="039" /> for a refresher.\n',
        encoding="utf-8",
    )
    lesson = parse_mdx(mdx)
    kinds = [b.kind for b in lesson.blocks]
    # No lesson-ref blocks emitted — tokens ride inside prose.
    assert "lesson" not in kinds
    md_blocks = [b for b in lesson.blocks if b.kind == "markdown"]
    assert any("{{lesson:039}}" in (b.markdown or "") for b in md_blocks)
    joined = " ".join(b.markdown or "" for b in md_blocks)
    assert "See" in joined and "for a refresher" in joined


def test_lesson_extracts_quizzes_and_markdown(svc: LessonsService):
    lesson = svc.get(LEGACY_MARKET_ORDER_LESSON)
    assert lesson is not None
    assert len(lesson.quizzes) == 2
    # Assert on the answer's TEXT, not its position — CR042 randomised which
    # slot holds the correct option, and content edits will move it again.
    q0 = lesson.quizzes[0]
    assert q0.options[q0.answer_index] == "Your order fills immediately at $152"
    kinds = [b.kind for b in lesson.blocks]
    assert "markdown" in kinds
    assert "quiz" in kinds
    assert "chat_with" in kinds


def _correct_answers(svc: LessonsService, lesson_id: str) -> list[int]:
    lesson = svc.get(lesson_id)
    assert lesson is not None
    return [q.answer_index for q in lesson.quizzes]


def _wrong_answers(svc: LessonsService, lesson_id: str) -> list[int]:
    lesson = svc.get(lesson_id)
    assert lesson is not None
    return [(q.answer_index + 1) % len(q.options) for q in lesson.quizzes]


def test_quiz_submit_correct_passes(svc: LessonsService):
    user_id = uuid4()
    result = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
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
        answers=_wrong_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    assert not result.passed
    assert result.correct == 0
    # explanation surfaced
    assert any(pq.get("explanation") for pq in result.per_question)


def _pin_trader_gateway(svc: LessonsService, *lesson_ids: str) -> None:
    """Make `lesson_ids` the entire gateway set for `trader`, for one test.

    DEF068 moved the gate from "first 3 lessons by id that callout the agent" to
    an explicit curated list, so isolating the earn-path mechanics now means
    pinning the map rather than stripping callouts. Both sides have to move
    together: `AGENT_GATEWAYS` is what `_gateway_lessons_for_agent` reads, and
    `meta.gates_agents` is what `_check_agent_unlocks` iterates to decide which
    agents a just-passed lesson could even affect.

    Mutates the service's in-memory cache and the gateway dict in place, matching
    what the earn-path tests here have always done; the `svc` fixture rebuilds
    both per test.
    """
    AGENT_GATEWAYS["trader"] = list(lesson_ids)
    keep = set(lesson_ids)
    for lid, lesson in svc._lessons.items():
        gates = [a for a in lesson.meta.gates_agents if a != "trader"]
        if lid in keep:
            gates.append("trader")
        lesson.meta.gates_agents = sorted(gates)


def test_earn_path_unlocks_trader_after_all_trader_lessons(svc: LessonsService):
    """With one lesson as the whole trader gateway, passing it unlocks Trader."""
    _pin_trader_gateway(svc, LEGACY_MARKET_ORDER_LESSON)
    user_id = uuid4()
    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    assert "trader" in res.unlocked_agents
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "trader" for a in activations)
    # Doesn't unlock twice on a re-pass
    res2 = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    assert res2.unlocked_agents == []


def test_gateway_set_is_the_curated_list_not_every_callout(svc: LessonsService):
    """Passing lessons that merely *mention* an agent never unlocks it (DEF068).

    This used to assert the opposite shape — that the gate was the first
    UNLOCK_REQUIRED_PER_AGENT lessons by id sort, whichever those happened to be.
    That rule is what put `aggressive_debator`'s third gate at lesson 225 and left
    a 50-lesson alpha user at 0/3 on three agents. The gate is now exactly the
    curated list and nothing else counts, which is the property worth pinning.
    """
    user_id = uuid4()
    _pin_trader_gateway(svc, LEGACY_MARKET_ORDER_LESSON)

    # Lessons that call out trader but aren't in the gateway set.
    enrichment_ids = [f"99{i}_fake_trader_{i}" for i in range(3)]
    template = svc.get(LEGACY_MARKET_ORDER_LESSON)
    for fid in enrichment_ids:
        f = template.model_copy(deep=True)
        f.meta.id = fid
        f.meta.agent_callouts = ["trader"]
        f.meta.gates_agents = []
        svc._lessons[fid] = f

    assert svc._gateway_lessons_for_agent("trader") == [LEGACY_MARKET_ORDER_LESSON]

    for fid in enrichment_ids:
        res = svc.submit_quiz(QuizSubmitRequest(
            user_id=user_id, lesson_id=fid,
            answers=_correct_answers(svc, fid),
        ))
        assert res.passed
        assert "trader" not in res.unlocked_agents

    # The one gateway lesson does it on its own.
    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id, lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    assert "trader" in res.unlocked_agents

    for fid in enrichment_ids:
        del svc._lessons[fid]


def test_unlock_requirements_reports_progress_per_agent(svc: LessonsService):
    """DEF068 — the endpoint behind the locked-agent sheet. Nothing used to
    answer "which lessons do I still owe", which is why the client derived it."""
    user_id = uuid4()
    _pin_trader_gateway(svc, LEGACY_MARKET_ORDER_LESSON)

    before = {r.agent_id: r for r in svc.unlock_requirements(user_id)}
    assert set(before) == set(AGENT_GATEWAYS)
    trader = before["trader"]
    assert trader.unlocked is False
    assert [l.lesson_id for l in trader.required] == [LEGACY_MARKET_ORDER_LESSON]
    assert trader.passed_count == 0
    assert trader.remaining_count == 1
    # Each gateway lesson carries the code the sheet renders and AMI speaks.
    assert all(l.code for l in trader.required)

    svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id, lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))

    after = {r.agent_id: r for r in svc.unlock_requirements(user_id)}["trader"]
    assert after.unlocked is True
    assert after.passed_count == 1
    assert after.remaining_count == 0
    assert after.required[0].passed is True


def test_earn_path_locks_remain_until_every_required_lesson_passes(svc: LessonsService):
    """With two lessons in the gateway, passing one is not enough — the
    activation only fires once every required lesson is passed.
    """
    user_id = uuid4()
    fake = svc.get(LEGACY_MARKET_ORDER_LESSON).model_copy(deep=True)
    fake.meta.id = "999_fake_trader_lesson"
    svc._lessons["999_fake_trader_lesson"] = fake
    _pin_trader_gateway(svc, LEGACY_MARKET_ORDER_LESSON, "999_fake_trader_lesson")

    res = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    assert res.unlocked_agents == []  # second lesson not done
    res2 = svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id,
        lesson_id="999_fake_trader_lesson",
        answers=_correct_answers(svc, "999_fake_trader_lesson"),
    ))
    assert "trader" in res2.unlocked_agents
    # cleanup
    del svc._lessons["999_fake_trader_lesson"]


def test_progress_summary_tracks_completion(svc: LessonsService):
    user_id = uuid4()
    svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id, lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    summary = svc.progress_summary(user_id)
    assert summary.lessons_completed >= 1
    assert summary.lessons_total >= 5
    assert "foundations" in summary.by_track


def test_list_status_returns_per_lesson_rows(svc: LessonsService):
    user_id = uuid4()
    # No rows yet
    assert svc.list_status(user_id) == []
    # Start one lesson
    svc.mark_started(user_id, LEGACY_MARKET_ORDER_LESSON)
    rows = svc.list_status(user_id)
    assert len(rows) == 1
    assert rows[0].lesson_id == LEGACY_MARKET_ORDER_LESSON
    assert rows[0].started_at is not None
    assert not rows[0].quiz_passed
    # Pass the quiz — completed_at and quiz_passed should be set
    svc.submit_quiz(QuizSubmitRequest(
        user_id=user_id, lesson_id=LEGACY_MARKET_ORDER_LESSON,
        answers=_correct_answers(svc, LEGACY_MARKET_ORDER_LESSON),
    ))
    rows = svc.list_status(user_id)
    assert len(rows) == 1
    assert rows[0].quiz_passed
    assert rows[0].completed_at is not None


def test_grant_activation_marks_skip_path(svc: LessonsService):
    user_id = uuid4()
    rec = svc.grant_activation(user_id, "portfolio_manager", method="skip_path")
    assert rec.agent_id == "portfolio_manager"
    assert rec.activation_method == "skip_path"
    activations = svc.list_activations(user_id)
    assert any(a.agent_id == "portfolio_manager" for a in activations)
