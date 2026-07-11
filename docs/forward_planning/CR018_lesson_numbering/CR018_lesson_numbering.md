# CR018 — Lesson numbering for easy reference

**Status:** done
**Filed:** 2026-07-11 (AT:R54)
**Source:** Saiful — "the lessons need to be numbered so that it can be referenced easily."

---

## What

Surface a **visible, stable lesson number** in the app so any of the ~270 lessons
can be referenced by a short handle (e.g. "Lesson 23") instead of only by title.

The number already exists — every lesson content file carries a 3-digit prefix in
its `id` (`001_what_is_a_stock`, `023_support_and_resistance`, …), assigned in the
canonical pedagogical order. Today that number is **not exposed to the client and
not shown in the UI**, so a user (or Saiful, or support) has no easy way to say
"go to lesson 23." This CR plumbs that existing number end-to-end and renders it.

## Why

- **270 lessons, title-only in the UI.** Referencing one in conversation, a bug
  report, support, or cross-lesson pointers ("prerequisite: lesson 14") is awkward
  without a number.
- The number is **already the source of truth** (the `id` prefix + file order), so
  this is a surfacing task, not a re-modelling one — low risk, high everyday value.
- Consistent with the analyst-to-analyst brand voice: a numbered curriculum reads
  as a structured course, not a loose pile of articles.

## Numbering scheme (decision)

Use the **existing numeric `id` prefix** as the canonical lesson number, displayed as
a `023` badge. The 270 lessons span prefixes `001`–`292` (the block `078`–`099` is
unused → the range is **gapped, not contiguous**). We surface the raw prefix, gaps
and all, **not** a recomputed 1..270 index. Rationale:

- **Stability beats contiguity for a reference code.** The prefix is permanent: "lesson
  023" means the same lesson forever. A recomputed 1..270 sequence would *shift* every
  time a lesson is inserted/removed/reordered, silently breaking every prior reference
  (a bug report saying "lesson 150" would drift). Gaps are cosmetic; stability is the
  whole point.
- Already unique and version-controlled (it's in the filename + `id`).
- **Zero content migration** — derived from the `id` prefix on the backend at load
  time; the 270 `.mdx` files are untouched (no new frontmatter field).

The number is a **stable reference code**, independent of whatever order a given list
view sorts by (the per-track list re-sorts by completion tier; the badge always shows
the lesson's canonical number).

## Scope

**In:**
- Backend: expose the numeric prefix as an explicit field (e.g. `number: int`) on the
  lesson schema/response, derived from the `id` prefix at load time (no content edit
  needed). Keep the string `id` as the primary key everywhere else.
- Mobile model: parse the new `number` field.
- Mobile lessons **list card**: show the number as a mono badge/prefix.
- Mobile lesson **reader header**: show the number alongside the title.
- Tests: backend derivation + a mobile widget assertion if the lessons screen has
  coverage.

**Out:**
- Renumbering or reordering lessons; changing the `id` scheme.
- Per-track / per-module compound numbering (rejected — global 001–270 is simpler to
  reference). Can revisit if Saiful wants track-scoped labels later.
- Localisation of the word "LESSON" beyond the existing i18n mechanism (the number
  itself is locale-neutral).

## Acceptance

- Each lesson shows its canonical number (`001`–`270`) in both the lessons list and
  the opened reader, as a compact mono badge consistent with the hex design system.
- The number is stable per lesson and matches the `id` prefix.
- `flutter analyze` clean; backend unit tests green (+ derivation test).
- Referencing "lesson NNN" is now unambiguous in-app.

## Implementation (AT:R54, done)

Derived the number on the backend from the `id` prefix — **no content edit** (the 270
`.mdx` files are untouched):

- `backend/app/services/lessons_service.py` — new `lesson_number(id)` helper
  (`"023_x".split("_")[0]` → `23`; `0` if unprefixed); wired into `parse_mdx`'s
  `LessonMeta(...)`.
- `backend/app/schemas/lessons.py` — `LessonMeta.number: int = 0` (propagates through
  `Lesson`/`TrackCatalogue`/`LessonCatalogue` automatically).
- `backend/tests/unit/test_lessons_service.py` — `+test_lesson_number_derived_from_id_prefix`
  (helper cases + a parsed fixture). Verified live against the real content dir: all
  270 lessons derive a number, range 1–292, zero unprefixed.
- `mobile/lib/models/lessons.dart` — `LessonMeta.number` field + `fromJson` + a
  `numberLabel` getter (zero-padded `"023"`, or `"L{level}"` fallback for a legacy
  unprefixed id).
- `mobile/lib/widgets/lessons/lesson_tile.dart` — the 36×36 leading badge now shows
  `meta.numberLabel` (cyan mono); the level tier moved to the caption line
  (`"3 min · L2"`).
- `mobile/lib/screens/lessons/lesson_reader_screen.dart` — `_LessonMetaBar` badge shows
  the number; level trails the duration/track meta line.

Backend suite 590 green; `flutter analyze` clean. Ships on the next device build
(no backend promote strictly required, but a promote is harmless — the field is
additive). The reader `_Header` title bar was left as title-only; the number sits in
the meta bar directly beneath it.
