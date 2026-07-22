<!-- dispatch hand-off — coder.mobile. CR053-MOBILE. -->
# CR053-MOBILE — coder.mobile hand-off

STATUS: READY_FOR_AUDIT (round 1)

COMMIT: 921f15ff686907656ca58b65315c6c2d14e140da (pushed to origin/main)

## Manifest

- `mobile/lib/screens/lessons/lesson_reader_screen.dart`
  - `_inline` tokenizer: added `\{\{lesson:[a-zA-Z0-9_]+\}\}` alternative to the
    `pattern` RegExp (beside `{{term:}}`), and an `else if (tok.startsWith('{{lesson:'))`
    branch beside the `{{term:}}` branch.
  - New `_InlineLessonChip` (ConsumerWidget) — label = target lesson's CR044
    `codeLabel` looked up via a flat scan of `lessonsNotifierProvider`'s
    catalogue (`_findLessonMetaById`); tap → `LessonReaderScreen(lessonId:)`.
    Unresolved id → plain `Text(lessonId, ...)`, no tap target (CR040).
  - New `_PrerequisitesRow` + `_PrerequisiteChip` — renders `lesson.meta.prerequisites`
    (already parsed, never surfaced) as tappable chips (code + title) under the
    meta bar; renders nothing when the list is empty. Same lookup + same
    degrade-loudly rule.
- `mobile/lib/screens/floor/floor_screen.dart`
  - Each gateway `Row` (the `for (final lesson in requiredLessons)` block) is
    now wrapped in `InkWell` → `LessonReaderScreen(lessonId: lesson.lessonId)`.
  - Progress CTA (`next` — the first unfinished gateway lesson, already
    computed via `firstWhere`) now deep-links `LessonReaderScreen(lessonId: next.lessonId)`
    instead of `TrackLessonsScreen(trackId: next.track)` (import swapped
    accordingly; `track_lessons_screen.dart` import removed, now unused here).
  - Added a small copy line above the gateway list (`floorLockedTapHint`,
    "Tap a lesson to start").
- `mobile/lib/l10n/app_en.arb` — new keys `lessonReaderPrerequisites`
  ("PREREQUISITES") and `floorLockedTapHint`. `ar`/`ms` left untranslated —
  `l10n.yaml`'s `nullable-getter: false` + missing-key-falls-back-to-English
  behavior confirmed via `flutter gen-l10n` (103/104 untranslated messages
  reported for ar/ms, pre-existing pattern, not a regression).
  `mobile/lib/generated/l10n/app_localizations*.dart` regenerated via
  `flutter gen-l10n` and committed (required for `flutter analyze`/`flutter test`
  to see the new getters).
- `mobile/test/widgets/lesson_reader_lesson_chip_test.dart` (new) — widget test:
  a `{{lesson:039}}` token resolves against a fixture catalogue and renders a
  tappable chip labeled "FUND 8" (tap pushes a second `LessonReaderScreen`);
  a `{{lesson:zzz}}` token degrades to plain text `zzz` with no
  `GestureDetector`/`InkWell` ancestor (no dead tap).

## Self-test (actual output, not claimed)

`cd mobile && flutter analyze`:
```
7 issues found → after `flutter gen-l10n` regeneration + super-parameter fix: 5 issues found.
```
All 5 remaining are pre-existing and unrelated to this change (confirmed via
`git stash` diff against HEAD before this commit — same 5, same files/lines,
modulo one line-number shift in `floor_screen.dart` from the new code above
it): 2× `deprecated_member_use` in `lib/main.dart:69`, 2×
`use_build_context_synchronously` in `floor_screen.dart` (pre-existing,
lines 73 and 313 — 313 was 295 before this commit's insertions), 1×
`use_super_parameters` in `test/widgets/sign_in_email_disclosure_test.dart:27`
(pre-existing, not this lane's file). Zero issues introduced by this change.

`cd mobile && flutter test`:
```
00:09 +37: All tests passed!
```
Full suite (37 tests across all widget test files), including the 2 new
tests in `lesson_reader_lesson_chip_test.dart`. Zero regressions.

## Contract check

Verified against CR053-BE's actual token shape `{{lesson:039}}` (id-keyed,
3-digit zero-padded in the example, but the regex accepts any
`[a-zA-Z0-9_]+` id per the BE contract) — both in the widget test fixture and
by construction (the regex/branch mirror the `{{term:}}` handling exactly,
which is already proven against live BE output).

## Additive check

`{{term:}}` tokenizing verified unchanged: the new regex alternative is
appended, not substituted; existing `_InlineTermChip` branch untouched;
`lesson_animation_test.dart` (animation blocks) and the full suite above
both pass, confirming no regression to `<ChatWith>`/quiz/animation
rendering.
