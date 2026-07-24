<!--
CR087-BE.architect.md — architect lane file (Architect owns). State derives from the round
numbers here vs CR087-BE.auditor.md. Bump `SUBMITTED: round N` on every resubmit.
Do NOT edit CR087-BE.auditor.md — that is the independent auditor's file.

GATE: independent. Routed to the pre-spawned independent auditor (track U). If none is running, the
lane HOLDS here (the Architect does not spawn its own auditor — separation of duties).
-->

# CR087-BE — audit lane (architect)

**Item:** CR087-BE — make the CR083 AR/MS translated lesson bodies reachable: loader parses
`{stem}.{ar,ms}.mdx` siblings, `get(id, locale)` serves the locale body with loud EN fallback,
`GET /v1/lessons/{id}?locale=`, quiz graded against the served locale. Backend half of CR087.

**Gate:** independent (D-5 — store-facing: AR ships to public tracks). Verify adversarially: a
damaged AR quiz must NEVER be served (fall back to EN); grading uses the served locale; EN meta
stays canonical; EN fallback never 404s.

**Built SHA (round 1):** code `abcc08b`, hand-off `eb271b6` on `lane/CR087-BE.coder.api`. Merge-base
with main = `487f94e` = **current main HEAD**, so the lane fast-forwards clean (no divergence, the
5-file diff IS the whole changeset). Not yet integrated.

**depends-on:** —. (CR087-MOBILE depends on THIS; mobile already audited **COMPLETE r1**.)

## What changed / why

| File (+/−) | What |
|---|---|
| `lessons_service.py` (+148/−8) | `_reload` also parses `.ar/.ms` siblings; per-locale map `id→locale→Lesson`; auto-derives `locale_versions` from what parsed+passed the integrity gate (no EN-frontmatter edits); EN meta canonical, only display fields localized; `get(id, locale)` EN-fallback; `submit_quiz` grades the served locale. |
| `api/lessons.py` (+5/−1) | `get_lesson` accepts `locale: str = "en"`. |
| `schemas/lessons.py` (+6) | `QuizSubmitRequest.locale: str = "en"` (grade the taken locale; back-compat default). |
| `test_cr087_lesson_locale.py` (+371 new) | loader variants, catalogue(ar), get(ar) + EN fallback, endpoint `?locale=`, AR/EN answer_index parity, submit under AR. |

## Architect pre-check (done before submitting — NOT the independence gate)

- **Scope / forbidden paths:** diffed vs merge-base `487f94e`. **5 files: 3 backend + 1 test + the
  coder's hand-off lane.** No `content/lessons/**`, no alembic/migration, no `docker-compose.yml`, no
  `mobile/**`, no `.claude/settings.local.json` / `uv.lock` / `Archive.zip`. No schema/DB change. Not on `main`.
- **Full unit suite:** re-run independently by me in a throwaway worktree at `eb271b6` (`uv sync
  --extra dev`) → **1 failed, 1115 passed (134s)**. The single failure is
  `test_registers_no_drift::test_registers_match_their_row_files` — a **pre-existing DEF098 ID
  collision** in `def_list.md` (a content-track register bug, unrelated to CR087; confirmed present
  at merge-base with `def_list.md` untouched by this lane). Everything CR087 touches is green; the
  new test file alone = 17 passed.
- **Code reviewed:** the loader composition (EN meta + localized display), the EN-fallback in
  `get()`, and the served-locale grading are correct. The shared `available` list aliasing into every
  composed meta is intentional and sound (fresh list per lesson, no cross-lesson bleed).

## ⚠ DEVIATION — needs your explicit sign-off

The assign scoped the quiz guard as a **build-time parity test that fails on drift.** The coder found
that against the real corpus that test would sit **permanently red** — a chunk of the CR083 AR files
are structurally damaged (emptied `options`, reset `answer`). Per CLAUDE.md *"make it structural,"* it
instead added a **serving-time integrity gate** `_locale_quiz_servable(en, loc)`: a locale lesson is
served only if its quiz matches EN per-question on count, option-count, and `answer_index` with no
empty option — **else the whole lesson falls back to EN (logged `lesson_locale_quiz_integrity_failed`).**
No AR user can get an unanswerable (DEF064 class) or mis-graded (DEF059 class) quiz; the suite stays
green without hiding the defect; the corpus test asserts the gate's invariant over *served* AR.

**I judge this a strict improvement over the spec** (structural, degrade-loudly, no user-facing
breakage) and accept it — but it changes the acceptance shape, so verify it adversarially, don't
rubber-stamp.

## Adversarial focus for the auditor
1. **Damaged AR quiz truly falls back to EN?** Mutate a locale lesson (empty an option / reorder
   answer_index) and confirm `get(id,"ar")` returns the EN body, not the broken AR one, and that the
   failure is logged.
2. **Grading uses the served locale** (`submit_quiz(req.locale)`), and a served AR quiz grades the
   same as EN (the gate guarantees answer_index parity).
3. **EN meta canonical** — a served AR lesson's `track/code/gates_agents/prerequisites` come from EN;
   only `title`/blocks/quizzes are localized.
4. **EN fallback never 404** for a real lesson lacking a translation (31 AR-missing lessons exist).
5. **`catalogue("ar")`** returns only servable-AR lessons (parsed + gate-passed), with translated titles.

## Context (not a CR087 blocker) — AR content quality
The coder measured the tracked 312 AR files: **~276 serve clean; ~36 fall back to EN** (18 parse-fail
+ 18 quiz-corrupt from CR083 translation tooling breaking MDX around `<Lesson/>` tags). AR effective
coverage ≈ **276/342 ≈ 81%**, all logged. This is a **CR083 content defect** to fix separately — the
serving gate degrades it gracefully; it does not block CR087-BE correctness.

SUBMITTED: round 1
