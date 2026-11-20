# ISS001 Phase 1 acceptance item 6 — `claim()` under real threads on real Postgres

**Date:** 2026-11-20 · **Verdict: PASS** · Founder's go (2026-11-20): throwaway schema only, drop after.

## Setup

1. Script: [`backend/scripts/iss001_pg_concurrency.py`](../../../../backend/scripts/iss001_pg_concurrency.py). Code under test: `backend/app/db/ami_claim.py` from branch `lane/iss001-pgtest` (copied to the container's `/tmp`, so the image's own copy was not what ran).
2. Ran inside `ami_api_alpha` (`docker exec -w /app`), using its `DATABASE_URL` (`postgresql+psycopg2`, SQLAlchemy 2.0.49). URL never printed. **1 run of the 3 allowed.**
3. Postgres: `PostgreSQL 15.18 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit`.
4. Isolation: schema `iss001_test_39798bea` created for the run; every pooled connection pinned `search_path` to that schema alone (asserted: `current_schemas(false) == [schema]`); the 5 tables were created there and `information_schema.tables` for the schema matched exactly those 5. No application table was touched.
5. Load: **8 real threads x 15 rounds** per cell, one `threading.Barrier` release per round, one session + one transaction per thread.

## Results (all cells: 15 rounds, 15 creators, 0 IntegrityError, 0 other errors, 1 row per key)

| # | Table / key shape | Mode | Losers (7/round = 105) | Result |
|---|---|---|---|---|
| 1 | `t_plain`, plain unique key | `or_skip` | 105 got the winner's row | PASS |
| 2 | `t_plain`, plain unique key | `or_raise` | 105 raised `Collision` | PASS |
| 3 | `t_update`, plain unique key + counter | `or_update` | 105 got the winner's row; counter `n == 7` every round | PASS |
| 4 | `t_nullkey`, run_id NULL (partial-index arbiter, DEF499 shape) | `or_skip` | 105 got the winner's row | PASS |
| 5 | `t_nullkey`, run_id NULL | `or_update` | 105 got the winner's row; `n == 7` every round | PASS |
| 6 | `t_nullkey`, run_id NULL | `or_raise` | 105 raised `Collision` | PASS |
| 7 | `t_nullkey`, run_id NOT NULL (full-constraint arbiter) | `or_skip` | 105 got the winner's row | PASS |

Also: `claim()` on the NULL-key table **without** the partial index raised `NoArbiter` (refused to run) on Postgres, as on sqlite.

Measured in this run, so no longer design-only: `ON CONFLICT (user_id, kind) WHERE run_id IS NULL` infers the partial index; the READ COMMITTED re-read after a lost race returns the winner's committed row; a loser blocked behind an uncommitted winner resumes correctly.

## Control — the old read-then-insert pattern, same load (8 x 15)

| Table | Pattern | Result |
|---|---|---|
| `t_ctl_null` (DEF499 table, no partial index, run_id NULL) | SELECT, INSERT if absent | **15 of 15 rounds produced duplicates**; 104 extra rows, no error raised (silent) |
| `t_ctl_plain` (plain unique key) | SELECT, INSERT if absent | **15 of 15 rounds hit IntegrityError**; 100 errors escaped |

So the harness can see the failure: it is not green because the race never fires.

## Cleanup

1. `DROP SCHEMA "iss001_test_39798bea" CASCADE` ran in a `finally`.
2. In-script check, `select count(*) from information_schema.schemata where schema_name like 'iss001_test_%'` = **0**. Re-checked independently after the run from a fresh connection = **0**.
3. Script and `ami_claim.py` removed from the container's `/tmp` and from melehost's `/tmp`.

## Caveats

1. One Postgres (15.18, Alpha's). Beta's Postgres version is not covered by this run; the NULL semantics (NULLS DISTINCT default) are the same on 15 and later, so the partial-index design holds there too, but it is not measured.
2. Alpha was idle-ish: 10 pooled connections, schema-local tables. This proves the guard's atomicity, not production throughput.
