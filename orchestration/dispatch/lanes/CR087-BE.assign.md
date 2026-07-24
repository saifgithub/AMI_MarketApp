<!-- dispatch assign lane — Architect-owned. CR052. CR087 backend sub-lane. -->
# CR087-BE — assign (lesson locale serving: loader + get(id,locale) + ?locale= API)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR087_lesson_locale_serving/CR087_lesson_locale_serving.md (§Scope → CR087-BE, §Acceptance)
DEPENDS-ON: —
GATE: independent    <!-- D-5: store-facing (AR ships to public tracks). -->
HOT-FILES: `backend/app/services/lessons_service.py` (loader `_reload` :344, `catalogue` :352, `get` :373, `submit_quiz` :432), `backend/app/api/lessons.py` (`get_lesson` :181), `backend/app/schemas/lessons.py` (Lesson/LessonMeta — only if a field is genuinely needed; prefer none). `backend/tests/unit/` new test file. coder.api is sole schema owner — but NO schema/migration change is expected here (content-only feature).

## Build

1. **Loader (`_reload`)** — keep globbing `*.en.mdx` as the canonical lesson set. For each EN
   lesson, additionally look for `{stem}.ar.mdx` and `{stem}.ms.mdx` siblings; parse each with
   the existing `parse_mdx`. Store per-locale bodies — e.g. `self._lessons: dict[str, dict[str,
   Lesson]]` keyed `id → locale → Lesson`, or a parallel `self._locale[(id, locale)]`. On a
   locale file that fails to parse: `logger.error` and skip that locale (never crash the load,
   never drop the EN lesson).
2. **Auto-derive `locale_versions`** — a lesson's available locales = the set of sibling files
   that actually parsed (`en` always present). Override whatever the EN frontmatter said
   (`["en"]`). Do NOT hand-edit the 342 EN frontmatters.
3. **EN meta stays canonical** — `id, track, code, agent_callouts, gates_agents, prerequisites,
   difficulty, module, duration_min` come from the EN lesson. Only display fields (title, blocks,
   quizzes) come from the locale file. (Guards earn-path/catalogue against EN↔AR meta drift.)
4. **`get(lesson_id, locale="en")`** — return the locale body; **fall back to EN** when the
   locale is absent (a loud, correct fallback — user sees English, not a 404/empty). Update the
   `get_lesson` API (`api/lessons.py:181`) to accept `locale: str = "en"` and pass it through.
5. **`catalogue(locale)`** already filters on `locale_versions`; once the loader populates it,
   `?locale=ar` returns the AR-available lessons. Verify, don't rewrite.
6. **Quiz integrity (MANDATORY — CLAUDE.md degrade loudly):** `submit_quiz` grades against
   `answer_index`. A translator who reordered options silently mis-grades AR users. Grade against
   the **served locale's** parsed quiz. AND add a corpus test asserting, per lesson that has an
   AR file, that AR and EN have the **same quiz count and identical `answer_index` per question**
   — fail the build on drift (this is the real risk in translated MCQs).

## Out of scope
Glossary/coach/daily-challenge locale (CR083 Tier 2). MS enablement. Any schema/migration. New
translations. Mobile (CR087-MOBILE).

## Tests
New `backend/tests/unit/test_cr087_lesson_locale.py`: loader loads AR variants; `catalogue("ar")`
non-empty; `get(id, "ar")` returns Arabic title/body; `get(id, "ar")` for an AR-missing lesson
returns EN (fallback); `get_lesson` endpoint honors `?locale=`; AR/EN quiz answer_index parity
across the corpus; submit_quiz grades correctly under `locale="ar"`. Full unit suite stays green
(`pytest backend/tests/unit/ -q`, sqlite tempfile, ~130s).

## Delivery
Push to `lane/CR087-BE.coder.api`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR087-BE.coder.api.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR087-BE.architect.md` (`SUBMITTED: round 1`, with adversarial-focus
notes: quiz answer_index parity, EN-fallback path, meta-canonical correctness). Commit tag
`(AT:coder.api CR087)`.

DISPATCH: ACCEPTED (round 1)

ASSIGNED: coder.api round 1

<!-- INTEGRATED 2026-07-24: coder.api build abcc08b independently audited COMPLETE (round 1). The
auditor disabled `_locale_quiz_servable` against the real corpus and got dozens of genuine
answer_index mismatches — proving the serving-time gate is load-bearing (the assign's build-time
parity test would have sat permanently red on the damaged CR083 corpus); deviation accepted. Clean
checkout of the 4 BE files onto main (merge-base 487f94e, no code divergence), full unit suite 1116
green. Lane closed → 55d54e4. -->

