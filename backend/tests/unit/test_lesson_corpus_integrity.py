"""Corpus-wide integrity checks over every shipped lesson quiz.

Why this file exists (DEF064/DEF065): the rest of test_lessons_service.py pins
to a single lesson (283_market_order_vs_limit), so it cannot see a defect that
lives in the other 269. Two shipped for months behind that blind spot:

  DEF064 — 12 quizzes used a numeric free-response form (`answer={20}
           tolerance={0}`, no `options`) that the authoring spec documented but
           the pipeline never implemented. parse_mdx's `or []` / `.get(...,0)`
           fallbacks turned it into a zero-option question, which the Flutter
           reader renders with no tappable rows. Those 12 lessons could never
           be completed, and two agent unlock gateways (trader,
           portfolio_manager) were unreachable behind them.
  DEF065 — 277 explanations cited an option by index ("the tempting wrong
           answer is option 0"). The reader renders no option labels, so those
           pointed at something invisible — under two contradictory
           conventions, 0-indexed in some files and 1-indexed in others.

Both are the CLAUDE.md "degrade loudly" class: a silent fallback shipped a dead
end. Per the failure_patterns house rule these assertions are the enforcing
check, so the same content defect fails the build instead of the user.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.lessons_service import CONTENT_LESSONS_DIR, parse_mdx

# Matches an explanation citing an option by number, either convention:
# "option 0", "Option 3", "options 1". DEF065.
_OPTION_INDEX_CITATION = re.compile(r"\boptions?\s+\d", re.IGNORECASE)

# The unsupported numeric free-response attribute. DEF064 — catching it at the
# source text (not the parsed model) is what makes reintroduction impossible:
# parse_mdx silently discards it, so the parsed form shows no trace.
_TOLERANCE_ATTR = re.compile(r"\btolerance=")

EXPECTED_LESSON_COUNT = 270


def _lesson_paths() -> list[Path]:
    return sorted(CONTENT_LESSONS_DIR.glob("*.en.mdx"))


@pytest.fixture(scope="module")
def lessons():
    return [parse_mdx(p) for p in _lesson_paths()]


def test_every_lesson_parses():
    """LessonsService._reload() swallows parse failures with a log line, so a
    malformed lesson silently vanishes from the catalogue rather than failing.
    Assert the count directly — a disappearing lesson is a shrinking
    curriculum, which is exactly the kind of quiet degradation we don't want.
    """
    paths = _lesson_paths()
    assert len(paths) == EXPECTED_LESSON_COUNT, (
        f"expected {EXPECTED_LESSON_COUNT} lesson files, found {len(paths)}"
    )
    for path in paths:
        parse_mdx(path)  # raises on malformed frontmatter/body


def test_every_question_is_answerable(lessons):
    """DEF064 — a question with fewer than two options cannot be answered, and
    the client's allAnswered gate then blocks the lesson forever."""
    offenders = [
        (lesson.meta.id, q.id, len(q.options))
        for lesson in lessons
        for q in lesson.quizzes
        if len(q.options) < 2
    ]
    assert not offenders, f"questions with <2 options: {offenders}"


def test_every_answer_index_is_in_range(lessons):
    offenders = [
        (lesson.meta.id, q.id, q.answer_index, len(q.options))
        for lesson in lessons
        for q in lesson.quizzes
        if not 0 <= q.answer_index < len(q.options)
    ]
    assert not offenders, f"answer_index out of range: {offenders}"


def test_options_are_distinct_and_non_empty(lessons):
    offenders = []
    for lesson in lessons:
        for q in lesson.quizzes:
            stripped = [o.strip() for o in q.options]
            if any(not o for o in stripped):
                offenders.append((lesson.meta.id, q.id, "empty option"))
            elif len(set(stripped)) != len(stripped):
                offenders.append((lesson.meta.id, q.id, "duplicate options"))
    assert not offenders, f"malformed option sets: {offenders}"


def test_every_question_has_text_and_explanation(lessons):
    offenders = [
        (lesson.meta.id, q.id)
        for lesson in lessons
        for q in lesson.quizzes
        if not (q.question or "").strip() or not (q.explanation or "").strip()
    ]
    assert not offenders, f"missing question text or explanation: {offenders}"


def test_no_question_text_cites_an_option_by_index(lessons):
    """DEF065 — the reader renders no option labels, so "option 2" names
    something the user cannot see. Name the option by its content instead.

    Covers all three user-visible surfaces, not just explanations: one option
    body was found citing indices too (186_sustainable_roe_mean_reversion),
    which an explanation-only check would have let through.
    """
    offenders = []
    for lesson in lessons:
        for q in lesson.quizzes:
            surfaces = [("explanation", q.explanation or ""), ("question", q.question or "")]
            surfaces += [(f"option[{i}]", o) for i, o in enumerate(q.options)]
            for where, text in surfaces:
                hit = _OPTION_INDEX_CITATION.search(text)
                if hit:
                    offenders.append((lesson.meta.id, q.id, where, hit.group(0)))
    assert not offenders, f"text citing an option by index: {offenders}"


def test_no_lesson_uses_the_unsupported_numeric_quiz_form():
    """DEF064 — `tolerance=` means someone authored a numeric free-response
    quiz. Nothing in backend/ or mobile/ implements it; parse_mdx drops the
    attribute and yields a zero-option question. Multiple-choice is the only
    supported form."""
    offenders = [
        path.name
        for path in _lesson_paths()
        if _TOLERANCE_ATTR.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "unsupported numeric free-response quiz (tolerance=) in: "
        f"{offenders}. Multiple-choice is the only supported form."
    )
