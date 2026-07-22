<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR053-MIGRATE — assign (migrate bare "lesson NNN" refs → tags / codes)

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md (§2.2 the gap, §3.4 the design decision, §5 Phase 2 migration bullet + Guards)
DEPENDS-ON: CR053-BE (the `<Lesson id/>`→`{{lesson:}}` tag + resolve guard must exist and be integrated first)
GATE: content review (Architect)
HOT-FILES: content/lessons/*.en.mdx (117 files), content/daily_challenges/2026_*.json (prose refs)

**What:** Close directive #1 — migrate the bare-number cross-references the app can no longer show (CR044
switched the visible id to the group code) to the identifiable/linkable forms. Do this with a **committed
migration script** (like `scripts/shuffle_quiz_answers.py`: textual, in-place, idempotent, re-runnable), NOT
by hand-editing 150 files. TWO reference classes, DIFFERENT mechanisms:

**A. Lesson bodies (238 refs across 117 files) → `<Lesson id="NNN"/>` MDX tag.**
- Bare prose refs ("lesson 039", "the math from Lesson 010", "023 (support and resistance)") become
  `<Lesson id="039"/>` etc. The reader renders these as tappable chips showing the CR044 code (CR053-MOBILE).
- Handle the forms the audit found: `lesson 0?\d\d`, `Lesson NNN`, `NNN (title)`, and **ranges** ("lessons
  007–011", "lessons 007-011") — expand a range to individual tags or tag the endpoints; do NOT mangle the
  sentence. When a ref already carries a title in parens ("lesson 014 (Position sizing basics)"), keep the
  title text and tag the number.
- **Never** rewrite a number that isn't a lesson ref (dates "in 2024", prices "$135", quiz option indices,
  frontmatter). The script must be conservative + auditable — print every edit (file, before→after).
- Add the strict guard NOW (ships with this migration): extend `test_lesson_corpus_integrity.py` — **no bare
  `\blesson\s+\d{2,3}\b` (case-insensitive) remains in any migrated lesson body**, except an explicit
  allowlist for intentional non-link prose. Combined with CR053-BE's resolve guard, this makes the corpus
  self-policing.

**B. Daily-challenge prose (41 refs) → CR044 code string + structured `related_lesson`.**
- Daily challenges are **plain-text JSON, NOT MDX** — `<Lesson/>` tags will NOT render there. So for the 41
  bare "lesson NNN"/"Module N" refs in scenario/question/options/explanation: **rewrite the visible text to
  the CR044 code** ("FUND 8") for identifiability (§3.4 — make the sentence say what the tile says).
- Where a challenge centres on one specific lesson, also **set/verify its `related_lesson`** structured field
  (the daily-challenge card already deep-links it — that's the tap target). Don't invent a related_lesson
  where the ref is incidental.
- The id→code map comes from loading the lesson corpus in the script (each lesson's frontmatter `code`).

**Constraints:** AMI by name; do NOT touch verified quiz numbers/answers or P2 figures; frozen CR044 codes;
the script is the artifact (commit `scripts/migrate_lesson_refs.py` or similar). Idempotent — running twice
is a no-op (don't double-tag). Preserve every lesson's meaning; a migration that garbles a sentence fails
review harder than an un-migrated ref.

**Self-test (headless one-shot — TARGETED, NOT the full suite / P7):**
`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py tests/unit/test_daily_challenge_service.py -q`
green (exit 0) — proves every `{{lesson:}}` resolves (BE guard) AND no bare ref remains (this lane's guard).
Report the edit count (how many refs migrated in each class) + the two guard results.

**Hand-off:** write `orchestration/dispatch/lanes/CR053-MIGRATE.noncoder.edu.md` `STATUS: READY_FOR_REVIEW
(round 1)` + manifest (refs migrated A/B, files touched, script path, guard exits). ONE commit (script +
migrated content + guard), tag `(AT:noncoder.edu CR053)`, push origin main. Verified by git + exit code.

ASSIGNED: (held — launches after CR053-BE integrates)
DISPATCH: OPEN
