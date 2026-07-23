<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR053-MIGRATE — assign (migrate bare "lesson NNN" refs → tags / codes)

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md (§2.2 the gap, §3.4 the design decision, §5 Phase 2 migration bullet + Guards)
DEPENDS-ON: CR053-BE (the `<Lesson id/>`→`{{lesson:}}` tag + resolve guard must exist and be integrated first)
GATE: none    <!-- normalized CR070 (was: content review (Architect)) — free-text GATE was never machine-parsed -->
HOT-FILES: content/lessons/*.en.mdx (117 files), content/daily_challenges/2026_*.json (prose refs)

**What:** Close directive #1 — migrate the bare-number cross-references the app can no longer show (CR044
switched the visible id to the group code) to the identifiable/linkable forms. Do this with a **committed
migration script** (like `scripts/shuffle_quiz_answers.py`: textual, in-place, idempotent, re-runnable), NOT
by hand-editing 150 files. TWO reference classes, DIFFERENT mechanisms:

**A. Lesson bodies → `<Lesson id="NNN"/>` MDX tag. TWO ref classes — the architect measured the corpus
(now 334 lessons, up from the doc's 270) and they MUST be disambiguated or the migration corrupts links:**

  **Class 1 — GLOBAL-ID refs (~235): safe, the primary migration.** A "lesson NNN" where the number is
  written 3-digit / zero-padded ("lesson 039", "Lesson 010", "lesson 014 (Position sizing basics)",
  "lesson 070") OR its value is ≥16 and, zero-padded to 3 digits, matches a real `content/lessons/<NNN>_*.en.mdx`.
  → replace with `<Lesson id="NNN"/>` (3-digit id). When a title already trails in parens, KEEP the title text
  and tag the number. Ranges ("lessons 007–011") → tag each endpoint (or expand); never mangle the sentence.

  **Class 2 — WITHIN-MODULE ORDINALS (~51, almost all in the new lessons 293–356): DO NOT tag as id="N".**
  A **bare 1–2 digit** "lesson N" (value ≤15, NOT zero-padded) inside a lesson that carries a CR044 `code`
  (prefix P) is a *within-module ordinal*: "lesson 4" in a lesson coded **MACRO 6** means **MACRO 4**, NOT
  global id 004. Resolve it via the same-prefix code map: build `code → id` from every lesson's frontmatter,
  then "lesson N" in a lesson with prefix P → the lesson coded "P N" → tag THAT lesson's global id
  (`<Lesson id="326"/>` renders "MACRO 4"). **If no same-prefix "P N" lesson exists, DO NOT guess — leave
  the text and add it to a flagged list in the report.** (Tagging "lesson 4" as id="004" would pass the
  resolve guard yet link the WRONG lesson — the resolve guard can't catch this, so the same-prefix
  resolution must be correct by construction. This is the single riskiest part of the lane.)

  **Never** rewrite a number that isn't a lesson ref (dates "in 2024", prices "$135", quiz option indices,
  frontmatter, "the 3 ratios"). Conservative + auditable.

  **MANDATORY dry-run report (for architect review BEFORE trusting the apply):** the script runs in a
  `--dry-run` mode first and writes `content/_authoring/cr053_migration_report.md` listing EVERY edit as
  `file | class | before → after`, plus a FLAGGED section (Class-2 refs with no same-prefix match, ranges,
  anything ambiguous). Commit this report alongside the migration so the architect content-review reads the
  edit plan, not just the diff.

  **Guard (ships with this migration):** extend `test_lesson_corpus_integrity.py` — **no bare zero-padded
  `\blesson\s+0\d\d\b` and no `\blesson\s+(1[6-9]|[2-9]\d|\d{3})\b` (i.e. no un-tagged GLOBAL-id ref)
  remains in any lesson body**, except an explicit allowlist. Do NOT forbid bare "lesson N" (N≤15) — those
  are legitimately within-module ordinals now converted to tags; a blanket ban would false-positive. Combined
  with CR053-BE's resolve guard (every `{{lesson:}}` resolves), the corpus is self-policing for Class 1.

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

ASSIGNED: noncoder.edu round 1
DISPATCH: ACCEPTED (round 1)

<!-- Accepted 2026-07-22 by architect (round 1): content review PASS on migration commit 320bf45 +
hand-off 1b27363. I re-ran the guards myself: test_lesson_corpus_integrity + test_daily_challenge_service
= 35 passed exit 0. DEEP REVIEW of content/_authoring/cr053_migration_report.md (327 lesson-body edits, 0
flagged, 33 daily): CLASS-2 (57 within-module ordinals) all resolved CORRECTLY via same-prefix code — 328
(MACRO 6) "lesson 4"→326 (MACRO 4, leading/coincident/lagging), NOT 004; SHARIA 349 "lesson 2"→348; every
one maps to the right same-track lesson, zero misresolved-to-global. Independent sweep: ZERO bare global
refs remain in any lesson body. **Worker's key catch (correct + necessary):** tagged with the FULL
frontmatter id (id="039_the_pe_ratio") not bare 3-digit — because CR053-BE's resolve guard + the mobile
_findLessonMetaById both key on LessonMeta.id (the full string); bare "039" would fail the guard and
degrade to plain text on device. My lane examples said bare 3-digit — the worker was right, I was wrong.
Ranges + title-in-parens handled. Daily rewrites correct (lesson 070→EDGE 20, 063→N&M 5, prices/dates
untouched). Two trivial daily-prose residuals ("N&M 4 + 064", "EDGE 9 and 058" — trailing bare number a
converted code left behind) I fixed myself as reviewer touch-up (→ N&M 6 / EDGE 14), daily test re-green.
Commit = 141 files, all content/scripts/tests, no forbidden files. noncoder.edu freed. **CR053 FULLY DONE
(BE 36314f4 + MOBILE 921f15f + MIGRATE 320bf45).** NEXT: Wave-1 wrap (LESSON_COUNT_FLOOR + positional-ref
guard). Note follow-up: the mobile widget test fixture used a bare id "039" — production emits full ids;
test still valid (exact-match logic identical) but a fidelity nit to upgrade in Wave-1 wrap. -->

