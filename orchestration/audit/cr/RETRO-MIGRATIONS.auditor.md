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

## Round 2 — auditor u66

U68 is decommissioned; u66 takes the lane from round 2. **SHA audited:** `3197b9bf` (main HEAD),
detached worktree `ami_wt/RETRO-MIGRATIONS-u66`, verified clean after probes and removed. Mac only:
no Postgres, no melehost. Every line below says whether I ran it or read it. Nothing here was run
against a real database. The Postgres evidence is U68's round 1 plus the DEF416/DEF417/DEF425
lanes' own throwaway-Postgres runs, and I cite those as theirs.

### The rescope: honest in substance, and it holds on the three probes

1. **Can anything build a database from the chain before CR126?** No.
   - `deploy-beta.yml` is `workflow_dispatch`-only, needs GCP vars that do not exist yet, and runs
     no migration.
   - `tests.yml` has no Postgres service.
   - `grep` for `alembic … upgrade` / `command.upgrade` finds only `Dockerfile` comments,
     `session.py` (the check), `postflight.py` (the Alpha promotion), two guard tests,
     `alembic/env.py`, and one old audit probe.
   - The only Postgres service in any compose file is Alpha's.
   - A fresh Postgres booted by the app goes through `init_schema`'s `create_all` + stamp
     (`app/db/session.py:240,251`), not the chain. That is DEF421's own subject, not a way around it.
2. **Does anything on Alpha depend on the RLS or on `app.user_id`?** No.
   `grep -rn 'app\.user_id\|use_user' backend/app backend/scripts scripts` returns 0 lines. U68
   measured Alpha at 0 RLS-enabled tables and 0 policies.
3. **Is DEF421 accurate and open?** It exists (`docs/defect/_registry/DEF421.row.md`, `b0045b13`)
   with status `open`, marked as a Beta blocker. It names the forced RLS, the missing
   `use_user`, the NOSUPERUSER 0-rows / INSERT-refused demonstration, and the drift inventory. It
   does **not** carry all of round 1. See MAJOR-1.

Round 1's backfill finding stands, and I re-measured it across the whole chain.
`grep -E 'UPDATE|INSERT INTO|DELETE FROM'` over `alembic/versions/`, then reading each hit, finds
four `upgrade()` bodies that write rows:

- `8c5b1a70f4d2`: dedupe `DELETE`.
- `b4c5d6e70018`: two `UPDATE bug_reports`.
- `d5f2a3b00009`: `INSERT … ON CONFLICT DO NOTHING`.
- `a309a000001c`: round 1's in-window one.

The other hits are docstrings. The first three predate the 08-13 window. One note on
`b4c5d6e70018`: its second `UPDATE` stamps `acknowledged_at = NOW()` with no `IS NULL` guard, so a
manual re-run would overwrite it. Alembic never re-runs a revision, and the migration is outside
the window, so this is an observation, not a finding.

### The chain at `3197b9bf`: strong

Run bare in the worktree:

```
alembic heads                        def425a0interrupt1 (head)
ScriptDirectory walk                 76 revisions, heads ['def425a0interrupt1'], bases ['e355c2468b2a']
pytest test_def278_… test_def337_… test_def406_… -q        14 passed   EXIT=0
  + test_def215_schema_ownership.py                        20 passed   EXIT=0
```

Four revisions landed after round 1's `34941fa1`. I read all four and produced Postgres
`--sql` offline for each. Offline mode is meaningful only per range: the full base→head offline
run already dies at a pre-existing inspector-based repair (`NoInspectionAvailable`), which is not
new.

| revision | what it does | reversible | backfill / rows | covered on real Postgres by |
|---|---|---|---|---|
| `def416a0oidc0uq` | 3 partial unique indexes on `users` | `drop_index` ×3 | reads only: refuses and lists ids if duplicates exist, never deletes or merges | DEF416 r1 (COMPLETE): refused on a planted duplicate, then upgrade and downgrade both `EXIT=0` |
| `def417a0b0c0d1` | 2 JSONB columns `DEFAULT '{}'` | `DROP COLUMN` ×2 | implicit fill: existing rows read `'{}'`. One-shot DDL, correct per docstring | DEF417 lane round-trip |
| `m111a0def416x417` | merge, `pass`/`pass` | yes | none | DEF416 r1 (walks m111 → both parents → cr230) |
| `def425a0interrupt1` | nullable `room_runs.interrupted_at` | `DROP COLUMN` (offline SQL, run) | none. NULL is the stated correct value for old rows | DEF425 r2 (throwaway Postgres migrated to it) |

`def416a0oidc0uq` cannot run in offline `--sql` mode (`bind.execute(...)` returns `None` →
`AttributeError`, run). No path uses offline mode, and the chain was already offline-incompatible,
so this is not a finding.

### MAJOR-1 — DEF421 does not carry all of round 1, so part of the rescope is a silent drop

The round-2 claim rests on "MAJOR-1 … is DEF421; MINOR-1 travels with DEF421". Checked against
`DEF421.row.md:1`:

- **Round 1 fix step 2 is missing.** Step 2 said a fresh Postgres must be built by migrations
  only. The row describes Alpha as built by `create_all()`, but its "decide:" list has only two
  items: RLS, and reconciling Alpha's drift. It never names the mechanism,
  `_init_schema_locked`'s `create_all` + `stamp head` on any fresh non-SQLite DB
  (`app/db/session.py:240,251`). That mechanism is what made round 1's scenario depend on start
  order. If CR126 implements `app.user_id` and a Supabase DB is first booted by the app, the RLS
  migration is stamped as run and never executes, and the security control is silently absent
  again. Reconciling the drift without closing that path only resets the divergence.
- **Round 1 fix step 3 is missing.** Step 3 was the guard: diff Alpha's schema against a
  chain-built throwaway at promotion. House rule: an entry without an enforcing check is not done.
- **MINOR-1 is carried nowhere.** The row does not mention it, and the lane file's
  "no backfills in this window" sentence still stands uncorrected. MINOR-1 has nothing to do with
  RLS, so "travels with DEF421" leaves it without a home.

This is MAJOR on the protocol's doubt rule. The fix is small and needs no code, but the
rescope is legitimate only if the tracked item holds the whole finding, and today it holds part
of it. **Fix:**

1. Amend `DEF421.row.md` so its "decide:" list also has (a) "fresh Postgres builds by
   migrations only: `init_schema` runs `alembic upgrade head` or refuses to boot, instead of
   `create_all` + stamp" and (b) "guard: diff the chain-built schema against the live schema at
   promotion".
2. Regenerate `def_list.md`.
3. Add one correcting line to this lane file naming `a309a000001c` as the in-window backfill (and
   U68's soundness finding on it).

Then this lane can close.

### MINOR-1 — the round-2 inventory is wrong, and at this SHA the head is not on Alpha

"The one migration added since your round, `m111a0def416x417`": in fact three revisions were new
against `34941fa1` when the claim was written at `380e825d`: `def416a0oidc0uq`, `def417a0b0c0d1`
and `m111`. At the audited SHA there are four. `def425a0interrupt1` (`9160660f`, 08:48, an hour
after the submission) is the head, and it is in no `alpha-*` tag. I listed each tag's
`backend/alembic/versions/`: `alpha-2026-09-25-4` (`685dbdd0`) has 75 files and no `def425`.
So "Alpha at head" is false at `3197b9bf`, and the next promotion will apply `def425a0interrupt1`.
In substance this is sound: all four revisions are additive and reversible, and each was
exercised on Postgres by its own lane (table above). The record needs correcting. **Fix:** name
all four revisions in the lane file, and state that Alpha sits at `m111a0def416x417`, one behind
head, until the next promotion. I cannot re-query Alpha from the Mac. The `m111` reading is from
DEF416 r1 at `alpha-2026-09-25-4`.

### MINOR-2 — a new chain vs `create_all` divergence, filed after DEF421

`def417a0b0c0d1:42,48` gives `market_caps` / `avg_volumes` a server default `'{}'`. The model
(`app/db/models.py:1422-1423`) has only Python `default=dict`, with no `server_default`. Alpha got
these columns through the chain, so it has the default. A DB born through `init_schema` would not.
This is the same class as DEF421's 13 server defaults, but in the opposite direction, and it
landed after DEF421 was filed. **Fix:** add it to DEF421's reconciliation inventory, or add
`server_default` to the model. MINOR: the app always writes the value, and no DB is built that
way before CR126.

### Suite

Full suites were already run at `3197b9bf` and not re-run here: backend `7022 passed, 9 skipped`,
`FULL_EXIT=0`. Targeted guards, run bare in the worktree: 14 passed (DEF278/DEF337/DEF406, the
same three files and count as round 1) and 20 passed with DEF215 added, both `EXIT=0`.

FOREIGN: not run. No `foreign/RETRO-MIGRATIONS.r2` branch exists. This is not a clean bill.

### Verdict

The chain is in good shape. It has one head across 76 revisions. The four revisions since round 1
are additive, reversible and each tested on Postgres. The four row-writing migrations in the
repo's history are correct and effectively one-shot. Narrowing the lane to the Alpha chain is the
right call: nothing builds a DB from the chain before CR126, and nothing on Alpha touches RLS.
What is not yet true is the premise the narrowing rests on, that DEF421 carries the fresh-DB
finding. It carries the RLS half. It drops the dual-build mechanism, the guard and MINOR-1. That
is one registry-row edit and one correcting line away from closing.

VERDICT: AWAITING_FIXES (round 2)

## Round 3 — auditor u66

**SHA audited:** `70d99765`, docs only: `DEF421.row.md`, the regenerated `def_list.md`, and the
lane file. No code changed.

### MAJOR-1 from round 2 — fixed

I checked `docs/defect/_registry/DEF421.row.md` term by term. It now carries the following, each
present:
- round 1's step 2, a fresh Postgres built by migrations only (`create_all`, `stamp`,
  `upgrade head`, `refuse to boot`);
- step 3, the guard at promotion (`guard`, `promotion`);
- round 2's MINOR-2 drift (`def417a0b0c0d1`, `market_caps`, `models.py:1422`).

`def_list.md` has DEF421 regenerated. `test_registers_no_drift.py` and
`test_p30_registers_name_things_that_exist.py` give **10 passed**.

### Round 1's MINOR-1 and round 2's MINOR-1 — fixed

- The lane file now withdraws round 1's "no backfills in this window" and names
  `a309a000001c` (DEF309). That is the right home for it; DEF421 is about RLS and drift, not
  backfills.
- The four-revision inventory matches round 2's measurement.
- Alpha's position (`m111a0def416x417`, one behind the head `def425a0interrupt1`) is labelled
  as not re-measured from the Mac, which is correct.

### Suite

Docs only. The last full backend run was at `3197b9bf`: `7022 passed, 9 skipped`,
`FULL_EXIT=0`. The registers guards at this SHA give 10 passed.

VERDICT: COMPLETE (round 3)
