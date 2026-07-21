<!--
CR054-GUARD.auditor.md — auditor lane file (track U owns). VERDICT line the
watcher/architect key on. Independent verification. Do NOT edit
CR054-GUARD.architect.md or cr/INDEX.md. Run report:
orchestration/audit/runs/2026-07-21_run-32/run_report.md
-->

# CR054-GUARD — audit lane (auditor)

**Item:** make the lesson-corpus guards content-addition-safe so Wave 1–3 content lanes land lessons
without a `backend/` edit — (1) exact `EXPECTED_LESSON_COUNT == 270` pin → `LESSON_COUNT_FLOOR >= 270`,
(2) retire the Wave-0 empty-track pin, (3) add the capstone invariants (last-in-module + declared
synthesis quiz) with the by-name legacy exemption `{071_how_to_verify_before_you_wire_money}`.
Delegated track-R → coder.api under CR052 dispatch; root unblock for W1-ETHIC + every later wave.
**Audited SHA:** `fd64a29` (on `origin/main` — `git branch -r --contains` confirmed). One source file:
`backend/tests/unit/test_lesson_corpus_integrity.py` (+2 lane docs; `git show --stat` = exactly 3 paths).
Audited in an ISOLATED worktree `.claude/worktrees/audit-CR054-GUARD/` at the SHA (clean 270-lesson
checkout — the state origin actually runs), plus a 280-state corpus run on the main tree.
**depends-on:** none.
**Run report:** `orchestration/audit/runs/2026-07-21_run-32/run_report.md`

## VERDICT: COMPLETE (round 1)

Zero BLOCKER + zero MAJOR. 2 MINOR (advisory, non-blocking, architect-owned follow-ups — see below).
All three guard changes verified at file:line, suite reproduced at both corpus states, every claimed
red-proof independently re-executed with my own probes (5 distinct offender plants, all bit with exact
attribution), the 071 exemption proven legitimate and load-bearing, and the floor-vs-pin policy call
judged acceptable. New 4-test auditor pin freezes the floor semantics + exemption set permanently.

---

## Findings (independently reproduced)

| # | Dimension | Verdict | Evidence |
|---|---|---|---|
| F1 | **Floor still catches silent shrink** | CONFIRMED | Probe (a): deleted 1 lesson in the worktree (269 files) → `test_every_lesson_parses` red: `expected at least 270 lesson files, found 269 — lessons have silently disappeared` (`assert 269 >= 270`). Restored → green. Floor sits at equality with the committed corpus (270/270), so the shrink window at HEAD is zero. Parse-all loop (test file L69–70) unchanged — malformed-lesson detection is count-independent. |
| F2 | **Last-in-module guard bites** | CONFIRMED | Probe (b): planted `capstone`+`synthesis` tags on mid-module `066` (M11) AND module-less `280` in one run → both flagged with exact attribution: `('066…', 'module 11 ends with 267_how_to_file_a_report_with_regulators')` + `('280_what_is_a_stock', 'no module: declared in frontmatter')` (L467). Genuinely-last `279_you_are_the_ceo` (M12's max) correctly PASSED this prong in the same run — no false positive. Loader default `module=0` verified (`schemas/lessons.py:118`) → the `module <= 0` offender branch is real (280–292 declare no module). |
| F3 | **Synthesis-quiz guard bites** | CONFIRMED | Probe (c): `279` with `capstone` but no `synthesis` tag → red `('279…', 'tags missing "synthesis" — declare the synthesis quiz')` (L486), while passing last-in-module — prong independence proven both directions. Synthetic module-99 capstone with zero `<Quiz/>` blocks → red `('999_audit_probe_capstone', 'capstone has no quiz at all')`; single-lesson-module semantics correct (trivially last). |
| F4 | **071 exemption legitimate, not a mask** | CONFIRMED | (i) Corpus-wide sweep: 071 is the ONLY committed lesson with `capstone` in `tags` → the exemption set is exactly the complete legacy-offender set, nothing else rides it. (ii) Genuinely pre-template: M11 spans 065–071 + 254–267 (last = 267), so 071 is mid-module because lessons were appended after it; it declares no `synthesis` tag. (iii) Authoring prompt L452: "Existing modules M1-M12 have no capstones. Do NOT retrofit them" — holding 071 to the CR054 template would demand a forbidden retrofit. (iv) Runtime-inert: `grep capstone backend/app/ mobile/lib/` → zero consumers; the tag renders nothing, so exempting it masks no user-facing behaviour. (v) Load-bearing: emptied the set → BOTH guards red at HEAD on exactly 071 (architect's red-proofs 2+3 independently reproduced). |
| F5 | **Policy: floor vs exact pin** | ACCEPTABLE | The count assertion's real job is file deletion (parse failures are caught count-independently by the parse-all loop). Residual exposure = deletions inside the floor-to-actual gap, which is 0 at HEAD and opens only between a wave integration and its floor bump. Compensated: CR044 contiguity guard reds on ANY non-top-of-track deletion (code sequence 1..N breaks), 60 gateway ids are pinned by name, and my new pin adds an independent floor tripwire. The alternative (exact pin) demonstrably deadlocks: W1-ETHIC sat NEEDS-INFO because noncoder.edu cannot edit `backend/` — an exact pin forces that cross-ownership violation into every content wave. Weakening is narrow, mostly-compensated, and buys out a real structural deadlock. See MINOR-1 for the bump-discipline caveat. |
| F6 | **Wave-0 pin retirement appropriate** | CONFIRMED | Retired test's own docstring scoped it as scaffolding ("enforcement floor until Wave 1 fills the tracks"); Wave 1 is now filling them. File went 21 → 22 tests (−1 retired, +2 capstone; counted at `e6aff3a` vs `fd64a29`). The 5 Wave-0 wiring guards (L332–412) + CR044 population guards (L179–219) verified still present and untouched. Retirement recorded in the section comment (L318–321). |

## Suite + corpus states (reproduced myself, foreground)

- Worktree at `fd64a29` (270 committed lessons): corpus file **22 passed** (8.49s); full
  `uv run pytest tests/unit/ -q` → **927 passed, 1 warning** (188.86s). Arithmetic checks out:
  926 at `e6aff3a` (W0d row) − 1 retired + 2 added = 927.
- Main tree (280 = 270 + 10 untracked W1-ETHIC files): corpus file **22 passed** (2.14s); guard
  NON-VACUOUS — `297` (M22) + `302` (M23) both carry `capstone`+`synthesis`, 3 quizzes each,
  last-in-module. The 10 W1 files verified still untracked post-commit (never swept in).

## Auditor pin (added)

`orchestration/audit/regression/test_cr054_guard_capstone_floor_pin.py` — **4 passed** at BOTH corpus
states (270 worktree / 280 main). Stdlib text-parse + independent frontmatter scan; pins: (1) count
guard stays a `>=` floor at >= 270 with no `==` pin regression, (2) corpus on disk meets the floor,
(3) both capstone guards exist and `PRE_CR054_CAPSTONE_TAGS` is frozen at exactly `{071…}` — widening
it is the guard's bypass vector and must trigger a fresh audit, (4) independent re-scan: every
capstone-tagged lesson is exempt or in a module >= 13, so a legacy retrofit can't hide even behind a
widened exemption. **Red-proofed 5 ways** (floor lowered to 200 / `>=` reverted to `==` / exemption
widened / legacy capstone planted on 066 / corpus shrunk to 269) — every mutation bit with a specific
message; restored green.

## MINOR (advisory, non-blocking; architect owns any follow-up — auditor mints no IDs)

- **MINOR-1 — floor-bump discipline is comment-only, and the bump is a `backend/` edit.** The
  constant's comment (L44–46) says each integrating wave bumps the floor, but content lanes are
  NONCODER and cannot touch the file — every bump needs a coder.api micro-touch, and nothing enforces
  it happening. If bumps habitually lag, the undetected-shrink window stays 10–40 lessons wide
  (top-of-track, non-gateway lessons only, per F5). Recommend: add "bump `LESSON_COUNT_FLOOR`" as an
  explicit per-wave integration-checklist item (e.g. in the wave close-out or a standing coder.api
  chore). My pin caps the drift (corpus-vs-floor tripwire) but doesn't close it.
- **MINOR-2 — the `synthesis`-tag contract is documented only in the guard file.** The authoring
  prompt's capstone template (L439–441) mandates the `capstone` tag but never says synthesis is
  declared via a `synthesis` tag; wave1_ethics.md's frontmatter block leaves `tags: [...]` freeform.
  A future template-compliant capstone without the tag goes red — loudly and with a self-explaining
  message (safe direction), but it's an avoidable round-trip. Recommend a one-line addition to the
  template: `tags` MUST also include `"synthesis"`. (Wave 1 is unaffected — 297/302 already carry it.)

## Definition-of-Done disposition

| Architect row | Auditor disposition |
|---|---|
| Scope (1 source file + 2 lane docs) | OK — `git show --stat fd64a29` = exactly 3 named paths; no app code, content, or other tests touched; shared-tree WIP (`uv.lock`, roster, `Archive.zip`) not swept in. |
| (1) Floor | **Reproduced** — L46 constant, L65 `>=` assertion, parse-all loop unchanged (L69–70); bites at 269 (probe a). |
| (2) Retirement | **Reproduced** — test gone (21→22 counted across SHAs), section comment records it (L318–321), 5 wiring + CR044 guards verified intact. |
| (3) Capstone guard | **Reproduced** — both tests verified at L444–486; all four offender branches bitten by my own probes (mid-module / no-module / missing-synthesis / no-quiz); exemption verified complete, legitimate, load-bearing (F4). |
| Green standalone at 270 | **Reproduced** — 22 passed in my own worktree at the SHA. |
| Green at 280 | **Reproduced** — 22 passed on the main tree; 297+302 validated non-vacuously. |
| Full suite | **Reproduced at 270** — 927 passed in the worktree. (280-state 927 corroborated by test arithmetic; corpus file at 280 re-run myself.) |
| Red-proofs (3) | **Re-executed independently** — my 5 probes cover and extend all 3 (shrink / mid-module / missing synthesis, + no-module and no-quiz branches the architect didn't probe). |
| Untracked W1 files | OK — all 10 still untracked at audit time; commit carries only the 3 named paths. |
| Commit | OK — single commit `fd64a29` on `origin/main`, tag `(AT:coder.api CR054)` sanctioned by `DISPATCH_PROTOCOL.md:41` (house precedent W0a/W0b/W0d). Register: umbrella CR054 `in_progress` — correct per sub-lane precedent. Docs row implicit-N/A holds: test-only change, contract documented in the guard file + lane docs (but see MINOR-2). |

## OUT-OF-SCOPE

- None.

---

SUBMITTED-SEEN: round 1
VERDICT: COMPLETE (round 1)
