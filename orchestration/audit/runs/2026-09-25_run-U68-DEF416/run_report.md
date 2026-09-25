<!--
run_report.md: auditor run report for DEF416 round 1 (U68, taken over from U67). The evidence
behind orchestration/audit/cr/DEF416.auditor.md.
-->

# 2026-09-25: DEF416 round 1 (auditor U68)

**SHA audited:** lane `b51147f2`, merged and live at `685dbdd0` (`alpha-2026-09-25-4`). **Verdict:**
`COMPLETE`, 0 BLOCKER, 0 MAJOR, 1 MINOR.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L` at `685dbdd0`. The same worktree also
  serves U68's other takeover lanes today, and is removed at the end.
- **Throwaway Postgres (melehost):** `postgres:15-alpine` container `audit_u68_l_pg` on network
  `audit_u68_l_net`, with a `git archive 685dbdd0` tree mounted read-only. Databases:
  `audit_fresh` (at head) and `audit_mig` (migration probe). Removed at the end.
- **Live, read-only:** the image `GIT_SHA` and in-container file hashes, plus `SELECT`s on
  `alembic_version`, `pg_indexes` and `users` duplicate counts.

## Probes

| Probe | Observed |
|---|---|
| Live head / indexes / duplicates | `m111a0def416x417`; 3 partial unique indexes present; 0 dups (apple 5, google 47, hms 0 non-null) |
| Migration over seeded duplicates | EXIT=1, RuntimeError lists both ids; 2 rows remain; version stays `cr230a0order0log` |
| Upgrade head, downgrade to cr230, upgrade head | EXIT 0/0/0, single head `m111a0def416x417` |
| NULL vs NULL on Postgres | 3 all-NULL rows insert |
| Apple race, route shape (two existing anon rows) | loser: `IntegrityError uq_users_apple_id` (HTTP 500); 1 row; retry adopts into the winner |
| Google race, route shape | loser: `IntegrityError users_email_key`; 1 row; retry adopts |
| Apple/Google race, lane's INSERT shape (no row for user_id) | both callers get the same id; 1 row |

## Mutations (reverted, tree re-checked clean)

| Mutation | Result |
|---|---|
| drop `uq_users_apple_id` from `User.__table_args__` | 2 failed |
| Apple recovery re-selects by `google_id` | 1 failed |

## Tests

- `test_def416_oidc_unique_race.py`, `test_p15_check_then_insert_guard.py`, `test_auth_service.py`
  and `test_auth_google.py`: 46 passed, EXIT=0.
- Full suite at `685dbdd0`: 6849 passed, 1 failed (the pre-existing, order-dependent
  `test_def247`), from U68's RETRO-SECURITY round-3 run.

FOREIGN: not run.
