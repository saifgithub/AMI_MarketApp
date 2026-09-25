<!--
run_report.md: auditor run report for RETRO-SECURITY round 4 (U68). It holds the evidence behind
the round-4 verdict in orchestration/audit/cr/RETRO-SECURITY.auditor.md.
-->

# 2026-09-25: RETRO-SECURITY round 4 (auditor U68)

**SHA audited:** `6d3be5fc` (fix `90a3af56`). **Verdict:** `COMPLETE`, with 0 BLOCKER, 0 MAJOR and
0 MINOR open.

## Environment

- **Pinned tree:** detached worktree `.claude/worktrees/audit-U68-R4` at `6d3be5fc`, removed at
  the end.
- **Interpreter (Mac):** `/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python`, run bare.
- **Throwaway Postgres (melehost):** `postgres:15-alpine` container `audit_u68_r4_pg` on isolated
  network `audit_u68_r4_net`, built by `alembic upgrade head` -> `m111a0def416x417`. The probe ran
  in `--rm` containers from the Alpha API image, with `git archive 6d3be5fc` and
  `git archive 685dbdd0` (the pre-fix tree) mounted read-only. Everything was removed after.
- **Full suite (melehost):** image `audit_u68_r4_pytest:tmp` (the Alpha image plus pytest), 3 shards
  on `--tmpfs /tmp` at `--cpus 0.9`, run with `env -u GIT_SHA -u ALPHA_TAG`. The 5 git-dependent
  files ran on the Mac. Removed after.
- **Live Alpha:** not touched. It runs `alpha-2026-09-25-4` (`685dbdd0`).

## Postgres credit races (real functions; a concurrent writer commits between the caller's load and its lock)

| Probe | 685dbdd0 (r3) | 6d3be5fc (r4) | Expected |
|---|---|---|---|
| rollover: balance_for vs pack webhook | 150 | **160** | 160 |
| rollover: balance_for vs spend | 150 | **149** | 149 |
| rollover: webhook _ensure_period+pack vs spend | 160 | **159** | 159 |
| drift (expired admin trial): balance_for vs pack webhook | 13 | **23** | 23 |
| drift: balance_for vs spend | 13 | **12** | 12 |
| drift: webhook _ensure_period+pack vs spend | 23 | **22** | 22 |
| drift: sequential control | — | 23, re-tagged floor_pass | 23 |

These round-3 probes, re-run on `6d3be5fc`, show no regressions:

| Probe | Result |
|---|---|
| refund | 5 |
| pack | 14 |
| admin | 5 |
| streak | 9 |
| plan_renew | 4 |
| real MergeService merge | 11 |
| rollover_pack_sequential | 160 |
| revoke_sequential | 13 |

## Mutations (each reverted, tree re-checked clean)

| Mutation | Result |
|---|---|
| re-check computed but ignored (`if False: return eff`) | 2 failed, 12 passed (the builder's rollover + drift tests) |
| `plan_drifted` dropped from the post-lock check | guard file 14 passed (survives there); across 24 credit test files 1 failed, 420 passed (`test_cr039…test_trial_lapse_regrants_immediately_not_at_month_rollover`) |

## Full suite at `6d3be5fc`

| Part | Result | Exit |
|---|---|---|
| melehost s0 | 2130 passed, 2 skipped | 0 |
| melehost s1 | 2672 passed, 3 skipped | 0 |
| melehost s2 | 1 failed, 2015 passed, 4 skipped (`test_def247…`, pre-existing and order-dependent; see the round-2 report) | 1 |
| Mac, 5 git-dependent files | 34 passed | 0 |

FOREIGN: not run. There is no `foreign/RETRO-SECURITY.r4` branch.
