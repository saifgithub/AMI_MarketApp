SUBMITTED: round 1

<!--
CR054-GUARD.architect.md — coder-owned audit lane (delegated from track R architect to coder.api under CR052 dispatch). Opened AT:coder.api CR054-GUARD. State derives from round numbers here vs CR054-GUARD.auditor.md (see orchestration/audit/PROTOCOL.md).
-->

# CR054-GUARD — audit lane (coder.api)

**Item:** make the corpus guards content-addition-safe, so every Wave 1–3 content lane can land lessons without a `backend/` edit. Three changes, all inside `backend/tests/unit/test_lesson_corpus_integrity.py` (the only source file this lane touches): lesson-count exact pin → floor, retire the Wave-0 empty-track pin, add the capstone guard. Specs:
[`CR054-GUARD.assign.md`](../../dispatch/lanes/CR054-GUARD.assign.md), parent CR054 §5.1 ("every capstone is the last lesson in its module and its final quiz is synthesis"),
[`wave1_ethics.md`](../../../docs/forward_planning/CR054_investment_body_of_knowledge/wave1_ethics.md), the capstone template in `content/_authoring/lesson_authoring_prompt.md` ("Module capstone template (v2)"), and the Architect's A1 in [`CR054-W1-ETHIC.noncoder.edu.md`](../../dispatch/lanes/CR054-W1-ETHIC.noncoder.edu.md).

**depends-on:** none. This lane is the root unblock: W1-ETHIC (10 authored, deliberately-uncommitted Ethics lessons) is HOLDing on it, and every later Wave-1/2/3 content lane inherits the same unblock.

**Commit:** single-commit hand-off — this lane's commit (child of `e6aff3a`, tag `AT:coder.api CR054`) carries exactly 3 named paths: the test file, `orchestration/dispatch/lanes/CR054-GUARD.coder.api.md`, and this audit lane.

## What was done

1. **Lesson-count exact pin → floor.** `EXPECTED_LESSON_COUNT = 270` (asserted `==` in `test_every_lesson_parses`) became `LESSON_COUNT_FLOOR = 270` asserted `>=`. The guard's reason to exist — a malformed lesson silently vanishing from the catalogue because `LessonsService._reload()` swallows parse failures — is a *shrink*, and the floor still catches every shrink below the last integrated corpus. What it stops doing is turning red when content waves *append*, which is the whole point: an exact pin forces a backend edit into every content lane (the exact cross-ownership deadlock W1-ETHIC's Q1 escalated). The constant's comment instructs each integrating wave to bump the floor (it only ever grows, never returns to an exact pin), so the floor tracks the corpus and the shrink-detection window never widens permanently. Every file on disk still runs through `parse_mdx` — the parse-all loop is unchanged.

2. **Retired `test_cr054_new_tracks_are_empty_at_wave_0`.** Its own docstring scoped it as scaffolding ("the enforcement floor until Wave 1 fills the tracks"); Wave 1 is now filling them deliberately, so the pin's job is done and it would otherwise block every Wave-1 lane. Deleted, with a note in the section comment recording what it was and why it went (per the assign: delete or convert to comment). The `CR054_NEW_TRACKS` dict and the 5 other Wave-0 *wiring* guards (enum declaration, display names + prefixes, prefix uniqueness, titles↔prefix parity, enum↔maps parity) stay — wiring correctness is permanent, only the emptiness pin was temporal. Population correctness stays covered by the CR044 guards (`test_lesson_code_prefix_matches_its_track` + `test_lesson_codes_are_contiguous_within_each_track`), exactly as the assign notes.

3. **Added the capstone guard** — new "CR054-GUARD: capstone invariants" section, two tests over lessons whose `tags` contain `"capstone"`:
   - `test_every_capstone_is_the_last_lesson_in_its_module` — the capstone must hold the max id-derived `number` within its `module` (same ordering as the catalogue sort). A capstone with no `module:` declared (loader default 0) is its own offender case with a explicit message, rather than a confusing comparison against the module-0 legacy group.
   - `test_every_capstone_ends_on_a_synthesis_quiz` — the capstone must have at least one quiz and must declare the synthesis contract via the `"synthesis"` tag.
   - **Why the tag is the synthesis check:** `QuizQuestion` has no per-quiz type field (id/question/options/answer_index/explanation only), so "final quiz is a synthesis question" has no deeper structural encoding to assert against today. The `synthesis` tag is the authored, machine-checkable declaration (both real capstones carry it); whether the questions genuinely span the module is the content-review gate's judgement (wave lanes are Architect/Saiful-reviewed, not auditor-gated). Documented in the section comment — per CR038, this is the structural part of a control whose semantic part is human review.
   - **Legacy exemption `PRE_CR054_CAPSTONE_TAGS = {071_how_to_verify_before_you_wire_money}`:** lesson 071 (EDGE 21, module 11) carries an informal M11-era `"capstone"` tag, sits mid-module (M11 runs through lesson 267), and has no synthesis tag — it fails BOTH prongs. The authoring prompt is explicit: "Existing modules M1-M12 have no capstones. Do NOT retrofit them." Without the exemption the guard is red at HEAD, violating the lane's standalone constraint; with it, the guard applies to every capstone authored under the CR054 template from now on ("any lesson whose tags contains capstone", minus the one pre-template outlier, by name, with the why in a comment).

## The two corpus states (the lane's central constraint)

The working tree currently holds **280** lesson files: 270 committed + 10 **untracked** W1-ETHIC lessons (`293..302`) that are `noncoder.edu`'s deliverable, HOLDing per A1. Verified both states:

- **270 (committed corpus = what origin/main holds after this lane integrates):** detached verification worktree at `e6aff3a` (`.claude/worktrees/coder.api-CR054-GUARD`, removed after use), my edited test file copied in → **22 passed**. Floor `270 >= 270` holds at equality; capstone guard finds zero CR054 capstones (071 exempt) and passes vacuously — vacuous-at-270 is the *designed* state, the same shape the retired Wave-0 pin had before Wave 1.
- **280 (working tree = the state noncoder commits into after the round bump):** **22 passed**. Floor `280 >= 270`; capstone guard is **non-vacuous**: it finds exactly `297_playing_it_straight_capstone` (M22, synthesis ✓, 3 quizzes, last-in-module ✓) and `302_advice_vs_education_capstone` (M23, synthesis ✓, 3 quizzes, last-in-module ✓) — the two real capstones this guard exists to validate.
- **Untracked-file discipline:** the 10 W1-ETHIC files were never staged, edited, moved, or committed. Commit assembled with `git add` by explicit path (3 files); `git status` of `content/lessons/` after commit shows all 10 still untracked and byte-identical (they were never touched — read-only inspection only).

## Tests run (self-test)

- `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` (main tree, 280): **22 passed** in 2.20s. File went 21 → 22 tests: −1 retired, +2 capstone guards.
- Same file at the committed 270-state (verification worktree at `e6aff3a`): **22 passed** in 2.27s.
- Full suite `uv run pytest tests/unit/ -q` (main tree, 280): **927 passed, 1 warning in 133.94s (0:02:13)**
- Full suite at the committed 270-state (worktree): **927 passed, 1 warning in 144.85s (0:02:24)**

## Red-proofs (each executed in the disposable worktree, then restored — never against noncoder's files)

1. **Floor bites on shrink:** removed one committed lesson in the worktree (269 files) → `test_every_lesson_parses` failed: `expected at least 270 lesson files, found 269 — lessons have silently disappeared from the corpus`. Restored; green again.
2. **Last-in-module bites:** emptied the exemption set in the worktree copy → `test_every_capstone_is_the_last_lesson_in_its_module` failed on the real mid-module case: `('071_how_to_verify_before_you_wire_money', 'module 11 ends with 267_how_to_file_a_report_with_regulators')`.
3. **Synthesis prong bites:** same run → `test_every_capstone_ends_on_a_synthesis_quiz` failed: `('071…', 'tags missing "synthesis" — declare the synthesis quiz')`. Restored via `git checkout` + re-copy of my file; 22 passed again.

Together 2+3 also prove the exemption is *load-bearing*, not decorative: dropping it turns HEAD red, which is exactly why it exists.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Exactly 1 source file: `backend/tests/unit/test_lesson_corpus_integrity.py` (+ this lane's 2 orchestration files). No app code, no content, no other tests touched. |
| **(1) Floor** | `LESSON_COUNT_FLOOR = 270`, asserted `>=`, silent-loss intent kept + documented bump rule; parse-all loop unchanged. |
| **(2) Retirement** | `test_cr054_new_tracks_are_empty_at_wave_0` deleted; section comment records what/why; the 5 wiring guards + CR044 contiguity/prefix guards untouched. |
| **(3) Capstone guard** | 2 tests: capstone ⇒ last-in-module (with explicit no-module offender case) + synthesis final quiz (tag-declared, no-quiz offender case). Legacy 071 exempt by name with rationale. |
| **Green standalone at 270** | 22 passed in the `e6aff3a` worktree — no Wave-1 content assumed. |
| **Green at 280** | 22 passed in the working tree with the 10 untracked W1-ETHIC files present; guard validates 297 + 302 non-vacuously. |
| **Full suite** | 280-state: 927 passed · 270-state: 927 passed |
| **Red-proofs** | 3, all executed (not by-construction): shrink, mid-module capstone, missing synthesis declaration. |
| **Untracked W1 files** | Never staged/edited/moved; still untracked post-commit; commit staged by explicit path only. |
| **Commit** | Single commit, 3 named paths, tag `(AT:coder.api CR054)`, pushed to origin. |
