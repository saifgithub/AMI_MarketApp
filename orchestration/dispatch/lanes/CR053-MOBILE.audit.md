# CR053-MOBILE — Audit Verdict

VERDICT: COMPLETE (round 1)

Audited commit: `921f15f` (feat(lessons): {{lesson:ID}} chip + prerequisites render/link + tappable gateway rows)
Auditor: auditor.core · lane: MOBILE/Flutter (no backend pytest)

## Measurements
- `flutter analyze`: **5 issues, all `info`, ZERO new errors/warnings.**
  - `floor_screen.dart:73` + `:313` use_build_context_synchronously — PRE-EXISTING async patterns, outside the changed hunks; the new gateway `onTap`/`onPressed` handlers are synchronous (`pop()` + `push()`, no await) so add no warning.
  - `main.dart:69` (×2) deprecated `copyWith`, `sign_in_email_disclosure_test.dart:27` use_super_parameters — all pre-existing info.
- `flutter test`: **37/37 passed** (exit 0), including the 2 new widget tests. New file re-run standalone: 2/2 passed.

## Verification detail
1. **Reader tokenizer additive** — the `{{term:[a-zA-Z0-9_]+\}\}` alternative is byte-UNCHANGED; the `|\{\{lesson:[a-zA-Z0-9_]+\}\}` alternative is APPENDED to the pattern. Term chips still tokenize. `_InlineLessonChip` label = `meta.codeLabel` (CR044) via `_findLessonMetaById(catalogue, id)` LessonCatalogue lookup; tap pushes `LessonReaderScreen(lessonId: meta.id)`; an id absent from the catalogue returns `Text(lessonId, style: baseStyle)` — plain text, NO GestureDetector/InkWell (CR040 degrade-loudly). `codeLabel` getter (lessons.dart:134) returns `code` when non-empty → 'FUND 8'.
2. **Prerequisites** — `_PrerequisitesRow` renders `SizedBox.shrink()` when the list is empty; otherwise a header + `Wrap` of `_PrerequisiteChip` (code · title), each a GestureDetector deep-linking to the reader; `meta == null` → plain `Text(lessonId)`, same degrade rule. Rendered from `lesson.meta.prerequisites` (already parsed, never surfaced before).
3. **Floor gateway rows** — each `requiredLessons` row is now an `InkWell` with `onTap` → `pop()` + `push(LessonReaderScreen(lessonId: lesson.lessonId))`. Primary CTA repointed from `TrackLessonsScreen(trackId: next.track)` to `LessonReaderScreen(lessonId: next.lessonId)` (the next unfinished gateway lesson, via the existing `firstWhere`). New `floorLockedTapHint` string added.
4. **Widget test genuinely asserts both paths** — resolvable `{{lesson:039}}` → 'FUND 8' inside a GestureDetector; after tap, `LessonReaderScreen` findsNWidgets(2). Unresolvable `{{lesson:zzz}}` → plain 'zzz' with GestureDetector findsNothing AND InkWell findsNothing. `takeException()` isNull throughout.

## Scope
`git show 921f15f --stat` touches ONLY: `mobile/lib/screens/lessons/lesson_reader_screen.dart`, `mobile/lib/screens/floor/floor_screen.dart`, `mobile/lib/l10n/app_en.arb`, the 4 generated l10n files, and the new test `mobile/test/widgets/lesson_reader_lesson_chip_test.dart`. NO `backend/uv.lock`, `.claude/settings.local.json`, or `Archive.zip` in the commit (those are pre-existing uncommitted working-tree noise, not part of 921f15f).

All holds. COMPLETE.
