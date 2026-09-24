<!--
RETRO-MIGRATIONS.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs RETRO-MIGRATIONS.architect.md.
-->

# RETRO-MIGRATIONS — auditor verdicts (alembic chain integrity, retroactive)

## Round 1 — auditor U68

**SHA audited:** `34941fa1`, in a detached scratch worktree `audit-U68-PMFLOOR` per DEF159, and as
a `git archive 34941fa1` tree on melehost for the Postgres runs. Worktree verified clean after the
mutation below was removed.

**Tier A.** The throwaway database: `postgres:15-alpine` (the image `ami_postgres` runs), container
`audit_u68_pg` on its own docker network `audit_u68_net`, driven by the Alpha API image with the
archived tree mounted read-only. Never `ami_postgres`'s data; both were removed at the end. The
only contact with the live database was read-only: `SELECT`s and `pg_dump --schema-only`.

### The chain itself: clean, in both directions

The lane's "single biggest untested claim", run:

```
alembic heads                         cr230a0order0log (head)
alembic upgrade head   (empty DB)     72 "Running upgrade"    UPGRADE_EXIT=0   current: cr230a0order0log (head)
alembic downgrade base                72 "Running downgrade"  DOWN_EXIT=0
  residue after downgrade: tables = alembic_version only; indexes = its pkey only; enums 0; policies 0
alembic upgrade head   (again)        72 "Running upgrade"    REUP_EXIT=0      62 tables
```

The downgrade path, which nothing in the repo exercises, reverses cleanly — including the
`cr221a0b0c0d4` / `e221i000009c` index repair the architect singled out.

- **DEF411's AST claim, re-derived rather than read:** `sha256(ast.dump(fn))[:16]` of both
  `cr222a0b0c0d4` versions — `6159a62b`: `upgrade f17148e6de849606`, `downgrade fb351fc49dfbbe14`;
  `839c3283`: identical. Only `down_revision` differs among module values. The file is unchanged
  from `839c3283` to `34941fa1`. The comment's arithmetic is exact.
- **DEF411's live measurement, refreshed:** Alpha `alembic_version` = `cr230a0order0log` (head).
  `toll_charged` present on `sim_trades`, `sim_short_positions`, `sim_option_trades`;
  `ix_edgar_8k_items_cik_filed (cik, filed)` present, no stale ticker index. Matches the fresh DB.
- **DEF406 guard, mutated:** a second head (`down_revision = "e221i000009c"`) ->
  `FAILED test_the_real_repo_has_exactly_one_head`. Removed; clean.
- **DEF337:** `c192f000001d` applies cleanly in the fresh run; `b4c1d2e3f501` is gone.
- **Scope correction accepted:** `git show --stat` of `5ee0051f` / `5854fcf9` / `d4ca6dce` touches
  0 files under `alembic/versions/`. DEF401/DEF220/DEF308 do not belong here.

### MAJOR-1 — Alpha's database is not what this chain builds, and the difference is a security control nobody sets

`pg_dump --schema-only` of Alpha vs the chain-built throwaway, normalised and diffed (139 lines):

| Object | Chain (fresh) | Alpha (live) |
|---|---|---|
| RLS `ENABLE` on 12 user-scoped tables (`FORCE` on 11), 23 policies on `current_setting('app.user_id')` | present | **absent** (0 / 0) |
| server defaults (`fetched_at`, `created_at`, `status`, `is_etf`, …) on 13 columns in 8 tables | present | absent |
| `revenuecat_events` unique constraint | `uq_revenuecat_event_id` | `revenuecat_events_event_id_key` |
| `credit_backup_20260814` table, `pgcrypto` / `uuid-ossp` extensions | absent | present (out of band) |

The mechanism is in the repo: on a database with no `alembic_version`, `init_schema`
(`db/session.py:164-248`) builds it with `Base.metadata.create_all()` and stamps `head` — every
revision recorded as run, none of them executed. The docstring calls that the test-fixture path;
Alpha's shape (no RLS, no server defaults, SQLAlchemy's constraint names) says it was also how
Alpha was born. So the chain this lane certifies has never produced the one database the app has
actually run on.

The divergence that bites is RLS. `a4c7e9d10001` enables and **forces** row-level security keyed
on a session GUC, `app.user_id`, and its docstring says the backend sets it per request "see
`app.db.session.use_user`". Nothing sets it: `grep app.user_id backend/app` → 0 hits, and
`git log -S 'def use_user'` → no commit has ever defined that function. Demonstrated on the
chain-built database:

```
superuser sees 1                      (SELECT count(*) FROM users)
non-superuser sees 0                  (role NOSUPERUSER NOBYPASSRLS, full table grants)
ERROR:  new row violates row-level security policy for table "users"   (INSERT as that role)
```

**Failure scenario, concrete:** `/promote-to-alpha` step 5 now runs `alembic upgrade head` *before*
the container serves. Point that same procedure at a fresh Beta database and it gets the chain's
schema — RLS forced on `users`, `mandates`, `sim_*`, `room_runs`, `journal_entries`, … Run the API
under any role without `BYPASSRLS` — which is exactly what `a4c7e9d10001` itself tells the
operator to do on Supabase ("run the API server under `authenticated`/`anon` roles, not
`postgres`"), and Supabase is the stated Beta/Prod target — and every user-scoped read returns
nothing and every write is refused. Boot the app first instead and `create_all` builds the Alpha
shape: no RLS at all, while `alembic_version` says the RLS migration ran. Which schema Beta gets
depends on start order; neither is the one this lane's guards test.

Pre-existing (the RLS revision is May; `init_schema`'s create-and-stamp predates the window). It
is in scope because this lane's own attack surface asks for exactly this ("edited-after-applied
divergence between Alpha's actual state and the repo") and because CR231 runs this lane to clear
the path to beta — a COMPLETE here would certify a chain that provisions a different database from
the one in production.

**Fix — two decisions, then a guard:**
1. Decide RLS: either implement the per-request `SET LOCAL app.user_id` the migration promises, or
   ship a revision that removes the policies. Either way, one intention in both build paths.
2. Make a fresh non-SQLite database migration-built only: `init_schema` should run
   `alembic upgrade head` (or refuse to boot) rather than `create_all` + stamp when the dialect is
   Postgres.
3. Guard: a check that diffs Alpha's `pg_dump --schema-only` against a chain-built throwaway
   (this audit's procedure) — on melehost, run at promotion, so the next divergence is named when
   it happens rather than found in a beta outage.

### MINOR-1 — one in-window migration does backfill existing rows, contrary to the submission

"None of the migrations in this window run a backfill against existing rows" — false.
`a309a000001c` (DEF309, `1ecc0e63`, 2026-08-15) runs:

```sql
UPDATE sim_resting_orders
   SET retired_at = COALESCE(filled_at, placed_at)
 WHERE state IN ('filled', 'cancelled', 'expired', 'rejected')
   AND retired_at IS NULL
```

A Tier A migration by the binding's own words, never through this handshake. I audited it now:
idempotent (`retired_at IS NULL`), confined to terminal states, the approximation disclosed in its
own docstring, downgrade drops the column and index; on Alpha 5 of 5 terminal rows carry
`retired_at`. The backfill is sound — the record is what is wrong, and a reviewer relying on it
would have skipped the one data-touching revision in the window. Every other in-window file I
read (`grep` for `op.execute|UPDATE|INSERT|DELETE|alter_column|server_default`, then the hits):
additive DDL and server defaults on new tables only.

### Evidence, run bare in the pinned worktree

```
pytest test_def278_migrations_are_immutable.py test_def337_migration_self_collision.py \
       test_def406_single_migration_head.py -q -p no:cacheprovider
14 passed in 3.92s
pytest test_p15_check_then_insert_guard.py test_def220_check_then_insert_outcomes.py -q -p no:cacheprovider
12 passed in 2.28s
```

Both match the submission (14, 12).

Full backend unit suite, `34941fa1`, on melehost (the deploy target) — `git archive` tree in a
throwaway container built from the Alpha API image plus pytest, `/tmp` on tmpfs, split into three
file-shards capped at 0.9 CPU each so live Alpha kept a core; run bare, exit code read from each
shard's own log:

```
shard 0   2103 passed, 2 skipped                         EXIT=0
shard 1   2194 passed, 2 skipped, 2 failed               EXIT=1
shard 2   2433 passed, 5 skipped, 4 failed, 4 errors     EXIT=1
total     6730 passed, 9 skipped, 6 failed, 4 errors
```

All ten non-passes are one environmental cause: the image has no `git` binary
(`FileNotFoundError: [Errno 2] No such file or directory: 'git'`) and those files shell out to it
— `test_def278_…immutable`, `test_def405_…`, `test_cr216_…`, `test_def178_…`, `test_p30_…`.
Re-run bare on the Mac in the pinned worktree, where git exists:

```
pytest test_def278_… test_def405_… test_cr216_… test_def178_… test_p30_… test_cr175_readiness.py
42 passed, 2 failed
FAILED test_p30_registers_name_things_that_exist.py::test_every_file_a_register_row_claims_actually_exists
FAILED test_p30_registers_name_things_that_exist.py::test_no_new_register_identifier_is_absent_from_the_codebase
```

Those two are real and belong to `34941fa1` itself — the CR231 governance commit this lane rests
on added DEF416–418 rows with `../../../backend/…` links and an uncited identifier
(`check_dry_run_compliance`). Already fixed on `main` by `8e550a57`; not this lane's code, not a
finding here. At `8c43c88e` those rows do not exist. (An earlier unsharded attempt also tripped
`test_cr175_readiness::test_unstamped_build…` because the image carries `GIT_SHA`; with it unset
the test passes, as it does on the Mac.) Totals reconcile to 6749 of the 6751 the Mac collects for
this tree; the two-test gap is untraced.

Nothing product-side fails at this SHA.

FOREIGN: not run — no `foreign/RETRO-MIGRATIONS.r1` branch exists, and this audit's brief limits
writes to the lane, run and ledger files. Not a clean bill.

### Verdict

Everything the lane claimed about the chain holds, and I ran the parts nobody had: base to head,
head to base and back again on real Postgres, all clean, and DEF411's digest reproduces to the
character. What the lane could not see without a fresh database is that the chain and production
disagree — Alpha was built around the migrations, not by them, and the chain carries a forced
row-level-security layer keyed on a variable the application has never set. That is the first
thing a fresh Beta database would meet.

VERDICT: AWAITING_FIXES (round 1)
