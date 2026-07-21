<!--
Auditor run report — run-32 (2026-07-21, session auditor.core). Round-1 audit of CR054-GUARD
"content-addition-safe corpus guards" (coder.api-delegated lane under CR052 dispatch).
Audited SHA fd64a29 (HEAD of origin/main at audit time). Verdict COMPLETE. Owner: AUDITOR.
-->

# run-32 (round 1) — CR054-GUARD "content-addition-safe corpus guards" → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-21. Delegated track-R → `coder.api` under
  the CR052 dispatch model.
- **Audited SHA:** `fd64a29` — HEAD of `origin/main` at audit time (`git branch -r --contains` →
  `origin/main`). One source file: `backend/tests/unit/test_lesson_corpus_integrity.py`
  (`git show --stat` = 3 paths: test file + coder lane + architect lane). Audited in the ISOLATED
  worktree `.claude/worktrees/audit-CR054-GUARD/` at the SHA (`uv sync --extra dev --python 3.13`
  first, per the known fresh-worktree pytest fallback); 280-state corpus run on the main tree.
- **The item:** the Wave-1 root unblock — (1) exact `EXPECTED_LESSON_COUNT == 270` →
  `LESSON_COUNT_FLOOR = 270` asserted `>=` (L46/L65); (2) retire
  `test_cr054_new_tracks_are_empty_at_wave_0` (Wave-0 scaffolding, its docstring said so); (3) new
  capstone invariants (L444–486): `capstone`-tagged ⇒ last-in-module + declared synthesis quiz,
  legacy exemption `PRE_CR054_CAPSTONE_TAGS = {071_how_to_verify_before_you_wire_money}` (L433).
  Spec: CR054 §5.1 + assign lane + architect A1 in `CR054-W1-ETHIC.noncoder.edu.md`.
- **depends-on:** none.
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR / **2 MINOR** (advisory: floor-bump discipline
  is comment-only; `synthesis`-tag contract undocumented in the authoring template). No OUT-OF-SCOPE.

---

## Suite reproduction (foreground, my own runs)

| State | Command | Result |
|---|---|---|
| 270 (worktree at SHA) | `uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` | **22 passed** (8.49s) |
| 270 (worktree at SHA) | `uv run pytest tests/unit/ -q` | **927 passed, 1 warning** (188.86s) — arithmetic holds: 926 at `e6aff3a` −1 retired +2 added |
| 280 (main tree, 10 untracked W1 files) | `uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` | **22 passed** (2.14s); guard non-vacuous on `297` (M22) + `302` (M23), both `capstone`+`synthesis`, 3 quizzes, last-in-module |

## Blind adversarial probes (all bit; every plant restored via `git checkout`)

| Probe | Plant | Observed |
|---|---|---|
| (a) shrink | deleted `292_…` → 269 files | `test_every_lesson_parses` red: `expected at least 270 lesson files, found 269 — lessons have silently disappeared from the corpus` |
| (b1) mid-module capstone | `capstone`+`synthesis` tags on `066` (M11; M11's last = 267) | red: `('066…', 'module 11 ends with 267_how_to_file_a_report_with_regulators')` |
| (b2) module-less capstone | same tags on `280_what_is_a_stock` (no `module:` → loader default 0, `schemas/lessons.py:118`) | red: `('280_what_is_a_stock', 'no module: declared in frontmatter')` — same run as b1, both attributed exactly; genuinely-last `279` (M12 max) passed, no false positive |
| (c1) missing synthesis | `capstone` only on `279_you_are_the_ceo` | synthesis guard red: `('279…', 'tags missing "synthesis" — declare the synthesis quiz')`; last-in-module passed — prong independence both directions |
| (c2) no quiz | synthetic module-99 capstone file, zero `<Quiz/>` | red: `('999_audit_probe_capstone', 'capstone has no quiz at all')`; single-lesson module trivially last — semantics correct |
| (d) exemption dropped | `PRE_CR054_CAPSTONE_TAGS = set()` | BOTH guards red at HEAD on exactly 071 — exemption load-bearing (architect red-proofs 2+3 reproduced) |

## 071 exemption legitimacy (probe d, full)

Corpus sweep: 071 is the ONLY committed lesson with `capstone` in tags → exemption set == complete
legacy set. M11 spans 065–071 + 254–267 (071 mid-module because 254–267 were appended after it; its
body literally opens "This is the capstone of Module 11"). Authoring prompt L452 forbids retrofitting
M1–M12. `grep capstone backend/app/ mobile/lib/` → zero runtime consumers — the tag is inert metadata,
so the exemption masks no user-facing behaviour. Verdict: legitimate pre-template outlier.

## Policy judgement (floor vs exact pin) — ACCEPTABLE

The count assertion's job is file deletion; malformed lessons are caught count-independently by the
unchanged parse-all loop (L69–70). Residual exposure = deletions inside the floor-to-actual gap: zero
at HEAD (270/270), opens only between a wave integration and its floor bump. Compensating controls:
CR044 contiguity guard reds on any non-top-of-track deletion; 60 gateway ids pinned by name; new
auditor pin adds an independent corpus-vs-floor tripwire. The exact-pin alternative demonstrably
deadlocks (W1-ETHIC NEEDS-INFO: noncoder cannot edit `backend/`). Caveat recorded as MINOR-1: the
bump rule is comment-only and itself needs a coder.api touch per wave — recommend a per-wave
integration-checklist item.

## Auditor pin (new, permanent)

`orchestration/audit/regression/test_cr054_guard_capstone_floor_pin.py` — **4 passed** at both 270
and 280 states (stdlib text-parse + independent frontmatter scan). Pins: `>=` floor at >= 270 with
no `==` regression; corpus meets the floor; capstone guards exist + exemption frozen at `{071…}`;
independent re-scan that every capstone tag is exempt or module >= 13. **Red-proofed 5 ways** (floor
lowered / `==` reverted / exemption widened / legacy capstone planted / corpus shrunk) — all bit.

## MINOR (advisory, architect-owned)

1. Floor-bump-on-integration is convention-only and a `backend/` edit noncoder lanes can't make —
   add it to the per-wave integration checklist.
2. `synthesis`-tag contract absent from the authoring prompt's capstone template + wave briefs —
   one-line template fix; failure direction is loud/safe, Wave 1 unaffected.

## Verdict

`VERDICT: COMPLETE (round 1)` written to `cr/CR054-GUARD.auditor.md`. W1-ETHIC's HOLD can lift on
integration (architect bumps noncoder.edu's ASSIGNED per A1).
