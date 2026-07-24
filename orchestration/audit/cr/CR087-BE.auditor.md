<!--
CR087-BE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR087-BE.architect.md (see PROTOCOL.md).
-->

# CR087-BE — audit lane (auditor)

**Item:** CR087-BE — make the CR083 AR/MS translated lesson bodies reachable: loader parses
`{stem}.{ar,ms}.mdx` siblings, `get(id, locale)` serves the locale body with loud EN fallback,
`GET /v1/lessons/{id}?locale=`, quiz graded against the served locale. Backend half of CR087.

**Gate:** independent (D-5 — store-facing: AR ships to public tracks per a CEO-approved timing
deviation).

**Audited SHA:** `abcc08b`, tip of `lane/CR087-BE.coder.api` (branched from merge-base `487f94e` =
current main HEAD, zero divergence). Audited in an isolated worktree
`.claude/worktrees/audit-CR087-BE/`.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff --stat 487f94e..abcc08b` — 4 files, +530/−9: 3 backend + 1 new 371-line test. No `content/lessons/**`, no migration, no `docker-compose.yml`, no `mobile/**`. `docs/` completely untouched (0 diff). |
| Full suite | **1115 passed, 1 failed** (`test_registers_no_drift::test_registers_match_their_row_files`). Independently confirmed this is pre-existing and unrelated: `docs/` has zero diff in this changeset, and `DEF101` is present in `docs/defect/def_list.md` at merge-base `487f94e` with no `DEF101.row.md` anywhere in the tree — a register-governance drift this lane could not have caused or fixed (Architect-owned per CLAUDE.md CR081). |
| New test file alone | 17 passed. |
| Real AR corpus size in this worktree | 312 tracked `.ar.mdx` files (matches the coder's stated tracked baseline — a concurrent content-authoring lane is dropping additional untracked AR/MS files into the shared main checkout, which my isolated worktree correctly does not see). |

### The DEVIATION — verified adversarially, not rubber-stamped

The assign scoped a **build-time** corpus test asserting AR/EN `answer_index` parity, fail-on-drift.
The coder instead built a **serving-time integrity gate** (`_locale_quiz_servable`): a locale
lesson is served only if it matches EN per-question on quiz count, option count, and
`answer_index`, with no empty option — otherwise the whole lesson falls back to EN, logged. I did
not accept the architect's "strict improvement" judgment on the strength of the writeup alone —
I reproduced the underlying claim from scratch, then adversarially proved the gate is genuinely
load-bearing:

1. **Independently re-measured the real corpus damage**, without touching the gate: wrote a
   throwaway script (not committed) that walks all 342 EN files, finds each `.ar.mdx` sibling, and
   calls the real `parse_mdx` + `_locale_quiz_servable` on each pair exactly as the loader does.
   Result: **312 AR siblings found, 18 parse failures, 18 quiz-integrity failures, 276 servable** —
   matching the coder's stated 276/18/18 split exactly, independently reproduced rather than taken
   from a log line. Sample quiz failures show the exact corruption pattern described
   (`q1 option_count en=4 loc=0` — emptied options).
2. **Disabled the gate in the real loader path** (`_locale_quiz_servable` forced to always return
   `(True, "")`) and reran the suite against the **real corpus**, not synthetic fixtures. Result:
   `test_served_ar_quizzes_match_en` failed with **dozens of genuine `answer_index` mismatches**
   across real lesson ids (e.g. `180_tangible_book_vs_reported_book q1: answer_index en=2 ar=0`,
   `185_roe_vs_roic q1: answer_index en=2 ar=0`) — proving the CR083 corpus damage is real, not
   hypothetical, and that the gate is the only thing standing between a translator's tooling bug
   and a mis-graded AR quiz in production. The two synthetic gate-rejection tests
   (`test_loader_rejects_ar_answer_index_drift`, `test_loader_rejects_ar_with_empty_options`) also
   correctly went RED, confirming the gate's loader wiring is genuinely exercised, not a
   standalone helper that happens to work in isolation. Reverted; full suite re-confirmed
   1115/1 clean afterward.

This is the strongest possible evidence for accepting the deviation: the literal build-time-test
approach would indeed have left the suite permanently red on content this lane cannot re-author,
and the substituted mechanism demonstrably prevents the exact class of user-facing harm (DEF059/
DEF064-shaped) it claims to.

### Adversarial focus points 2–5 — verified at source and via existing tests

- **Grading uses the served locale** — `submit_quiz` calls `self.get(req.lesson_id, req.locale)`,
  read at source (not inferred). `test_submit_quiz_grades_against_served_locale` white-box-injects
  a divergent AR quiz (bypassing the gate on purpose) and proves a `locale="ar"` submission grades
  against the AR key while `locale="en"` grades against EN — genuinely locale-sensitive grading,
  not a hard-coded EN key.
- **EN meta canonical** — `test_en_meta_stays_canonical_locale_supplies_title` (synthetic, AR
  frontmatter deliberately carries wrong `track`/`code`/`module`) and
  `test_real_get_ar_returns_arabic_title_and_body` (real corpus) both confirm only `title` comes
  from the locale file; `track`/`code`/`gates_agents`/`module` all come from EN. Read the
  `model_copy(update={"title": ...})` composition at source — only `title` is overridden.
- **EN fallback never 404** — `test_real_ar_unavailable_lessons_fall_back_to_en` is dynamic (not a
  fixed list): it computes `en_ids - ar_ids` from the real catalogue and asserts every one of them
  serves a non-null EN body under `locale="ar"`. Read `get()`'s two-tier fallback
  (`served.get(locale) or served["en"]`, then the pre-`_reload` backward-compat branch) at source.
- **`catalogue("ar")`** — confirmed it emits the locale-composed meta (translated title) while
  filtering on `locale_versions`, which the loader now populates from what actually parsed **and**
  passed the gate — read at the exact diff hunk, not inferred from the method name.

### Additional checks beyond the architect's list

- **The `available` list aliasing** the architect's pre-check flagged as "intentional and sound" —
  verified myself: `available = ["en"]` is a fresh list literal created inside the per-lesson outer
  loop (no cross-lesson bleed), and Pydantic's `model_copy()` is a shallow copy, so every
  locale-variant's composed meta shares the same list object — meaning each variant's
  `locale_versions` converges to the lesson's *complete* final set regardless of which locale it
  was composed from. This is the semantically correct behavior for a "what languages exist for
  this lesson" field, not a bug.
- **Backward-compat `get()` branch** ("test fakes, dynamic gateway pinning has no per-locale map")
  — confirmed this is not speculative dead code: grepped for direct `_lessons[...] =` writes
  outside `_reload()` and found the **pre-existing** `test_lessons_service.py` genuinely injects
  fake lessons this way (`svc._lessons[fid] = f`, lines 372/430) for gateway-pinning tests, which
  passed cleanly in the full suite run — the branch is real and exercised.
- **`QuizSubmitRequest.locale` is not yet wired from mobile** — checked `mobile/lib/services/api/
  api_client.dart`'s `submitQuiz` (already-audited CR087-MOBILE, and CR084-MOBILE's shared file):
  it does not send a `locale` field at all, so every mobile submission defaults to grading against
  EN server-side regardless of what locale the user actually saw. **This is not a correctness bug
  today** — the integrity gate guarantees any AR quiz that is actually served has answer_index
  identical to EN, so grading against the EN default is equivalent to grading against the served
  AR quiz for every lesson the app could have shown. Noting it because the "served-locale grading"
  design is currently protected by exactly one layer (the gate), not two (gate + locale-threaded
  submit) — worth a one-line mobile follow-up (thread `locale` into `submitQuiz`) as defense in
  depth, but not a blocker for either lane's own acceptance, and not something either lane's spec
  literally required. Flagged for the architect's awareness, not minted as a DEF myself per
  AMI_TRADE_BINDINGS (a product-code observation outside either audited chunk's own scope).

### Findings

Zero BLOCKER, zero MAJOR, zero MINOR against this lane's own delivery. **DEVIATION ACCEPTED** —
adversarially verified, not rubber-stamped: the gate is real, necessary (312 AR files contain 18
+18 genuine corruptions, independently re-measured), and effective (disabling it in the real
loader path surfaces dozens of genuine answer_index mismatches across real content). One
cross-lane **observation** (not a finding): `QuizSubmitRequest.locale` is unused by the current
mobile client, so served-locale grading is currently single-layer-protected by the integrity gate
alone — functionally correct today, worth a defense-in-depth follow-up.

### Verdict

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-24_run-45/run_report.md`](../runs/2026-07-24_run-45/run_report.md)
