<!--
run_report.md: auditor run report for RETRO-SIM-OPTIONS round 2 (U68). It holds the evidence behind
the round-2 verdict in orchestration/audit/cr/RETRO-SIM-OPTIONS.auditor.md.
-->

# 2026-09-25: RETRO-SIM-OPTIONS round 2 (auditor U68)

**SHA audited:** `ae468eff`. The lane's fix is `3e822fa5`. **Verdict:** `COMPLETE`, with 0 BLOCKER,
0 MAJOR and 2 MINOR open.

## Environment (shared across U68's three round-2 lanes)

- **Pinned tree:** detached worktree `.claude/worktrees/audit-U68-R2` at `ae468eff`, plus
  `.claude/worktrees/audit-U68-R2base` at `0accfeed` (the live Alpha SHA) for the two regression
  checks. Both were removed at the end. Probe files were untracked scratch and were deleted with
  the tree.
- **Interpreter (Mac):** `/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python`, run bare with no pipe.
- **Full suite (melehost):** `git archive ae468eff` was extracted under `~/audit_U68_r2/` and run
  in a throwaway container from the Alpha API image with pytest added (`audit_u68_r2_pytest:tmp`).
  The run used `--tmpfs /tmp`, 3 shards at `--cpus 0.9`, and `env -u GIT_SHA -u ALPHA_TAG`. The 5
  git-dependent files ran on the Mac. The image, container and scratch dir were all removed after.
- **Throwaway Postgres:** `postgres:15-alpine` container `audit_u68_r2_pg` on isolated network
  `audit_u68_r2_net`, built by `alembic upgrade head` -> `m111a0def416x417`. Removed after.
- **Live Alpha:** read-only. `alpha-2026-09-25-3` / `0accfeed` does not carry the round-2 fixes.
  Two `SELECT`s: 0 of 54 current mandates allow derivatives, and there are 0 rows in `sim_option_legs`.

## Full suite at `ae468eff`

| Part | Result | Exit |
|---|---|---|
| melehost s0 | 1 failed, 2126 passed, 2 skipped (`test_def200_ratchet`) | 1 |
| melehost s1 | 2669 passed, 3 skipped | 0 |
| melehost s2 | 1 failed, 2013 passed, 4 skipped (`test_def247…displaced_envelope_is_still_reported`) | 1 |
| Mac, 5 git-dependent files | 34 passed | 0 |

- `test_def200_ratchet` fails alone at `ae468eff` and passes at `0accfeed` (`4 passed`). The cause
  is `brief.py::event_stream`'s sync `refund()`, from RETRO-SECURITY `717cd8ff`. Graded as
  RETRO-SECURITY MAJOR-3.
- `test_def247…` passes alone. Shard 2's first 95 files, run in shard order on the Mac, give
  `1 failed, 1474 passed` at **both** `ae468eff` and `0accfeed`. So the failure is pre-existing
  and order-dependent (structlog `capture_logs` versus a logger cached earlier in the same
  process), and not caused by round 2.

## Probes (my round-1 merge probe, re-run unchanged, plus the other branch)

| Branch | Observed |
|---|---|
| Both accounts have portfolios (the destructive branch) | adopter total value 10000.0 -> 10000.0 (+0.00), AAPL held 0 / locked 0, dangling legs 0, `sim_option_legs_dropped=2` (round 1: +4650.00, locked 100 / held 0) |
| Adopter has no portfolio (the whole portfolio is re-keyed) | adopter total value 0.0 -> 60814.0 (= orphan total value), AAPL held 100 / locked 100, dangling legs 0 |
| `_size_to_budget(put 95, budget $9,000)` | "…risks 1.00x the budget" for a $9,030 loss (MINOR-3, still open) |

- Mobile consent sheet: `merge_sheet.dart:90-104,132,196` and `app_en.arb`
  `mergeSheetBody` / `mergeSheetConfirm` ("MERGE EVERYTHING") show no option count. This is MINOR-4.
- Live, read-only: 0 of 54 current mandates allow derivatives, and there are 0 `sim_option_legs`.

## Mutations (reverted, tree re-checked clean)

- Round-1 re-key (`update(SimOptionLegRow)` and `update(SimOptionTradeRow)` into the target) put
  back: `5 failed, 3 passed`, including both invariant tests.

FOREIGN: not run. There is no `foreign/RETRO-SIM-OPTIONS.r2` branch.
