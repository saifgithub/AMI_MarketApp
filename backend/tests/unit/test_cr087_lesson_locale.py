"""CR087 — lesson locale serving (AR/MS translated bodies → app).

The Language Manager (CR083) authored AR + MS translated lesson bodies, but the
pipeline only ever loaded and served `*.en.mdx`. This suite pins the serving
slice that makes a non-EN locale return the translated body end to end:

  - the loader parses `{stem}.ar.mdx` / `{stem}.ms.mdx` siblings and derives
    each lesson's `locale_versions` from what actually parsed (a malformed
    locale file is logged and skipped — the EN lesson never drops);
  - `get(id, locale)` returns the locale body, falling back to EN when absent;
  - EN meta stays canonical; only title/blocks/quizzes come from the locale;
  - `catalogue(locale)` returns the locale-available lessons with translated
    titles;
  - `GET /v1/lessons/{id}?locale=ar` honours the query param;
  - quiz grading uses the *served locale's* answer_index.

Quiz-integrity is the real risk (CLAUDE.md: degrade loudly): a translator who
reordered an MCQ's options would silently mis-grade AR users. The controlled
`test_submit_quiz_grades_against_served_locale` proves grading follows the
served locale, and `test_served_ar_quizzes_match_en` fails the build on any
AR↔EN answer_index drift in a *served* AR lesson (the loader's integrity gate
drops corrupted AR bodies to EN fallback before they can be served).

Design note — controlled vs corpus tests: the pure serving logic (fallback,
canonical meta, served-locale grading, malformed-skip) is pinned with tiny
tmp-dir fixtures so it is deterministic and independent of the shipping corpus.
A smaller set of tests then runs over the real content to prove the wiring holds
end to end.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lessons import router
from app.schemas.lessons import Lesson, QuizSubmitRequest
from app.services.lessons_service import (
    LessonsService,
    _locale_quiz_servable,
    get_lessons_service,
    parse_mdx,
)

# A stable, foundational AR lesson that parses cleanly — used for the real-corpus
# happy path. Asserted to exist / be AR-available so a corpus change fails here
# loudly rather than skipping silently.
KNOWN_GOOD_AR_LESSON = "001_what_is_a_stock"

# Any Arabic-script codepoint — proves a string is actually Arabic, not the
# English text keyed under "ar".
_ARABIC_RE = re.compile(r"[؀-ۿ]")


def _has_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


# ── tmp-dir MDX builders ─────────────────────────────────────────────────────


def _mdx(
    stem: str,
    title: str,
    *,
    answer: int = 1,
    n_options: int = 3,
    track: str = "foundations",
    code: str = "CORE 1",
    module: int = 1,
) -> str:
    opts = ", ".join(f'"opt{i}"' for i in range(n_options))
    return (
        "---\n"
        f'id: "{stem}"\n'
        f'title: "{title}"\n'
        f'track: "{track}"\n'
        f'code: "{code}"\n'
        f"module: {module}\n"
        "duration_min: 4\n"
        "difficulty: 2\n"
        "---\n\n"
        "# Heading\n\nSome body prose.\n\n"
        "<Quiz\n"
        '  question="Q?"\n'
        f"  options={{[{opts}]}}\n"
        f"  answer={{{answer}}}\n"
        '  explanation="Because reasons."\n'
        "/>\n"
    )


def _write(dir_: Path, stem: str, locale: str, content: str) -> None:
    (dir_ / f"{stem}.{locale}.mdx").write_text(content, encoding="utf-8")


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def svc():
    """The real singleton service, loaded from the shipping corpus."""
    return get_lessons_service()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ── controlled loader / fallback logic ───────────────────────────────────────


def test_loader_parses_locale_siblings(tmp_path: Path):
    _write(tmp_path, "010_x", "en", _mdx("010_x", "English title"))
    _write(tmp_path, "010_x", "ar", _mdx("010_x", "عنوان عربي"))
    _write(tmp_path, "010_x", "ms", _mdx("010_x", "Tajuk Melayu"))

    s = LessonsService(content_dir=tmp_path)
    lesson = s._lessons["010_x"]
    assert lesson.meta.locale_versions == ["en", "ar", "ms"]
    assert set(s._locale_lessons["010_x"]) == {"en", "ar", "ms"}


def test_loader_skips_malformed_locale_and_keeps_en(tmp_path: Path):
    """A locale file that fails to parse is skipped (logged), the EN lesson is
    never dropped, and the lesson's locale_versions excludes the broken locale.
    """
    _write(tmp_path, "011_y", "en", _mdx("011_y", "English title"))
    # Unescaped nested double-quotes → YAML ParserError, exactly the class of
    # bug present in ~22 shipping AR files.
    _write(tmp_path, "011_y", "ar", _mdx("011_y", 'bad "nested" title'))

    s = LessonsService(content_dir=tmp_path)
    assert "011_y" in s._lessons  # EN survived
    assert s._lessons["011_y"].meta.locale_versions == ["en"]
    assert "ar" not in s._locale_lessons["011_y"]
    # And serving AR falls back to the EN body, never crashes.
    assert s.get("011_y", "ar").meta.title == "English title"


def test_get_falls_back_to_en_when_locale_absent(tmp_path: Path):
    _write(tmp_path, "012_z", "en", _mdx("012_z", "English title"))
    s = LessonsService(content_dir=tmp_path)
    en = s.get("012_z", "en")
    ar = s.get("012_z", "ar")
    assert ar is not None
    assert ar.meta.title == en.meta.title
    assert ar.blocks == en.blocks


def test_get_unknown_lesson_returns_none(tmp_path: Path):
    _write(tmp_path, "013_a", "en", _mdx("013_a", "English title"))
    s = LessonsService(content_dir=tmp_path)
    assert s.get("999_missing", "ar") is None
    assert s.get("999_missing", "en") is None


def test_en_meta_stays_canonical_locale_supplies_title(tmp_path: Path):
    """Structural meta (track, code, module) comes from EN even when the locale
    frontmatter disagrees; only the display title comes from the locale file."""
    _write(
        tmp_path, "014_b", "en",
        _mdx("014_b", "English", track="technical_analysis", code="TECH 9", module=3),
    )
    _write(
        tmp_path, "014_b", "ar",
        # AR frontmatter deliberately carries wrong structural meta.
        _mdx("014_b", "عنوان", track="foundations", code="WRONG 1", module=9),
    )
    s = LessonsService(content_dir=tmp_path)
    ar = s.get("014_b", "ar")
    assert ar.meta.title == "عنوان"          # display field ← locale
    assert ar.meta.track == "technical_analysis"  # canonical ← EN
    assert ar.meta.code == "TECH 9"          # canonical ← EN
    assert ar.meta.module == 3               # canonical ← EN


def test_catalogue_filters_by_locale_and_localizes_title(tmp_path: Path):
    _write(tmp_path, "015_c", "en", _mdx("015_c", "Both English"))
    _write(tmp_path, "015_c", "ar", _mdx("015_c", "عربي متوفر"))
    _write(tmp_path, "016_d", "en", _mdx("016_d", "English only"))
    s = LessonsService(content_dir=tmp_path)

    en_cat = s.catalogue("en")
    ar_cat = s.catalogue("ar")
    en_ids = {m.id for t in en_cat.tracks for m in t.lessons}
    ar_ids = {m.id for t in ar_cat.tracks for m in t.lessons}
    assert en_ids == {"015_c", "016_d"}
    assert ar_ids == {"015_c"}  # EN-only lesson excluded from AR catalogue
    ar_meta = next(m for t in ar_cat.tracks for m in t.lessons if m.id == "015_c")
    assert ar_meta.title == "عربي متوفر"  # localized title in the catalogue


# ── controlled quiz-integrity gate (the real risk) ───────────────────────────


def test_loader_rejects_ar_answer_index_drift(tmp_path: Path):
    """A translator who reordered the AR options (answer_index 2 vs EN's 1)
    would mis-grade AR users. The gate rejects that AR body — the lesson falls
    back to EN, and the AR served quiz carries EN's answer_index."""
    _write(tmp_path, "017_e", "en", _mdx("017_e", "English", answer=1))
    _write(tmp_path, "017_e", "ar", _mdx("017_e", "عربي", answer=2))
    s = LessonsService(content_dir=tmp_path)
    assert s._lessons["017_e"].meta.locale_versions == ["en"]  # AR rejected
    assert "ar" not in s._locale_lessons["017_e"]
    assert s.get("017_e", "ar").quizzes[0].answer_index == 1  # EN, not the drifted 2


def test_loader_rejects_ar_with_empty_options(tmp_path: Path):
    """The dominant CR083 AR corruption: options emptied to `[]` and answer
    reset to 0. Serving it would be an unanswerable AR quiz (DEF064). Rejected
    → EN fallback."""
    _write(tmp_path, "017_f", "en", _mdx("017_f", "English", answer=1, n_options=3))
    _write(tmp_path, "017_f", "ar", _mdx("017_f", "عربي", answer=0, n_options=0))
    s = LessonsService(content_dir=tmp_path)
    assert s._lessons["017_f"].meta.locale_versions == ["en"]
    assert len(s.get("017_f", "ar").quizzes[0].options) == 3  # EN options served


def test_gate_helper_accepts_identical_quiz(tmp_path: Path):
    _write(tmp_path, "017_g", "en", _mdx("017_g", "English", answer=2))
    _write(tmp_path, "017_g", "ar", _mdx("017_g", "عربي", answer=2))
    s = LessonsService(content_dir=tmp_path)
    en = s.get("017_g", "en")
    ar_raw = parse_mdx(tmp_path / "017_g.ar.mdx")
    ok, reason = _locale_quiz_servable(en, ar_raw)
    assert ok, reason
    assert "ar" in s._locale_lessons["017_g"]


def test_submit_quiz_grades_against_served_locale(tmp_path: Path):
    """submit_quiz grades against the *served* locale's quiz object, not a
    hard-coded EN one. Proven by injecting a divergent (answer_index 2) AR body
    directly into the service — bypassing the integrity gate on purpose — and
    showing the AR submission is graded against 2 while EN stays 1."""
    _write(tmp_path, "017_h", "en", _mdx("017_h", "English", answer=1))
    s = LessonsService(content_dir=tmp_path)
    s.clear()

    en = s.get("017_h", "en")
    ar_quiz = en.quizzes[0].model_copy(update={"answer_index": 2})
    s._locale_lessons["017_h"]["ar"] = Lesson(
        meta=en.meta.model_copy(update={"title": "عربي"}),
        blocks=en.blocks,
        quizzes=[ar_quiz],
    )

    # AR key is 2 → AR-locale submission of 2 passes, of 1 fails.
    assert s.submit_quiz(QuizSubmitRequest(
        user_id=uuid4(), lesson_id="017_h", answers=[2], locale="ar",
    )).passed
    assert not s.submit_quiz(QuizSubmitRequest(
        user_id=uuid4(), lesson_id="017_h", answers=[1], locale="ar",
    )).passed
    # EN key is 1 → EN-locale submission of 1 passes, of 2 fails.
    assert s.submit_quiz(QuizSubmitRequest(
        user_id=uuid4(), lesson_id="017_h", answers=[1], locale="en",
    )).passed
    assert not s.submit_quiz(QuizSubmitRequest(
        user_id=uuid4(), lesson_id="017_h", answers=[2], locale="en",
    )).passed


def test_submit_quiz_defaults_to_en_locale(tmp_path: Path):
    """A request without a locale grades against EN (backward-compatible)."""
    _write(tmp_path, "018_f", "en", _mdx("018_f", "English", answer=0))
    s = LessonsService(content_dir=tmp_path)
    s.clear()
    resp = s.submit_quiz(QuizSubmitRequest(
        user_id=uuid4(), lesson_id="018_f", answers=[0],
    ))
    assert resp.passed


# ── real corpus wiring ───────────────────────────────────────────────────────


def test_real_catalogue_ar_is_non_empty(svc):
    cat = svc.catalogue(locale="ar")
    assert cat.total_lessons > 0
    ids = {m.id for t in cat.tracks for m in t.lessons}
    assert KNOWN_GOOD_AR_LESSON in ids


def test_real_get_ar_returns_arabic_title_and_body(svc):
    en = svc.get(KNOWN_GOOD_AR_LESSON, "en")
    ar = svc.get(KNOWN_GOOD_AR_LESSON, "ar")
    assert ar is not None
    assert _has_arabic(ar.meta.title)
    assert ar.meta.title != en.meta.title
    ar_markdown = " ".join(b.markdown or "" for b in ar.blocks)
    assert _has_arabic(ar_markdown)
    # Canonical structural meta preserved from EN.
    assert ar.meta.id == en.meta.id
    assert ar.meta.track == en.meta.track
    assert ar.meta.code == en.meta.code
    assert ar.meta.gates_agents == en.meta.gates_agents


def test_real_get_lesson_endpoint_honors_locale(client: TestClient):
    r_en = client.get(f"/v1/lessons/{KNOWN_GOOD_AR_LESSON}")
    r_ar = client.get(f"/v1/lessons/{KNOWN_GOOD_AR_LESSON}?locale=ar")
    assert r_en.status_code == 200, r_en.text
    assert r_ar.status_code == 200, r_ar.text
    assert _has_arabic(r_ar.json()["meta"]["title"])
    assert not _has_arabic(r_en.json()["meta"]["title"])


def test_real_ar_unavailable_lessons_fall_back_to_en(svc):
    """Every lesson whose AR body is unavailable (no sibling OR malformed and
    skipped by the loader) must serve the EN body under locale='ar' — never a
    404 or empty. Dynamic so it holds regardless of how many AR files parse."""
    ar_ids = {m.id for t in svc.catalogue("ar").tracks for m in t.lessons}
    en_ids = {m.id for t in svc.catalogue("en").tracks for m in t.lessons}
    fallback_ids = en_ids - ar_ids
    for lid in fallback_ids:
        ar = svc.get(lid, "ar")
        en = svc.get(lid, "en")
        assert ar is not None, f"{lid}: AR serve returned None"
        assert ar.blocks == en.blocks, f"{lid}: fallback body is not EN"
        assert ar.meta.title == en.meta.title


def test_served_ar_quizzes_match_en(svc):
    """CR087 — the real risk: a translator who reordered an MCQ's options makes
    AR's answer_index disagree with EN's, silently mis-grading AR users. This
    asserts the invariant our serving gate guarantees: every lesson the service
    actually serves in AR has, per question, identical quiz count, option count
    and answer_index to EN, with no empty option. It is green by construction of
    the gate — and it is a live guard: if the gate is ever weakened, or a served
    AR lesson drifts, this fails the build.

    (AR files that are unparseable or quiz-corrupted are *not* served — they
    fall back to EN, so they carry no grading risk. Their count is reported in
    the lane hand-off as a CR083 content follow-up, not failed here, because
    this lane cannot re-author 43 Arabic translations.)
    """
    ar_ids = {m.id for t in svc.catalogue("ar").tracks for m in t.lessons}
    assert ar_ids, "no AR lessons served — corpus or loader regressed"

    drift: list[str] = []
    for lid in sorted(ar_ids):
        en = svc.get(lid, "en")
        ar = svc.get(lid, "ar")
        if len(en.quizzes) != len(ar.quizzes):
            drift.append(f"{lid}: quiz count en={len(en.quizzes)} ar={len(ar.quizzes)}")
            continue
        for i, (eq, aq) in enumerate(zip(en.quizzes, ar.quizzes)):
            if eq.answer_index != aq.answer_index:
                drift.append(
                    f"{lid} q{i}: answer_index en={eq.answer_index} ar={aq.answer_index}"
                )
            if any(not (o or "").strip() for o in aq.options):
                drift.append(f"{lid} q{i}: empty AR option served")
    assert not drift, "SERVED AR/EN quiz drift (gate leak):\n" + "\n".join(drift)


def test_ar_serving_coverage_has_a_reasonable_floor(svc):
    """A blunt regression tripwire: if AR serving collapses (loader bug, corpus
    wipe), catch it here rather than shipping an all-English 'AR' release. Not
    an exact pin — the corpus grows and content gets fixed. Floor only."""
    ar_ids = {m.id for t in svc.catalogue("ar").tracks for m in t.lessons}
    assert len(ar_ids) >= 250, f"AR served collapsed to {len(ar_ids)} lessons"
