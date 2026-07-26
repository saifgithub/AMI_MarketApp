# DEF111 — Daily challenge "related lesson" 404s 100% of the time (bare-numeric id vs real lesson id)

**Status:** resolved · **Filed + fixed:** 2026-07-27 (AT:R65)
**Source:** user bug report `34861dc8` (iOS, app 0.1.0+51) — "after reading then daily
lesson, and selecting the related lesson I got this error" (`Lesson load failed:
DioException [bad response]: ... 404`).

## What

Every `related_lesson` field across the daily-challenge content corpus
(`content/daily_challenges/**/*.json`, canonical + `ms`/`ar` overlays) was authored
as the bare 3-digit CR018 display/reference number (e.g. `"045"`) instead of the
real lookup key `LessonsService.get()` uses — the full lesson id/slug (e.g.
`"045_greed"`, matching `content/lessons/045_greed.en.mdx`'s frontmatter `id`).

`LessonsService.get()` (`backend/app/services/lessons_service.py:496-506`) is an
exact dict-key lookup with no numeric-prefix fallback, so `GET /v1/lessons/045`
404s unconditionally. `backend/app/api/lessons.py:181-192` turns that into a 404
HTTP response; the mobile client's `LessonReaderNotifier.load()`
(`mobile/lib/state/lessons_providers.dart:162-176`) surfaces it verbatim as
"Lesson load failed: $e" — the exact string in the bug report.

**Scope: 100% of the corpus, not an edge case.** Verified independently: 573/573
`related_lesson` occurrences across all 21 corpus files (7 monthly files × EN/MS/AR)
were in the wrong (bare-numeric) form; 0 were correct. Every tap on a "related
lesson" link anywhere in the app has always 404'd.

## Why it survived

`daily_challenge_card.dart:335` is the **only** lesson-linking call site in the app
that hands a content-authored ad-hoc string straight to `LessonReaderScreen`
without resolving it through catalogue metadata first — every other call site
(`lesson_reader_screen.dart:640,729`, `track_lessons_screen.dart:104,110`) passes
the real `meta.id`. The daily-challenge authoring content was evidently written
using the CR018-style bare reference number (the human-facing display number,
matching the `EDGE 49`-style badge convention), not the real id, and nothing
validated `related_lesson` against the lesson corpus at authoring or load time.

## Fix

- Rewrote all 573 `related_lesson` values across the 21 corpus files from the bare
  numeric prefix to the real lesson id, via a deterministic mapping built from
  `content/lessons/*.en.mdx` filenames (`NNN_slug.en.mdx` → `NNN_slug`). Every
  referenced prefix (70 distinct) resolved cleanly to a real lesson — zero
  orphaned references, so no content had to be dropped or guessed at. Targeted
  string substitution (not a full JSON re-serialize) to keep the diff to exactly
  the 573 changed values with no incidental reformatting.
- Added `test_every_daily_challenge_related_lesson_resolves` to
  `backend/tests/unit/test_lesson_corpus_integrity.py` — asserts every
  `related_lesson` in the corpus resolves to a real lesson id, so the bare-numeric
  form (or any future typo) fails the build instead of shipping silently.

## Verification

- `pytest backend/tests/unit/test_lesson_corpus_integrity.py -q` — 25 passed
  (24 pre-existing + the new guard).
- Full suite `pytest backend/tests/unit/ -q` from repo root — 1261 passed (1260
  pre-existing + the new guard), unrelated to the pre-existing register-drift
  state from a concurrent session's in-flight CR097 work.
- All 21 modified JSON files independently re-parsed to confirm well-formed JSON
  post-edit.

## Acceptance

- `GET /v1/lessons/<related_lesson>` resolves for every daily-challenge entry in
  the corpus (verified via the guard test, not spot-checked).
- A future mis-authored `related_lesson` fails the backend test suite rather than
  shipping to users.
