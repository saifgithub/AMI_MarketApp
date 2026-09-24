<!--
run_report.md — auditor run report, RETRO-PM-FLOOR round 1 (U68). Evidence behind the verdict in
orchestration/audit/cr/RETRO-PM-FLOOR.auditor.md.
-->

# 2026-09-25 — RETRO-PM-FLOOR round 1 (auditor U68)

**SHA audited:** `34941fa1`. **Verdict:** `AWAITING_FIXES` — 2 MAJOR, 2 MINOR.

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

## Probes (scratch test files in the pinned worktree, never committed)

| Probe | Command / setup | Observed |
|---|---|---|
| Floor on every PM path | real `RoomRunner.run`, always-APPROVE fake gateway, ticker blocklisted; samples {1,5} x reply {clean, prose->reformat, JSON+brace tail} x grammar {off,on} x Risk Officer {off,on} | `24 passed`, every verdict `REJECT`, `ticker MSFT in user blocklist` |
| Respawn floor inputs | drawn-down user (50% vs 30% cap); api-path `run(portfolio_value, dd)` vs `_respawn_run_from_row` | api-path `REJECT` (drawdown); respawn `APPROVE`, `viol=[]` |
| Sector-context failure | 2 held, `max_open_positions=2`, `default_sector_map` raises | control `REJECT` (max_open_positions); failure `APPROVE`, `viol=[]` |
| Zero-readable vote | samples=5, every PM draw prose | `APPROVE samples=None approve_votes=None reformat_calls=1`, no disclosure |
| Two-object reply | `extract_json_object` at SHA vs `886355e4^` | SHA -> first object (`APPROVE`); pre-DEF398 -> `None` |

## Mutations (each reverted, tree re-checked clean)

DEF384 vote bypass -> 3 failed · DEF383 `.value` -> 2 failed · DEF059 outage APPROVE -> 1 failed ·
DEF067 reformat any -> 1 failed · DEF398 raw_decode off -> 5 failed · R51 cap off -> 6 failed.

## Live, read-only

- File hashes lane SHA = `alpha-2026-09-24-1` = `alpha-2026-09-25-1` = running container for
  `safety_floor.py` / `room_runner.py` / `schemas/room.py`.
- `printenv`: `PM_SELF_CONSISTENCY_SAMPLES=5`, `ROOM_JSON_CONSTRAINTS_ENABLED=true`,
  `ROOM_RISK_OFFICER_ENABLED=true`, `ROOM_TRADER_REGEX_ENABLED=true`, `ROOM_MAX_SCRIPTED_TURNS=4`.
- `llm_audit` 7 days: `room_pm enforced 351`, `room_risk_officer enforced 70`.
- `room_runs`: `retry_count=1` -> 3 completed PASS + 1 failed, latest 2026-08-14.

## Suites

Targeted (14 files): `333 passed in 159.12s`, EXIT=0.

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
