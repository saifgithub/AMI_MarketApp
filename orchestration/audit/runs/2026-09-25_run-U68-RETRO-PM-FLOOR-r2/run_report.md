<!--
run_report.md: auditor run report for RETRO-PM-FLOOR round 2 (U68). It holds the evidence
behind the round-2 verdict in orchestration/audit/cr/RETRO-PM-FLOOR.auditor.md.
-->

# 2026-09-25: RETRO-PM-FLOOR round 2 (auditor U68)

**SHA audited:** `ae468eff`. The lane's fix is `692f9324`. **Verdict:** `COMPLETE`, with 0 BLOCKER,
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

## Probes (my round-1 probes, re-run on this tree)

| Probe | Observed |
|---|---|
| Respawn, drawn-down user | `status=completed action=REJECT` (round 1: APPROVE) |
| Respawn, snapshot read fails | `status=failed action=None`, error states the reason, `refunded=0` (MINOR-3) |
| Sector resolver fails, 2 held, cap 2 | `REJECT` max_open_positions (round 1: APPROVE) |
| Holdings read fails | `REJECT`, CR040 "caller did not supply holdings" block |
| 24-run matrix (samples x reply shape x grammar x Risk Officer), ticker blocklisted | all `REJECT` |
| Zero-readable vote, risk 2 | `APPROVE samples=5 approve_votes=0`; the reason text says it is not a vote |
| Two decisions: draft APPROVE then PASS, reformatter silent | `PASS` |
| Same, reformatter answers APPROVE | `APPROVE` (MINOR-2 residual 1) |
| Quoted-brace tail / non-action object first | `APPROVE` (MINOR-2 residual 2) |

## Mutations (each reverted, tree re-checked clean)

- Respawn kwargs removed: 1 failed.
- Sector-only failure branch returns `[]`: 1 failed.
- Conflict check disabled: 2 failed.

FOREIGN: not run. There is no `foreign/RETRO-PM-FLOOR.r2` branch.
