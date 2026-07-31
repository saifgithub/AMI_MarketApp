# Audit run report — 2026-07-31 run-10

ITEM: R65-BATCH1 · ROUND: 1 · VERDICT: AWAITING_FIXES (2 MAJOR)
SHA: `af0aeb77` (on main, as submitted) · SCOPE: `chunk` — 7 items
judged individually: DEF195, DEF160, DEF201, DEF200, DEF117, CR105, CR127
AUDITOR: track U (Kimi) · worktree `.claude/worktrees/audit-R65-BATCH1`
(detached at the SHA — DEF159 trap avoided; numbers match the bridge's
own detached measurement)

## MAJORs

- **M1 — DEF195: gate with no tests and no caller.** Both halves
  independently confirmed (grep finds only the file itself; no test
  file exists). A 191-line release gate that never runs = the
  DEF063/DEF038 dark-for-months class. Architect pre-judged MAJOR;
  upheld independently. Fix: wire into build/CI when CR084-ALPHA's
  build-script edits land + a smoke test (fixture OpenAPI + known-bad
  client keys → nonzero exit).
- **M2 — DEF201: fourth release path found.** `one_on_one.py`:
  `spend()` (credit_service.py:234 — opens a DB session, commits) can
  raise non-`InsufficientCredits` (DB failure) between `acquire()` and
  the generator's `try`/`finally`; the except only covers 402; slot
  leaks permanently (no TTL/eviction; restart-only recovery). Cap=2 →
  two DB-blip failures wedge a user's 1-on-1 into 429 until restart.
  Fix: broad `except Exception: release; raise` + a test raising
  non-402 from spend().

## MINORs

- m1: DEF201 janitor unwired (6 tests, no invoker; compose mount
  verified committed at docker-compose.yml:258, not live until
  promotion). Volume cap bounds the disk meanwhile. Second unwired
  deliverable in one batch — the class is forming a habit.

## Clean items

- DEF160: copyWith trap genuinely handled; DEF152 guard widening
  (`\.reset\(\)` → `\.reset\(`) upheld — singleton-call-site and
  confirm-precedes-reset invariants both intact.
- DEF200: census re-run myself → 75/93 reproduced. Depends-threadpool
  judgment correct; one-hop scope disclosed honestly.
- DEF117: ALL arithmetic redone independently — NVDA 5.0x wick ratio
  exact (1.50/0.30), pullback 6.60/412.40 = 1.60% + R:R 2.97 ≈ 3.0,
  TNB OCF−capex = −8.8B "sharply negative" (+yield 3.38%, payout 70.4%
  re-verified), TSLA 18×266.50 = 4,797 = 5.996% under cap. Keys/ids/
  schema untouched.
- CR105: assembled-prompt guard real (build_agent_prompt, exactly 2
  mentions == resolved, anti-vacuous resolved≠50 check); trader.md and
  parity test confirmed untouched. Acceptance #7 owed post-promotion
  (recorded).
- CR127: byte-identical revert re-verified (one added doc comment in
  hero region; roomHero* × en/ar/ms unchanged vs 972c0a0a^).
  NEEDS-DEVICE-CHECK + architect-composed AR/MS (disclosed).

## Measurements (all detached at af0aeb77)

backend 1860/0 (278.60s; bridge 270.55s) · flutter 402 passed ·
analyze exit 0 5 infos · registers DEF 205 / CR 130 OK · census 75/93
reproduced. Blind mutation (mine): removed 402 explicit release →
exactly 1 RED (402-release test), reverted byte-identical, 12/12
re-green.

DoD enforcement waived per standing instruction.
