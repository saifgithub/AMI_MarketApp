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

import json
import re
from pathlib import Path

import pytest

from app.services.lessons_service import CONTENT_LESSONS_DIR, parse_mdx

# Matches an explanation citing an option by number, either convention:
# "option 0", "Option 3", "options 1" (DEF065) — or by position, "the first
# option", "the last option" (DEF079, same failure under answer-shuffle).
# DEF083 widened the positional branch: DEF079's guard required the literal
# word "option(s)" after the ordinal, but the corpus overwhelmingly writes
# "the first one", "the first answer", or a bare "the last — 'quoted text'" —
# none of which contain "option", so none were caught. Also matches ordinals
# followed by "ones?|answers?|choices?", or a bare "the <ordinal> —" form.
_OPTION_INDEX_CITATION = re.compile(
    r"\boptions?\s+\d"
    r"|\b(?:first|second|third|fourth|fifth|last)\s+(?:options?|ones?|answers?|choices?)\b"
    r"|\bthe\s+(?:first|second|third|fourth|fifth|last)\s+[—–]",
    re.IGNORECASE,
)

# The unsupported numeric free-response attribute. DEF064 — catching it at the
# source text (not the parsed model) is what makes reintroduction impossible:
# parse_mdx silently discards it, so the parsed form shows no trace.
_TOLERANCE_ATTR = re.compile(r"\btolerance=")

# A floor, not an exact pin (CR054-GUARD). Content waves append lessons without
# touching backend/, so an exact count would turn red on every wave; a floor
# still catches the silent-shrink failure this file exists for. Bump it when a
# wave integrates — it only ever grows, never returns to an exact pin.
LESSON_COUNT_FLOOR = 342


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
    assert len(paths) >= LESSON_COUNT_FLOOR, (
        f"expected at least {LESSON_COUNT_FLOOR} lesson files, found "
        f"{len(paths)} — lessons have silently disappeared from the corpus"
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


# ── CR053: `{{lesson:ID}}` inline quick-link resolve guard ──────────────
#
# `<Lesson id="ID"/>` is substituted (parse_mdx, mirroring `<Term>`) to the
# inline token `{{lesson:ID}}`. Nothing validates that ID against the corpus
# at substitution time — parse_mdx sees one file and has no global id map —
# so a typo'd or deleted id would otherwise ship as a dead client-side chip.
# This is the resolve guard (degrade-loudly, CR040): every token produced
# across the whole corpus must resolve to a real `content/lessons/<ID>_*.en.mdx`.
#
# Pre-migration (CR053-MIGRATE not yet landed) there are zero `<Lesson/>` tags
# in the corpus, so this passes vacuously today — that's correct; it arms the
# guard so the migration's tags are validated as they land.

_LESSON_TOKEN_RE = re.compile(r"\{\{lesson:(?P<id>[^}]+)\}\}")


def test_every_lesson_token_resolves_to_a_real_lesson_id(lessons):
    known_ids = {l.meta.id for l in lessons}
    offenders = []
    for lesson in lessons:
        for block in lesson.blocks:
            for token_id in _LESSON_TOKEN_RE.findall(block.markdown or ""):
                if token_id not in known_ids:
                    offenders.append((lesson.meta.id, token_id))
    assert not offenders, (
        "{{lesson:ID}} tokens with no matching content/lessons/<ID>_*.en.mdx "
        f"(source lesson, dangling id): {offenders}"
    )


# ── CR053-MIGRATE: no un-tagged GLOBAL-id ref left in prose ─────────────
#
# scripts/migrate_lesson_refs.py converts every "lesson NNN" (3-digit/
# zero-padded, or value>=16 matching a real lesson) to a `<Lesson id=.../>`
# tag, which parse_mdx substitutes to `{{lesson:...}}` before this test ever
# sees the raw body — so a real edit disappears from _RAW_LESSON_REF_RE's
# view entirely; only a MISSED one would still read as bare prose here. Bare
# "lesson N" for N<=15 is deliberately NOT forbidden — CR053-MIGRATE resolves
# those as within-module ordinals (same-prefix code lookup, not a global id),
# and a blanket ban would false-positive on the ~57 legitimate ones.
_RAW_LESSON_REF_RE = re.compile(
    r"\blesson\s+(?:0\d\d|(?:1[6-9]|[2-9]\d|\d{3}))\b", re.IGNORECASE
)

# No allowlist entries exist post-migration (0 flagged in
# content/_authoring/cr053_migration_report.md). A future addition here must
# name the specific lesson + ref and say why it's exempt, not just silence
# the guard.
CR053_GLOBAL_REF_ALLOWLIST: set[tuple[str, str]] = set()


def test_no_untagged_global_lesson_ref_remains_in_any_body():
    """CR053-MIGRATE guard — combined with the resolve guard above, the
    corpus is self-policing for Class 1: every global-id ref is either a
    resolving `{{lesson:}}` token or doesn't exist as bare prose any more."""
    offenders = []
    for path in _lesson_paths():
        raw = path.read_text(encoding="utf-8")
        body = raw.split("---", 2)[-1] if raw.startswith("---") else raw
        for m in _RAW_LESSON_REF_RE.finditer(body):
            if (path.name, m.group(0)) in CR053_GLOBAL_REF_ALLOWLIST:
                continue
            offenders.append((path.name, m.group(0)))
    assert not offenders, (
        "un-tagged global-id 'lesson NNN' prose ref (should be a "
        f"<Lesson id=.../> tag, or added to the allowlist with a reason): {offenders}"
    )


# ── CR044: group-scoped lesson codes ────────────────────────────────────
#
# The code is the identifier the user reads off the badge and says back to the
# Concierge ("go read N&M 22"). It's authored into frontmatter and frozen there
# rather than derived, so nothing recomputes it — which means nothing would
# notice a missing, duplicated, or mislabelled one either. These do.


def test_every_lesson_has_a_code(lessons):
    """A lesson with no code renders a fallback badge and cannot be referenced
    in speech or in agent copy — the exact gap CR044 exists to close."""
    offenders = [l.meta.id for l in lessons if not l.meta.code]
    assert not offenders, f"lessons missing a `code` in frontmatter: {offenders}"


def test_lesson_codes_are_unique(lessons):
    """Two lessons sharing a code makes every reference to it ambiguous."""
    seen: dict[str, str] = {}
    collisions = []
    for l in lessons:
        if l.meta.code in seen:
            collisions.append((l.meta.code, seen[l.meta.code], l.meta.id))
        seen[l.meta.code] = l.meta.id
    assert not collisions, f"duplicate lesson codes (code, first, second): {collisions}"


def test_lesson_code_prefix_matches_its_track(lessons):
    """The prefix IS the group claim. A lesson whose track moved but whose code
    didn't would tell the user it lives somewhere it doesn't."""
    from app.services.lessons_service import TRACK_PREFIX

    offenders = [
        (l.meta.id, l.meta.code, l.meta.track)
        for l in lessons
        if not l.meta.code.startswith(TRACK_PREFIX.get(l.meta.track, "\0") + " ")
    ]
    assert not offenders, (
        f"code prefix disagrees with track (id, code, track): {offenders}"
    )


def test_lesson_codes_are_contiguous_within_each_track(lessons):
    """`TECH 1..45` with no gaps and no repeats.

    A gap means a lesson was deleted and its code retired mid-sequence, which is
    survivable; but it more often means a hand-edit went wrong. Either way the
    author should have to look at it deliberately rather than discover it from a
    user who couldn't find TECH 30.
    """
    from collections import defaultdict

    nums: dict[str, list[int]] = defaultdict(list)
    malformed = []
    for l in lessons:
        parts = l.meta.code.rsplit(" ", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            malformed.append((l.meta.id, l.meta.code))
            continue
        nums[l.meta.track].append(int(parts[1]))
    assert not malformed, f"codes not in '<PREFIX> <n>' form: {malformed}"

    broken = {
        track: sorted(ns)
        for track, ns in nums.items()
        if sorted(ns) != list(range(1, len(ns) + 1))
    }
    assert not broken, f"track code sequences not contiguous 1..N: {broken}"


# ── DEF111: daily-challenge related_lesson must resolve to a real lesson ──
#
# LessonsService.get() is an exact dict-key lookup keyed on the full lesson
# id (e.g. "045_greed"), not the bare CR018 display/reference number ("045").
# Every content/daily_challenges/**/*.json `related_lesson` field was
# authored as the bare number — 573/573 occurrences, corpus-wide, 0 correct —
# so GET /v1/lessons/045 404s every time a user taps the "related lesson"
# link after a daily challenge (100% failure rate, not an edge case). Every
# other lesson-linking call site (lesson_reader_screen.dart,
# track_lessons_screen.dart) passes the real `meta.id`; the daily-challenge
# corpus was the one outlier. Fixed by rewriting all 573 values to the real
# id; this guard makes the bare-numeric form fail the build if it recurs.


def test_every_daily_challenge_related_lesson_resolves(lessons):
    from app.services.daily_challenge_service import CONTENT_DAILY_CHALLENGES_DIR

    known_ids = {l.meta.id for l in lessons}
    offenders = []
    for path in sorted(CONTENT_DAILY_CHALLENGES_DIR.glob("**/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data:
            related = item.get("related_lesson")
            if related and related not in known_ids:
                offenders.append((path.name, item.get("id"), related))
    assert not offenders, (
        "related_lesson values with no matching content/lessons/<ID>_*.en.mdx "
        f"(file, challenge_id, related_lesson): {offenders}"
    )


# ── DEF068: curated agent gateways ──────────────────────────────────────


def test_every_agent_has_a_full_curated_gateway_set():
    """All 12 gated agents, exactly GATEWAY_SIZE lessons each.

    An agent missing from the map has an empty gateway set, and
    `_check_agent_unlocks` skips empty sets — so it would be permanently
    unlockable with no error anywhere. That is DEF064's failure mode arriving by
    a different route.
    """
    from app.schemas.agents import TWELVE_AGENT_IDS
    from app.services.agent_gateways import AGENT_GATEWAYS, GATEWAY_SIZE

    expected = {a.value if hasattr(a, "value") else a for a in TWELVE_AGENT_IDS}
    assert set(AGENT_GATEWAYS) == expected, (
        f"gateway map covers {sorted(AGENT_GATEWAYS)}, expected {sorted(expected)}"
    )
    wrong_size = {
        agent: len(ids)
        for agent, ids in AGENT_GATEWAYS.items()
        if len(ids) != GATEWAY_SIZE
    }
    assert not wrong_size, f"agents whose gateway set isn't {GATEWAY_SIZE}: {wrong_size}"

    dupes = {
        agent: ids for agent, ids in AGENT_GATEWAYS.items() if len(set(ids)) != len(ids)
    }
    assert not dupes, f"agents with a repeated gateway lesson: {dupes}"


def test_every_gateway_lesson_exists_in_the_corpus(lessons):
    """A typo'd id is an unpassable gate: nothing serves that lesson, so the
    requirement can never be satisfied and the agent is dead."""
    from app.services.agent_gateways import AGENT_GATEWAYS

    ids = {l.meta.id for l in lessons}
    missing = [
        (agent, lesson_id)
        for agent, gateway in AGENT_GATEWAYS.items()
        for lesson_id in gateway
        if lesson_id not in ids
    ]
    assert not missing, f"gateway lessons not in the corpus: {missing}"


def test_every_gateway_lesson_declares_its_agent_in_callouts(lessons):
    """The lesson tile renders `agent_callouts` as hex avatars. A gateway lesson
    that doesn't name its agent shows the user a lesson that unlocks somebody it
    never mentions — the tile and the gate disagreeing about who it belongs to.
    """
    from app.services.agent_gateways import AGENT_GATEWAYS

    by_id = {l.meta.id: l.meta for l in lessons}
    offenders = [
        (agent, lesson_id)
        for agent, gateway in AGENT_GATEWAYS.items()
        for lesson_id in gateway
        if lesson_id in by_id and agent not in by_id[lesson_id].agent_callouts
    ]
    assert not offenders, (
        "gateway lessons that don't list their agent in agent_callouts: "
        f"{offenders}"
    )


def test_gates_agents_is_the_inverse_of_the_gateway_map(lessons):
    """`gates_agents` drives both the lesson-list badge and the unlock check
    (`_check_agent_unlocks` iterates it). If it drifts from AGENT_GATEWAYS, a
    lesson silently stops counting toward the gate it belongs to."""
    from app.services.agent_gateways import AGENT_GATEWAYS

    expected: dict[str, list[str]] = {}
    for agent, gateway in AGENT_GATEWAYS.items():
        for lesson_id in gateway:
            expected.setdefault(lesson_id, []).append(agent)

    mismatched = [
        (l.meta.id, sorted(l.meta.gates_agents), sorted(expected.get(l.meta.id, [])))
        for l in lessons
        if sorted(l.meta.gates_agents) != sorted(expected.get(l.meta.id, []))
    ]
    assert not mismatched, f"gates_agents drifted (id, actual, expected): {mismatched}"


# ── CR054 Wave 0: BOK track wiring ──────────────────────────────────────
#
# The 4 new tracks (asset_classes / economics_macro / quant_methods /
# ethics_integrity) start empty and fill deliberately, wave by wave. This
# section guards the wiring: each new track is declared in the `Track` enum
# AND wired into both maps with the frozen CR044 prefix, no prefix collides
# with any existing one, and the display/prefix maps are 1:1 keyed to the
# `Track` enum. Anything thinner and a wave-1 author could ship an "ASST 1"
# badge that renders empty. Population correctness is the CR044 guards' job
# above (prefix-matches-track + contiguous 1..N).
#
# A Wave-0 pin (`test_cr054_new_tracks_are_empty_at_wave_0`) additionally
# asserted the 4 tracks held zero lessons; it was scaffolding by design ("the
# enforcement floor until Wave 1 fills the tracks") and was retired by
# CR054-GUARD the moment Wave 1 began landing content.
#
# CR059 extends this set with the 2 net-new facets that complete the locked
# 13-facet taxonomy: `islamic_finance` (SHARIA) and `decision_evaluation`
# (EVAL). Same guard, same empty-until-content-lands posture — no new
# emptiness pin, per CR059 §4 (CR044 contiguity covers population later).


CR054_NEW_TRACKS = {
    "asset_classes": "ASST",
    "economics_macro": "MACRO",
    "quant_methods": "QUANT",
    "ethics_integrity": "ETHIC",
    "islamic_finance": "SHARIA",
    "decision_evaluation": "EVAL",
}


def test_cr054_new_tracks_are_declared_in_the_track_enum():
    """The `Track` enum in schemas/lessons.py is the single source of truth for
    the valid track set — a new track that lives only in the service-layer maps
    but not in the enum is silently untyped and cannot be referenced from
    schema-level validation later."""
    from app.schemas.lessons import Track

    enum_values = {t.value for t in Track}
    missing = [t for t in CR054_NEW_TRACKS if t not in enum_values]
    assert not missing, f"CR054 tracks missing from Track enum: {missing}"


def test_cr054_new_tracks_have_display_names_and_prefixes():
    """Every new BOK track has BOTH a display name (rendered in the catalogue
    tile) and a CR044 prefix (stamped into every lesson's spoken code). One
    without the other ships a half-wired track that a Wave 1 author would
    discover only when their frontmatter fails to load or their tile renders
    with no title."""
    from app.services.lessons_service import TRACK_TITLES, TRACK_PREFIX

    for track, prefix in CR054_NEW_TRACKS.items():
        assert track in TRACK_TITLES, f"missing display name for CR054 track: {track}"
        assert TRACK_TITLES[track].strip(), f"blank display name for CR054 track: {track}"
        assert TRACK_PREFIX.get(track) == prefix, (
            f"CR044 prefix mismatch for {track}: got {TRACK_PREFIX.get(track)!r}, "
            f"want {prefix!r}"
        )


def test_all_cr044_prefixes_are_unique():
    """A shared prefix would make "MACRO 3" ambiguous between two tracks — the
    exact class of failure CR044 exists to prevent. Covers the whole prefix
    map, not just the new rows, so a future addition that collides with an
    existing prefix (e.g. someone reusing TECH) fails here too."""
    from app.services.lessons_service import TRACK_PREFIX

    seen: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []
    for track, prefix in TRACK_PREFIX.items():
        if prefix in seen:
            collisions.append((prefix, seen[prefix], track))
        else:
            seen[prefix] = track
    assert not collisions, (
        f"duplicate CR044 track prefixes (prefix, first_track, second_track): {collisions}"
    )


def test_track_title_and_prefix_maps_have_matching_keys():
    """Wire drift — a track present in TRACK_TITLES but not in TRACK_PREFIX
    (or vice versa) ships either a titled track with no lesson codes or a
    prefix that cannot be rendered anywhere. Enforce the 1:1 across both maps."""
    from app.services.lessons_service import TRACK_TITLES, TRACK_PREFIX

    only_titles = set(TRACK_TITLES) - set(TRACK_PREFIX)
    only_prefixes = set(TRACK_PREFIX) - set(TRACK_TITLES)
    assert not only_titles and not only_prefixes, (
        f"TRACK_TITLES vs TRACK_PREFIX drift — only in titles: {sorted(only_titles)}, "
        f"only in prefixes: {sorted(only_prefixes)}"
    )


def test_track_enum_and_maps_cover_the_same_track_set():
    """`Track` enum is the canonical set; the two service-layer maps must
    exactly enumerate it. A `Track` value with no maps is a track without
    display/prefix wiring (dead in the UI); a map entry with no `Track` value
    is a stringly-typed track no schema can validate."""
    from app.schemas.lessons import Track
    from app.services.lessons_service import TRACK_PREFIX, TRACK_TITLES

    enum_values = {t.value for t in Track}
    assert set(TRACK_TITLES) == enum_values, (
        f"TRACK_TITLES keys drifted from Track enum: "
        f"only_in_map={sorted(set(TRACK_TITLES) - enum_values)}, "
        f"only_in_enum={sorted(enum_values - set(TRACK_TITLES))}"
    )
    assert set(TRACK_PREFIX) == enum_values, (
        f"TRACK_PREFIX keys drifted from Track enum: "
        f"only_in_map={sorted(set(TRACK_PREFIX) - enum_values)}, "
        f"only_in_enum={sorted(enum_values - set(TRACK_PREFIX))}"
    )


# ── CR054-GUARD: capstone invariants ────────────────────────────────────
#
# Every CR054 module (M13–M26) ends with exactly one capstone — a synthesis
# lesson per the authoring prompt's "Module capstone template (v2)". The
# author's declaration is the `capstone` tag; these guards hold that tag to
# the template's two structural promises: the capstone is its module's LAST
# lesson, and it ends on a synthesis quiz (declared via the `synthesis` tag —
# there is no per-quiz type field, so the tag is the machine-checkable form;
# whether the questions genuinely span the module is the content-review
# gate's judgement, not a regex's).


# 071_how_to_verify_before_you_wire_money (EDGE 21, module 11) predates the
# CR054 template — its "capstone" tag is informal M11-era usage: it sits
# mid-module (M11 runs through lesson 267) and declares no synthesis quiz.
# The authoring prompt is explicit that M1–M12 have no capstones and must not
# be retrofitted, so it is exempt rather than held to rules written two
# hundred lessons after it shipped.
PRE_CR054_CAPSTONE_TAGS = {"071_how_to_verify_before_you_wire_money"}


def _cr054_capstones(lessons):
    return [
        l
        for l in lessons
        if "capstone" in l.meta.tags and l.meta.id not in PRE_CR054_CAPSTONE_TAGS
    ]


def test_every_capstone_is_the_last_lesson_in_its_module(lessons):
    """A capstone mid-module means either the capstone landed early or a
    later lesson was appended after it — both break the module's arc (the
    capstone synthesises everything before it, so nothing may follow it).
    Uses the id-derived `number` as the order, same as the catalogue sort."""
    last_by_module: dict[int, object] = {}
    for l in lessons:
        cur = last_by_module.get(l.meta.module)
        if cur is None or l.meta.number > cur.meta.number:
            last_by_module[l.meta.module] = l

    offenders = []
    for l in _cr054_capstones(lessons):
        if l.meta.module <= 0:
            offenders.append((l.meta.id, "no module: declared in frontmatter"))
        elif last_by_module[l.meta.module].meta.id != l.meta.id:
            offenders.append(
                (
                    l.meta.id,
                    f"module {l.meta.module} ends with "
                    f"{last_by_module[l.meta.module].meta.id}",
                )
            )
    assert not offenders, (
        f"capstones that are not their module's last lesson: {offenders}"
    )


def test_every_capstone_ends_on_a_synthesis_quiz(lessons):
    """The capstone's final quiz must test synthesis, not recall (authoring
    prompt: capstone quizzes "need at least two of the module's lessons to
    answer"). The authored declaration of that contract is the `synthesis`
    tag; a capstone without it — or with no quiz at all — either skipped the
    synthesis quiz or forgot to declare it. Both need a deliberate look."""
    offenders = []
    for l in _cr054_capstones(lessons):
        if not l.quizzes:
            offenders.append((l.meta.id, "capstone has no quiz at all"))
        elif "synthesis" not in l.meta.tags:
            offenders.append(
                (l.meta.id, 'tags missing "synthesis" — declare the synthesis quiz')
            )
    assert not offenders, f"capstones without a declared synthesis quiz: {offenders}"
