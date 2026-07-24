<!-- dispatch assign lane — Architect-owned. CR052. CR087 mobile sub-lane. -->
# CR087-MOBILE — assign (thread locale into lesson-detail fetch + RTL verify)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR087_lesson_locale_serving/CR087_lesson_locale_serving.md (§Scope → CR087-MOBILE, §Acceptance)
DEPENDS-ON: CR087-BE    <!-- needs the `?locale=` response shape from the backend before fromJson re-verification. Scaffolding the getLesson signature + wiring the locale source can start in parallel; the fromJson re-verify waits for CR087-BE READY_FOR_AUDIT. -->
GATE: independent    <!-- D-5: store-facing. -->
HOT-FILES: `mobile/lib/services/api/api_client.dart` (`getLesson` :484 — no locale today; `lessonCatalogue` :475 already passes it), the lesson-detail screen/state that calls `getLesson`, `mobile/lib/i18n/locale_provider.dart` (`localeNotifierProvider` — the active locale source). Serialize `api_client.dart` edits internally (single owner).

## Build

1. **`getLesson(lessonId, {String locale = 'en'})`** → `GET /v1/lessons/$lessonId?locale=$locale`.
   Thread the **active locale** (from `localeNotifierProvider`, same value the catalogue call
   already uses) through to the lesson-detail open — do not hard-code, do not read the SDK/system
   locale separately (must match the catalogue's locale so list ↔ detail agree).
2. **Contract re-verify (MANDATORY — CLAUDE.md degrade loudly):** the backend↔mobile mirror is
   hand-written, NOT type-enforced. Before `READY_FOR_AUDIT`, re-verify `Lesson.fromJson` (and
   nested blocks/quiz) against **actual CR087-BE `?locale=ar` JSON**, not the spec — a rename is
   masked by `?? default`.
3. **RTL:** MaterialApp sets `Directionality` to RTL when locale is `ar` (`app.dart`). Confirm the
   lesson **body + quiz** actually render right-to-left and that no hard-coded `TextDirection.ltr`
   / `EdgeInsetsDirectional`-ignoring layout breaks it. Fix any LTR assumption in the lesson view.
4. **EN fallback is invisible to the client** — the backend returns EN body for an AR-missing
   lesson (31 exist); the app just renders whatever it got. No client-side "missing translation"
   branch needed; don't invent one.

## Out of scope
Backend loader/serving (CR087-BE). Glossary/coach/daily-challenge screens. MS. Language switcher
(already built, A11). New translations.

## Tests
Widget tests (follow the existing mobile pattern): Arabic catalogue renders; lesson detail shows
the AR body when locale=ar; quiz submit works under AR; EN fallback lesson renders without error.
Re-verify `fromJson` against real backend JSON before audit. `flutter test` green.

## Delivery
Push to `lane/CR087-MOBILE.coder.mobile`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR087-MOBILE.coder.mobile.md` (`STATUS: READY_FOR_AUDIT (round 1)`)
+ `orchestration/audit/cr/CR087-MOBILE.architect.md` (`SUBMITTED: round 1`). Commit tag
`(AT:coder.mobile CR087)`.

DISPATCH: OPEN

ASSIGNED: coder.mobile round 1
