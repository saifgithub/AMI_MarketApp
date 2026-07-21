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
# ethics_integrity) hold zero lessons at Wave 0 — the contiguity + prefix-
# matches-track assertions above therefore have nothing to check for them. This
# section is the enforcement floor until Wave 1 fills the tracks: it asserts
# each new track is declared in the `Track` enum AND wired into both maps with
# the frozen CR044 prefix, that no prefix collides with any existing one, and
# that the display/prefix maps are 1:1 keyed to the `Track` enum. Anything
# thinner and a wave-1 author could ship an "ASST 1" badge that renders empty.


CR054_NEW_TRACKS = {
    "asset_classes": "ASST",
    "economics_macro": "MACRO",
    "quant_methods": "QUANT",
    "ethics_integrity": "ETHIC",
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


def test_cr054_new_tracks_are_empty_at_wave_0(lessons):
    """Wave 0 wires the tracks; Wave 1 fills them. If a lesson lands in a new
    track before Wave 1's author pipeline is in place, the CR044 code
    contiguity guarantee could break mid-authoring — fail loudly here so the
    stray lesson is noticed at build time, not from a user report."""
    stray = [
        (l.meta.id, l.meta.track)
        for l in lessons
        if l.meta.track in CR054_NEW_TRACKS
    ]
    assert not stray, (
        f"CR054 new tracks are Wave-0 empty; found lessons already in them: {stray}"
    )
