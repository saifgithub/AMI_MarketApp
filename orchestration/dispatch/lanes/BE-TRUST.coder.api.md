<!-- lane hand-off — coder.api. CR052. -->
# BE-TRUST — hand-off (round 1)

STATUS: READY_FOR_AUDIT (round 1)

Branch: `lane/BE-TRUST`, worktree `/Volumes/Extreme Pro/AMI_MarketApp_BE-TRUST`
(pushed to origin). Commit `9f3273f0`.

## DEF202 — journal retention keyed off a client-supplied `plan`

`backend/app/api/journal.py::list_entries` (`GET /v1/journal/{user_id}`) took
`plan: str = "trial_trader"` as a query param, coerced it, and passed it
straight to `store.list_for_user(plan=plan_enum, …)` — the value that decides
the retention window and the `retention_days` the client renders. Deleted the
parameter entirely; `plan_enum = effective_plan_for_user(user_id)` now, the
same correction DEF179 applied to `one_on_one.py` and `brief_engine.py`.
Removed the now-unused `from app.schemas import Plan` import.

**`/trash` checked, not touched:** `list_trash` never took a `plan` param in
the first place — `store.list_deleted()` doesn't accept one, and the route
always returns `retention_days=None`. Same shape the assign asked me to
check; it was already correct.

## DEF119 — freeze()'s 2-per-year cap is an unprotected COUNT-then-INSERT

Added a transaction-scoped Postgres advisory lock in
`reputation_service.py::freeze()`, keyed on `f"streak_freeze:{user_id}:{period_key}"`,
immediately before the `COUNT` — `session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": ...})`.
Gated to `session.get_bind().dialect.name == "postgresql"` because SQLite has
no advisory locks; the gate is a no-op on the test engine and load-bearing
only in production.

**Evidence, disclosed honestly per the assign's own standard — and one
measured discrepancy from the row:**
- `test_freeze_takes_a_postgres_advisory_lock_keyed_on_user_and_period` proves
  the lock statement's *shape* (issued, gated on the postgres dialect, keyed
  correctly) via a proxy session that fakes `dialect.name == "postgresql"`
  while running on the real sqlite engine underneath. This is a real
  red→green mutation test: reverting the fix makes `lock_calls` empty.
- `test_freeze_concurrent_attempt_is_inconclusive_on_sqlite_by_design` races
  two threads calling `freeze()` on separate sessions for two different new
  dates. **The DEF119 row and the CR091-STREAKS auditor both describe SQLite
  masking the race with `OperationalError: database is locked`. Run
  repeatedly on this machine (5+ runs), that did not happen** — the
  `sqlite3` module's default busy-timeout quietly waits out the write lock
  instead of raising, so both threads' stale COUNT-of-1 goes on to commit,
  and the 2-per-year cap is **actually exceeded (3 rows)** every time. That's
  a *stronger* confirmation of the underlying defect than "inconclusive" —
  the race is directly reproducible here — but it means the test cannot
  assert the cap holds (it doesn't, on this engine, and the postgres-only
  lock doesn't reach it). The test instead asserts only internal consistency
  (`rows == 1 + successes`) and documents the actual measured behaviour in
  its own docstring, rather than writing a green result that implies more
  than this machine can prove. **Still true, and unchanged from the row:**
  whether the advisory lock actually serialises two concurrent Postgres
  transactions cannot be shown here — there is no local Postgres and the Mac
  must not start one.
- Cannot exercise the `postgresql` branch against a real Postgres server —
  same constraint the row already names.

## DEF140 — sse_text escaped `\n` but forwarded a raw `\r`

`sse_text` now raises `SseFramingError` on any raw `\r` in the payload,
rather than normalising or escaping it — escaping to a literal `\r` would
render literally on the shipped `0.1.0+56` Flutter decoder (it only inverts
`\n` and `\\`). Comment added at `escape_sse_text`'s docstring explaining
*why* LF is escaped but CR is rejected outright (the sharp edge the row
calls out).

`test_def127_sse_framing_invariant.py`:
- Removed `"carriage\r\nreturn"` from the "always exactly one event"
  parametrize list — that payload now raises instead of framing cleanly.
- Added `test_sse_text_refuses_a_payload_with_a_raw_carriage_return`,
  parametrized over a lone `\r`, `\r\n`, mid-string, and trailing-only,
  mirroring `test_sse_json_refuses_a_payload_with_a_raw_newline`'s shape.

Also fixed a pre-existing `SyntaxWarning: invalid escape sequence '\`'` in
`escape_sse_text`'s original docstring (an unrelated backtick+backslash
combination) while rewriting it — not part of DEF140 but caught while
editing the same lines.

## Tests

- `backend/tests/unit/test_def202_journal_plan_trust.py` (new, 2 tests) —
  a Floor Pass user requesting `?plan=floor_manager` still gets 30-day
  retention and the truncated entry list; a Floor Pass user omitting `plan`
  entirely still gets 30-day retention (not the old `trial_trader` default's
  unlimited — the case that actually distinguishes the fix, since
  `trial_trader` and `floor_manager` both resolve to unlimited retention).
- `backend/tests/unit/test_reputation_service.py` (+2 tests, DEF119, above).
- `backend/tests/unit/test_def127_sse_framing_invariant.py` (net +3 cases,
  DEF140, above).

## Mutation testing (acceptance-6)

Reverted each fix file in turn (`git stash push -- <file>`), ran the relevant
test(s), confirmed RED, restored (`git stash pop`):
1. `journal.py`'s `effective_plan_for_user` switch → both DEF202 tests red
   (`AssertionError: assert None == 30` — the reverted code let
   `trial_trader`'s unlimited retention through for a Floor Pass user).
2. `sse.py`'s CR rejection → all 4 parametrize cases of
   `test_sse_text_refuses_a_payload_with_a_raw_carriage_return` red
   (`Failed: DID NOT RAISE SseFramingError`).
3. `reputation_service.py`'s advisory lock → `test_freeze_takes_a_postgres_advisory_lock_keyed_on_user_and_period`
   red (`lock_calls == []`). The concurrency test (2) doesn't move under this
   mutation — expected, since it doesn't assert the cap holds either way
   (see DEF119 section above); nothing came back green that should have
   gone red.

## Full suite

`"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`
from repo root, run against the worktree (venv doesn't exist inside the
worktree itself, so I pointed at the main checkout's venv): **1799 passed, 0
failed, 8 warnings** (252.82s).

**Discrepancy to disclose:** the assign states baseline **1798** with one
known excluded failure
(`test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
"another track's uncommitted work in the shared checkout"). Running the same
command in the **main checkout** first (before creating this worktree)
reproduced exactly that: 1798 passed, 1 failed, matching the assign. But this
worktree was created via `git worktree add` from committed `main`
(`892d857d`), which does **not** carry that other track's *uncommitted*
`webhooks.py`/test changes — so in this worktree that test exercises the
clean committed code and passes. Net: this worktree's own baseline (before my
7 net new test cases) was 1792, not 1798; 1792 + 7 = 1799, all green. Zero
failures either way — flagging per "if you can measure an instruction is
wrong, disclose with the measurement," not asserting the assign's baseline
number is wrong for the shared checkout it describes.

## Registers

`DEF202.row.md`, `DEF119.row.md`, `DEF140.row.md` flipped to `fixed` (status
cell is a bare token; the Fix column carries `` `(AT:R65 DEF202 DEF119 DEF140)` ``
for all three, Session column left at `AT:R65`). `DEF119`'s prior Fix-column
value was a link to the CR091 folder rather than a fix tag — replaced with
the same commit-tag convention the other two rows already used. Regenerated
`docs/defect/def_list.md` via `scripts/registers/gen_registers.py gen def`.
All three rows + the regenerated table + the code + the tests landed in one
commit (`9f3273f0`), per DEF159.
