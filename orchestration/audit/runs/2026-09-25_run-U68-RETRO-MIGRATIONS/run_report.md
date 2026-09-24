<!--
run_report.md — auditor run report, RETRO-MIGRATIONS round 1 (U68). Evidence behind the verdict in
orchestration/audit/cr/RETRO-MIGRATIONS.auditor.md.
-->

# 2026-09-25 — RETRO-MIGRATIONS round 1 (auditor U68)

**SHA audited:** `34941fa1`. **Verdict:** `AWAITING_FIXES` — 1 MAJOR, 1 MINOR.

## Environment (shared across U68's four RETRO lanes, 2026-09-24/25)

- **Pinned trees:** detached worktrees `.claude/worktrees/audit-U68-PMFLOOR` (`34941fa1`) and
  `.claude/worktrees/audit-U68-SEC` (`8c43c88e`); `git archive 34941fa1` extracted on melehost
  under `~/audit_U68_scratch/` for the Postgres and full-suite runs. All removed at the end.
- **Interpreter (Mac):** `/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python`, bare, no pipe.
- **Full suite (melehost):** throwaway container from the Alpha API image with pytest added
  (`audit_u68_pytest:tmp`, removed after), tree mounted, `--tmpfs /tmp` (the first two attempts ran
  I/O-bound at ~1%/min on melehost's disk and were killed; nothing else differs).
  `8c43c88e..34941fa1` is 12 docs/register files, no source.
- **Throwaway Postgres:** `postgres:15-alpine` (same image as `ami_postgres`), container
  `audit_u68_pg` on isolated network `audit_u68_net`. Removed after.
- **Live Alpha:** read-only only — `printenv`, `docker logs`, `SELECT`s, `pg_dump --schema-only`,
  file hashes via `docker exec … cat`. No write to the live DB, no restart, no edit under `~/ami_trade/`.

## Throwaway Postgres runs

```
alembic heads            cr230a0order0log (head)
upgrade head  (empty)    72 upgrades   UPGRADE_EXIT=0
downgrade base           72 downgrades DOWN_EXIT=0   residue: alembic_version only
upgrade head  (again)    72 upgrades   REUP_EXIT=0   62 tables
```

## Schema diff, Alpha vs chain-built (pg_dump --schema-only, normalised)

139 diff lines. Chain has RLS enabled on 12 tables (forced on 11), 23 policies; Alpha has 0 / 0.
13 server defaults in 8 tables chain-only. `revenuecat_events` unique constraint named differently.
Alpha-only: `credit_backup_20260814`, `pgcrypto`, `uuid-ossp`.

RLS demonstration on the chain-built DB: superuser sees 1 user row; `NOSUPERUSER NOBYPASSRLS`
role with full grants sees 0; its INSERT fails `new row violates row-level security policy`.
`grep app.user_id backend/app` -> 0; `git log -S 'def use_user'` -> none.

## Other checks

- DEF411: `sha256(ast.dump)[:16]` upgrade `f17148e6de849606`, downgrade `fb351fc49dfbbe14` in both
  `6159a62b` and `839c3283`; only `down_revision` differs.
- Alpha: `alembic_version=cr230a0order0log`; `toll_charged` on 3 tables; `ix_edgar_8k_items_cik_filed`.
- DEF309 backfill `a309a000001c`: sound; Alpha 5/5 terminal resting orders dated.
- DEF406 guard mutation (second head) -> `FAILED test_the_real_repo_has_exactly_one_head`.

## Suites

Migration guards: `14 passed`; P15 guards: `12 passed`.

## Full suite

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
