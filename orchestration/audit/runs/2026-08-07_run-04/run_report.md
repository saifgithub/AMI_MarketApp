# Run report — 2026-08-07_run-04

Item: CR124, round 3. SHA: `93fce6a7`. Verdict: AWAITING_FIXES (round 3) — 1 MAJOR
(environmental: no live measurement, not a code defect), 0 BLOCKER, 0 MINOR. Full findings in
`orchestration/audit/cr/CR124.auditor.md`.

## Context — concurrent-session housekeeping note

Between my round-1 push (`741591af`) and this pass, a second auditor instance (tag `AT:U66`)
independently audited round 2 (`d8e9466e` — architect's fix for my MAJOR-1 digest gap) and
reconfirmed my MAJOR-2/MAJOR-3 findings still stood unaddressed, verdict `AWAITING_FIXES (round
2)`, committed/pushed as `7fe71bf0`. That commit touched only the lane file — no run report, no
audit-trail row (protocol's "Done (per item)" wasn't fully executed for that round). The
architect then shipped a further fix (`93fce6a7`, commit-labeled "round 2" again but landing
after U66's round-2 verdict, so functionally round 3) addressing all remaining findings: the
runbook safety claim, the yfinance cache regression, and both MINORs (REDISCLI_AUTH and
`01_website_role.sql` coverage). This report covers my independent audit of that commit.

## Setup

```text
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add .claude/worktrees/audit-CR124-r3 93fce6a7
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```text
cd .claude/worktrees/audit-CR124-r3/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2591 passed, 13 warnings in 301.20s (0:05:01)
```

`test_cr124_compose_hardening.py` now 21 tests (17 round 1 → 18 round 2 → 21 round 3).

## Fresh mutations, all three new guards, all confirmed correct

- Deleted `ENV HOME=/data` from `backend/Dockerfile` →
  `test_the_backend_image_gives_the_non_root_user_a_writable_home` fails alone (`assert []`), 20
  others pass.
- Deleted `REDISCLI_AUTH` from redis's `environment:` in `docker-compose.yml` →
  `test_the_redis_healthcheck_can_actually_authenticate` fails alone (`assert False`), 20 others
  pass.
- Deleted `REVOKE CONNECT ON DATABASE ami_trade FROM PUBLIC;` from
  `infra/local/postgres-init/01_website_role.sql` →
  `test_the_website_role_sql_actually_restricts_the_app_database` fails alone, 20 others pass.

Tree restored and diffed byte-identical to pre-mutation backups after each (`diff` clean, no
`git status --short` residue).

## Findings

All 3 MAJOR + 2 MINOR from round 1 (mine) and round 2 (U66's reconfirmation) are fixed and
independently re-verified this round via fresh file:line reads and fresh mutations — not relayed
from either prior pass. Zero code-level BLOCKER/MAJOR/MINOR remain.

**One item still withholds COMPLETE, unchanged since round 1: no measurement in this CR has been
taken live.** SSH to melehost remains down (DEF224), no Docker daemon exists on the Mac, and
CR124's entire acceptance list is live probes against melehost. The C3 exposure is, by the
architect's own repeated statement, still live on melehost right now. Judged (as in round 1) that
this alone is legitimate grounds for AWAITING_FIXES on a security-hardening CR — marking COMPLETE
would move the item to `done` in the register while the vulnerability it exists to close remains
open in production. Full reasoning in the lane file's final section.

## Worktree cleanup

```text
git worktree remove .claude/worktrees/audit-CR124-r3
```
