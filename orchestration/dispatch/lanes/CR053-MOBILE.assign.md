<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR053-MOBILE — assign ({{lesson:}} chip + prerequisites render/link + tappable gateway rows)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md (§3.1 mechanisms, §4.2/§4.3 gateway UX, §5 Phase 1 + Phase 2 client bullets)
DEPENDS-ON: CR053-BE (the server must emit `{{lesson:ID}}` tokens — integrate BE first)
GATE: auditor.core (code lane)
HOT-FILES: mobile/lib/screens/lessons/lesson_reader_screen.dart, mobile/lib/screens/lessons/floor_screen.dart (coder.mobile owns)

**What:** Make cross-lesson references and agent-gateway rows tappable — the client half of CR053. THREE
pieces, ONE commit:

**1. `{{lesson:ID}}` inline chip — reader `_inline` tokenizer (lesson_reader_screen.dart:525-563).**
Add one alternative to the `pattern` RegExp (:527-528, beside `\{\{term:[a-zA-Z0-9_]+\}\}`) matching
`\{\{lesson:[a-zA-Z0-9_]+\}\}`, and one `else if (tok.startsWith('{{lesson:'))` branch beside the
`{{term:}}` branch (:536). The chip:
- **Label = the target lesson's CR044 code** ("FUND 8"), looked up by lessonId from the `LessonCatalogue`
  (`lessons_providers.dart` — the catalogue holds every `LessonMeta` with `codeLabel` + id). **Degrade
  loudly (CR040):** if the id doesn't resolve in the catalogue, render the raw id as plain text, NOT a dead
  tap. This satisfies directive #1 (shows the code, matching the tile badge).
- **Tap → `LessonReaderScreen(lessonId: <id>)`** — the same deep-link the daily-challenge/glossary/coach
  surfaces already push. Style it as a tappable inline chip (WidgetSpan), visually sibling to the term chip
  but distinguishable (it's a lesson, not a glossary term).

**2. Render + link `prerequisites` (surface A — data already parsed, reader just never shows it).**
The lesson's `prerequisites` (full lesson ids like `033_profit_and_margins`) are in `LessonMeta`. Add a
compact "Prerequisites" affordance to the reader (near the meta bar / top) listing each prereq as a tappable
chip — label = that lesson's CR044 code + title, tap → `LessonReaderScreen(lessonId:)`. Same catalogue
lookup + same degrade-loudly rule. Keep it unobtrusive when `prerequisites` is empty (render nothing).

**3. Locked-agent gateway rows tappable + CTA repoint (floor_screen.dart:201-225, 247-253) — directive #3.**
- Each gateway `Row` (the `for (final lesson in requiredLessons)` block) becomes a tap target
  (`InkWell`/`GestureDetector`) → `LessonReaderScreen(lessonId: lesson.lessonId)`. Today it names the lesson
  but does nothing on tap (§4.2 #1 — the single biggest friction).
- Repoint the primary progress CTA (:247-253 — the `next` unfinished gateway lesson is ALREADY computed via
  `firstWhere`) to deep-link **that lesson's reader**, not the track list the user must then search (§4.2 #2).
- Copy tweak if warranted (e.g. "Tap a lesson to start") — AMI by name, never "the AI"; reuse existing i18n
  keys where possible, add keys with context comments if new copy is needed.

**Contract check (CLAUDE.md degrade-loudly):** the `{{lesson:}}` token is produced by CR053-BE — verify the
chip renders against an ACTUAL backend response carrying the token (or a fixture mirroring BE's exact output
`{{lesson:039}}`), not an assumed shape.

**Constraints:** additive; do NOT break the existing `{{term:}}` / `<ChatWith>` / quiz rendering. Widget test:
a `{{lesson:039}}` token renders a tappable chip; an unresolvable `{{lesson:zzz}}` degrades to plain text (no
dead tap). `flutter analyze` clean.

**Self-test:** `cd mobile && flutter analyze` clean + `flutter test` for the new widget test green. (No
pytest — mobile lane.)

**Hand-off:** write `orchestration/dispatch/lanes/CR053-MOBILE.coder.mobile.md` `STATUS: READY_FOR_AUDIT
(round 1)` + `audit/handshake/cr/CR053-MOBILE.architect.md` + `SUBMITTED: round 1`. ONE commit, tag
`(AT:coder.mobile CR053)`, push origin main. Report commit sha + `flutter analyze`/`flutter test` results.

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED (round 1)

<!-- Accepted 2026-07-22 by architect: auditor.core VERDICT COMPLETE (round 1) on code 921f15f (verdict
a4aede0). I ALSO independently re-ran: flutter analyze = 5 pre-existing info issues, ZERO new (the two
floor_screen use_build_context_synchronously infos at :73/:313 are pre-existing async patterns outside the
changed hunks 197-288; new onTap handlers synchronous); flutter test = 37/37 passed incl the 2 new widget
tests. Read the tokenizer diff: {{term:}} alternative byte-UNCHANGED, {{lesson:}} appended; chip label =
meta.codeLabel via _findLessonMetaById(catalogue,id); tap → LessonReaderScreen(meta.id); absent id → plain
Text (no GestureDetector/InkWell) — CR040 degrade proven by the widget test's unresolvable {{lesson:zzz}}
case. Prerequisites = SizedBox.shrink() when empty else tappable code·title chips. Gateway rows InkWell →
reader, CTA repointed to next.lessonId. Commit = mobile/lib + app_en.arb + regenerated l10n + test only,
no forbidden files. coder.mobile freed. **Render branch is now shipped — CR053-MIGRATE content can safely
follow.** NEXT: CR053-MIGRATE (the last CR053 lane), with a dry-run-report review gate. -->

