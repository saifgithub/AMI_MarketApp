# DEF416 — `users.apple_id` / `users.google_id` had no unique constraint

**Filed:** 2026-09-24, source: CR231's stabilisation-programme sweep
**Category:** backend / auth / data integrity
**Severity:** high — a race can silently fork one identity into two accounts

---

## What's broken

`backend/app/db/models.py` declared `apple_id`, `google_id` and `hms_unionid`
as plain nullable `String` columns — no `unique=True`, no index, nothing.
`auth_service.py`'s `sign_in_with_apple` (~:590-668, pre-fix) and
`sign_in_with_google` (~:691-760, pre-fix) both do the ordinary
check-then-insert shape: SELECT `User` by the provider `sub`, and if nothing
comes back, build and INSERT a fresh row.

That is correct under one writer. Under two concurrent first-time sign-ins
presenting the **same** OIDC `sub` (double-tap, a client retry on a slow
response, two devices completing an in-flight Apple/Google auth for the same
person near-simultaneously), both reads land before either commit, both
branches decide "no existing user," and — because there was no constraint —
**both INSERTs succeed**. No `IntegrityError`, no error surfaced anywhere.
The result is two `User` rows for one real identity, silently diverging from
that point (separate credit balances, separate journals, separate trial
windows), discovered only much later if the same person signs in on a third
device and gets a coin-flip which of the two rows they land on.

This is the same failure class as `ISS001_DB_INSERT_RACE`
(`docs/dilemmas/ISS001_DB_INSERT_RACE/`) and DEF401
(`docs/defect/_registry/DEF401.row.md`) — `failure_patterns.md` **P15**. It
is strictly worse than the ordinary P15 shape: P15's other sites at least
have a constraint to violate, so the race produces a loud `IntegrityError`
that can be caught. Here there was nothing to catch — the ISS001 brief's own
2026-08-15 correction is what first surfaced that `apple_id`/`google_id`
carry no constraint at all (§3.1, rows 3-4).

`test_p15_check_then_insert_guard.py`'s `_UNREVIEWED` pin already named
`sign_in_with_apple` and `sign_in_with_google` (added under CR191's
inventory) — this defect is what answers them, ahead of CR191's remaining
scope (`_claim_or_create`, `ensure_anonymous`, still pinned; see "What this
does not fix" below).

## Fix

### 1. Migration `def416a0oidc0uq` (`backend/alembic/versions/def416a0oidc0uq_users_oidc_unique.py`)

Adds three partial unique indexes on `users`:

```python
op.create_index(
    "uq_users_apple_id", "users", ["apple_id"],
    unique=True,
    sqlite_where=text("apple_id IS NOT NULL"),
    postgresql_where=text("apple_id IS NOT NULL"),
)
# ...same for google_id, hms_unionid
```

`WHERE ... IS NOT NULL` — every column is nullable (a user who has never
linked that provider has NULL in it), and NULL already does not collide in a
plain single-column unique index on either Postgres or SQLite. The `WHERE`
clause is not load-bearing for that reason; it is here because it states the
actual invariant ("no two REAL sub values collide") explicitly, and it keeps
this migration identically spelled on both dialects — the same reasoning
`uq_journal_dedupe` (`d3e4f5a60029`) and `uq_reputation_event_dedup`
(`d1e2f3a40015`) already give for their own partial indexes.

**Chained onto the single current head** (`cr230a0order0log`, verified via
`alembic.script.ScriptDirectory.get_heads()` before writing this, not by
tracing `down_revision` pointers by eye).

`hms_unionid` is closed alongside the other two even though nothing writes
it yet (no Huawei AppGallery flow exists — CLAUDE.md: "Huawei AppGallery at
v1.1") — same column shape, same class of bug, closed now instead of left as
the next instance the moment that flow lands.

**Pre-check, fail loudly, never auto-resolve.** Before creating the indexes,
on Postgres, the migration runs a `GROUP BY ... HAVING COUNT(*) > 1` query
per column and raises `RuntimeError` listing every conflicting value and the
full set of row ids sharing it if any group is found — it does **not**
delete, merge, or otherwise pick a winner among existing duplicate rows. See
"Operator remedy" below. (SQLite is skipped: a fresh test DB is built by
`Base.metadata.create_all()` and stamped straight to head — see
`init_schema`'s docstring — so it never replays this migration's `upgrade()`
at all; the pre-check's `array_agg`-based SQL is Postgres-specific anyway.)

### 2. `models.py` mirror

`User.__table_args__` gained the same three `Index(..., unique=True,
sqlite_where=..., postgresql_where=...)` declarations, so a fresh test DB
(built via `create_all()`, not the migration chain) enforces the identical
constraint under the unit suite.

### 3. `auth_service.py` — DEF401's shipped recovery shape, reused

Both `sign_in_with_apple` and `sign_in_with_google`'s fresh-insert branch
now wraps the insert in a SAVEPOINT and catches the constraint violation:

```python
try:
    with s.begin_nested():
        s.add(row)
        s.flush()
except IntegrityError:
    # another caller's read-to-commit window overlapped ours and it won.
    logger.info("apple_sign_in_race_lost", apple_sub=apple_sub)
    row = s.execute(select(User).where(User.apple_id == apple_sub)).scalar_one_or_none()
    if row is None:
        raise  # constraint fired, so a row must exist — anything else is stranger
    _attach_apple_sub(row)  # same field-merge the "found an existing row" branch takes
```

`s.begin_nested()` is load-bearing, not decorative: `get_session()`
(`backend/app/db/session.py`) commits the *whole* session on clean exit and
rolls back the *whole* session on any exception. Without the SAVEPOINT, the
`IntegrityError` from the failed INSERT poisons the entire session — the
subsequent re-SELECT then raises `PendingRollbackError` instead of
recovering. This was verified as a mutation: temporarily removing
`begin_nested()` turns the new race test into a `PendingRollbackError`
failure rather than a clean pass (see "Tests" below).

`_attach_apple_sub` / `_attach_google_sub` are the existing "found an
existing row" field-merge logic (apple_id/google_id attach, don't-overwrite
email/display_name, anonymous→claimed promotion), extracted into a closure
so both the normal found-row branch and the lost-race recovery branch run
byte-identical logic — the loser of the race gets exactly the same treatment
a caller who found the row on the very first SELECT would have gotten.

This is DEF401's exact shape (`verdict_outcomes.py:286-312`,
`bank_verdict_outcome`): SAVEPOINT insert, catch `IntegrityError`, re-SELECT
by the column the constraint fired on, hand off to the found-row path,
return the winner's row. No new mechanism was invented.

## What this does not fix

- **`_claim_or_create` and `ensure_anonymous`** remain pinned in
  `_UNREVIEWED` — out of scope for this defect (it names apple_id/google_id
  specifically). Their remaining check-then-insert surfaces (the
  `user_id`-promote fallback path, `device_user_id`) are CR191's scope, not
  this one's.
- **`email`/`phone`/`handle`/`desk_key`** already carry `unique=True` and
  are unaffected by this change.
- **ISS001 itself is unresolved** — three submissions in, no verdict (field
  was kept open 2026-08-16 for a 4th contributor per
  `docs/dilemmas/ISS001_DB_INSERT_RACE/ISS001_STATE.md`). This defect does
  not wait on that verdict: it reuses the pattern already shipped and proven
  for DEF401, which is independent of whatever ISS001 eventually decides for
  the other 20+ sites' general mechanism.

## Operator remedy — pre-existing duplicates on a live database

If the migration's pre-check fires on Alpha (or any Postgres environment),
`alembic upgrade head` stops before creating any index, with a `RuntimeError`
naming every `apple_id`/`google_id`/`hms_unionid` value that is shared by
more than one row and the full list of conflicting `User.id`s.

This is not expected to fire — Alpha runs one uvicorn with no `--workers`
(the same deployment fact `docs/dilemmas/ISS001_DB_INSERT_RACE/
ISS001_problem_statement.md` §2 uses to explain why the P15 class hasn't bitten
in production yet) — but the pre-check exists because "probably fine" is not
a migration precondition. **The auditor should count actual duplicates on
melehost, read-only, before this promotes** (see architect doc's Attack
Surface section) — that is the real answer to "does this fire," not this
paragraph's reasoning from deployment topology.

If it does fire, the remedy is manual, by design — the migration will not
guess which row is canonical:

1. For each reported group, pull the conflicting rows (`SELECT * FROM users
   WHERE id IN (...)`) and decide which is the real, continuing account —
   typically the one with `claimed_at` set earliest, or the one with
   non-trivial state (journal entries, portfolio holdings, credit history).
2. Re-key the loser's dependent rows (`user_devices`, `journal_entries`,
   `sim_portfolios`, etc.) onto the winner's `id`, the same operation
   `_rekey_devices_to` already performs for the BL2 adoption case — by hand,
   under a transaction, on melehost directly (this is a one-time data
   migration for a specific incident, not application code).
3. Delete (or clearly tombstone) the loser row once nothing references it.
4. Re-run `alembic upgrade head`.

No script for this ships with the migration — a duplicate-account merge is
exactly the kind of decision (which account is "real," what happens to its
history) that must not be made silently or generically for an unknown
future incident.

## Tests

`backend/tests/unit/test_def416_oidc_unique_race.py` (6 tests):

- `test_apple_sign_in_race_lands_one_user_row_both_callers_agree` /
  `test_google_sign_in_race_lands_one_user_row_both_callers_agree` — the
  actual race, reproduced deterministically (winner committed through a
  separate, already-closed session first; the loser's own pre-check SELECT
  blinded once via a session proxy, matching
  `test_cr219_verdict_outcome_ledger.py`'s `_BlindSelectOnce` and
  `test_def220_check_then_insert_outcomes.py`'s `_BlindOnce` — no threads,
  no flakiness). Asserts exactly one row survives and the loser's return
  value points at the winner's id.
- `test_apple_id_unique_index_rejects_duplicate_outside_the_recovery_path` /
  `test_google_id_unique_index_rejects_duplicate_outside_the_recovery_path`
  — the constraint itself, bypassing `auth_service` entirely: a direct
  second INSERT with the same sub must raise.
- `test_multiple_users_with_null_apple_id_do_not_collide` — the partial
  index must not turn "never linked Apple" into a one-user-only state.
- `test_hms_unionid_unique_index_rejects_duplicate` — the third column, even
  though nothing writes it today.

Plus: `test_p15_check_then_insert_guard.py` (the AST guard now sees both
sites as guarded — `sign_in_with_apple`/`sign_in_with_google` removed from
`_UNREVIEWED`, `_claim_or_create`/`ensure_anonymous` left pinned),
`test_def278_migrations_are_immutable.py` (single head, migration untouched
after commit), the full existing auth suite (`test_auth_dependency.py`,
`test_auth_device_info.py`, `test_auth_google.py`,
`test_auth_phase1_5_audit_fixes.py`, `test_auth_service.py`,
`test_def177_llm_proxy_auth.py`, `test_def183_oidc_blocking_dos.py`,
`test_oidc_verifier.py`), `test_config_compose_parity.py`.

**Mutation evidence:** removed `s.begin_nested()` from the Apple path in a
scratch edit (leaving the bare `try: s.add(row); s.flush() except
IntegrityError:`) — `test_apple_sign_in_race_lands_one_user_row_both_
callers_agree` failed with `sqlalchemy.exc.PendingRollbackError: This
Session's transaction has been rolled back due to a previous exception
during flush`, exactly demonstrating why the SAVEPOINT is load-bearing
rather than cosmetic. Reverted; suite green again.

## Status

`fixed`. Not yet promoted to Alpha — `/promote-to-alpha` owed, and the
architect doc asks the auditor to count existing duplicates on melehost
read-only before that promotion runs.
