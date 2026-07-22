STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR053-BE. State machine driven by the STATUS line above (byte-exact). See orchestration/dispatch/loop_prompts/CODER.md. -->

# CR053-BE — coder.api lane

**Item:** cut the server seam for cross-lesson quick-links — `<Lesson id="..."/>` → `{{lesson:...}}` inline token substitution, mirroring the existing `<Term>`→`{{term:}}` treatment exactly, plus the resolve guard (degrade-loudly, CR040). Mechanism + guard only — content migration is CR053-MIGRATE, the mobile chip is CR053-MOBILE.

**Spec:** [`docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md`](../../../docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md) §3.1.3, §5 Phase 2 server bullet, §5 Guards.

**What/why:** `<Lesson id="039"/>` inside a lesson's prose now substitutes to the inline token `{{lesson:039}}`, riding within its surrounding markdown block instead of being promoted to a standalone block — identical treatment to `{{term:}}`. The token is id-keyed; `parse_mdx` sees one file at a time and has no global id→code map, so CR044 code resolution for the chip label happens client-side (CR053-MOBILE).

**Changed:**
- `backend/app/services/lessons_service.py` — added `_LESSON_RE` beside `_TERM_RE`, added `_inline_lesson_tokens()` mirroring `_inline_term_tokens()`, called it in `parse_mdx` immediately after the existing `body = _inline_term_tokens(body)` line. Purely additive — `_inline_term_tokens`, `_TERM_RE`, `_CHATWITH_RE`, `_ANIMATION_RE` and all existing signatures untouched.
- `backend/tests/unit/test_lesson_corpus_integrity.py` — new `test_every_lesson_token_resolves_to_a_real_lesson_id`: every `{{lesson:ID}}` token produced across the whole corpus must resolve to a real `content/lessons/<ID>_*.en.mdx`, failing loudly and listing dangling ids. Passes vacuously today (zero `<Lesson/>` tags pre-migration) — arms the guard for CR053-MIGRATE. No "no bare lesson NNN remains" assertion added (that ships with the migration lane).
- `backend/tests/unit/test_lessons_service.py` — new `test_lesson_inlines_lesson_tokens_into_prose`, cloned from `test_lesson_inlines_term_tokens_into_prose`'s shape: asserts `<Lesson id="039"/>` parses into a prose block containing `{{lesson:039}}` and that no standalone `lesson` block kind is emitted.

**Tests:** `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py tests/unit/test_lessons_service.py -q` → 41 passed, exit 0.

**Definition of Done:**

| Item | Status |
|---|---|
| `_LESSON_RE` + `_inline_lesson_tokens()` mirror `_TERM_RE`/`_inline_term_tokens()` exactly | done |
| Called in `parse_mdx` right after `_inline_term_tokens`, rides inside prose (not a standalone block) | done |
| Token id-keyed, no server-side id→code resolution | done |
| Resolve guard added to corpus-integrity test, passes vacuously pre-migration | done |
| Unit test cloned from `{{term:}}` shape | done |
| Existing substitution funcs/regexes/signatures untouched (additive only) | done |
| Targeted self-test green | done (41 passed, exit 0) |

**Auditor:** auditor.core.

SUBMITTED: round 1
