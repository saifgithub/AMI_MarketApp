<!--
run_report.md — auditor run report, RETRO-SIM-OPTIONS round 1 (U68). Evidence behind the verdict in
orchestration/audit/cr/RETRO-SIM-OPTIONS.auditor.md.
-->

# 2026-09-25 — RETRO-SIM-OPTIONS round 1 (auditor U68)

**SHA audited:** `8c43c88e`. **Verdict:** `AWAITING_FIXES` — 1 MAJOR, 3 MINOR.

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

## Probes

| Probe | Setup | Observed |
|---|---|---|
| DEF368 destructive merge | orphan: 100 AAPL + covered call + $5k CSP; both users have portfolios | adopter NAV `10000 -> 14650` with cash unchanged; AAPL held 0, locked 100 (naked call) |
| Row-creating functions | enumerated every `Sim*Row(` constructor and its callers | floors at submit / fill_resting_order / open_option_structure; settlement allow-and-flag; game lane by design; merge none |
| Settlement arithmetic | hand re-derivation, 5 cases + ITM threshold + early assignment | all correct, NAV continuous |

## Mutations (each reverted)

DEF357 lifecycle call removed -> 2 failed (margin_sweep file; 0 in the cited lifecycle file) ·
DEF356 netting removed -> 1 failed · DEF311 retire removed -> 4 failed · DEF305 guard bypassed ->
2 failed · DEF310 phase 2 disabled -> 2 failed · DEF312 refusal bypassed -> 4 failed.

## Live, read-only

- `SIM_BRACKET_SWEEP_ENABLED=true` (container env and `.env`); flipped per Saiful 2026-08-26.
- Current mandates with `derivatives_allowed`: 0 / 52. `sim_option_legs` 0, `sim_option_trades` 0.
- Wrong-side brackets (census predicate as SQL): 3 historical `closed`, 0 active.
- `sim_resting_orders`: 5 terminal, 5 with `retired_at`.

## Suites

Targeted (33 files): `494 passed, 1 warning`, EXIT=0. Flutter DEF363: `+27: All tests passed!`, EXIT=0.

## Full suite

The source at `8c43c88e` is byte-identical to `34941fa1` (the 12 files between them are docs and register rows), so the full suite was run once, at `34941fa1`, for all four RETRO lanes.

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

Nothing product-side fails at this SHA or at `8c43c88e`.
