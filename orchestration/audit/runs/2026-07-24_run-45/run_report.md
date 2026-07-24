<!--
Auditor run report — run-45 (2026-07-24, session auditor.core/track U). Round-1 audit of
CR087-BE. Audited SHA abcc08b on lane/CR087-BE.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-45 (round 1) — CR087-BE lesson locale serving + quiz-integrity gate → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-24. Backend half of CR087, landed right
  after CR087-MOBILE (run-44) which was audited before this lane even started building.
- **Audited SHA:** `abcc08b`, tip of `lane/CR087-BE.coder.api` (branched from merge-base `487f94e`
  = current main HEAD, zero divergence — the diff IS the whole changeset). Audited in a fresh
  isolated worktree `.claude/worktrees/audit-CR087-BE/`.
- **The item:** loader discovers AR/MS `.mdx` siblings, `get(id, locale)` serves the translated
  body with EN fallback, `GET /v1/lessons/{id}?locale=`, quiz grading follows the served locale —
  guarded by a **serving-time quiz-integrity gate** substituted for the assign's literal
  build-time-test spec (flagged as a DEVIATION needing explicit sign-off).
- **Gate:** independent (D-5 — store-facing).
- **Verdict:** COMPLETE (round 1) — zero BLOCKER/MAJOR/MINOR against this lane's delivery.
  DEVIATION accepted after adversarial verification. One cross-lane observation (not a finding).

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 4 files, +530/−9. `docs/` untouched (0 diff) — the register-drift test failure is provably pre-existing. |
| Full suite | 1115 passed, 1 pre-existing-and-unrelated failure (confirmed via `docs/` diff + merge-base check). |
| New tests alone | 17 passed. |
| Real AR corpus | 312 tracked files seen in the isolated worktree (correctly excludes a concurrent content lane's untracked churn visible in the shared main checkout). |

### The DEVIATION — the center of this audit

Rather than accept the architect's "strict improvement, I judge this acceptable" note, I:

1. **Independently re-derived the corpus damage claim from zero** — a throwaway script calling the
   real `parse_mdx`/`_locale_quiz_servable` on all 312 real AR/EN pairs, reproducing the exact
   276-servable / 18-parse-fail / 18-quiz-fail split the coder reported, with real failure reasons
   matching the described corruption shape.
2. **Disabled the gate in the real loader and reran against real content** — surfaced dozens of
   genuine `answer_index` mismatches across actual lesson ids, not synthetic fixtures. This is
   direct, first-hand proof the corpus damage is real and the gate is the only thing preventing a
   live mis-graded-quiz defect. The two synthetic gate-rejection unit tests also correctly failed,
   confirming the gate's wiring into the loader (not just the standalone helper function) is what's
   under test. Reverted; suite re-confirmed clean.

This is materially stronger verification than reading the tests and trusting the pass/fail: it
proves both halves of the deviation's justification — that a build-time hard-fail really would
have been permanently red, and that the substituted mechanism really does prevent the harm class
it claims to.

### Remaining adversarial focus points (2–5)

Served-locale grading, EN-meta-canonical, EN-fallback-never-404 (dynamic corpus-wide check), and
`catalogue()` filtering — all read at source and cross-checked against both synthetic and
real-corpus tests; no gaps found.

### Beyond the architect's list

Verified the `available` list's Pydantic shallow-copy aliasing is sound (fresh per-lesson, no
cross-lesson bleed, and the shared-reference behavior is semantically correct for a
"locales-that-exist" field). Confirmed the `get()` backward-compat branch is real and exercised by
pre-existing gateway-pinning tests, not speculative dead code. Noted — as a cross-lane observation,
not a finding — that mobile's `submitQuiz` doesn't yet thread `locale`, so served-locale grading is
currently protected by exactly one layer (the integrity gate) rather than two; functionally correct
today because the gate guarantees AR/EN answer_index parity for anything actually served, but worth
a defense-in-depth follow-up.

## Findings

None against this lane's own delivery. DEVIATION accepted with adversarial evidence, not
rubber-stamped.

## Verdict

**VERDICT: COMPLETE (round 1)**
