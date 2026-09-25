<!--
run_report.md: auditor run report for RETRO-SECURITY round 3 (U68). It holds the evidence behind
the round-3 verdict in orchestration/audit/cr/RETRO-SECURITY.auditor.md, plus the RETRO-PM-FLOOR
post-COMPLETE spot-check (no verdict owed).
-->

# 2026-09-25: RETRO-SECURITY round 3 (auditor U68)

**SHA audited:** `685dbdd0` (fixes `aa17a2d1` and `685dbdd0`; the PM-FLOOR minors are `429682c1`).
**Verdict:** `AWAITING_FIXES`, with 0 BLOCKER, 1 MAJOR open (MAJOR-1, on `_ensure_period`) and
0 MINOR.

## Environment

- **Pinned tree:** detached worktree `.claude/worktrees/audit-U68-R3` at `685dbdd0`, removed at
  the end. Probe files were untracked scratch, recovered from my round-2 transcript and deleted
  with the tree.
- **Interpreter (Mac):** `/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python`, run bare.
- **Throwaway Postgres (melehost):** `postgres:15-alpine` container `audit_u68_r3_pg` on isolated
  network `audit_u68_r3_net`, built by `alembic upgrade head` -> `m111a0def416x417`. The probes ran
  in `--rm` containers from the Alpha API image with `git archive 685dbdd0` mounted read-only.
  Everything was removed after.
- **Full suite (melehost):** image `audit_u68_r3_pytest:tmp` (Alpha image plus pytest), 3 shards on
  `--tmpfs /tmp` at `--cpus 0.9`, with `env -u GIT_SHA -u ALPHA_TAG`. The 5 git-dependent files ran
  on the Mac. Removed after.
- **Live Alpha:** not touched. It still runs `0accfeed`.

## Postgres credit races (real functions; a concurrent `spend(1)` commits between the caller's load and its first lock)

| Probe | Expected | Final |
|---|---|---|
| `refund_vs_spend` | 5 | 5 |
| `pack_vs_spend` (webhook shape) | 14 | **14** (round 2: 15) |
| `admin_vs_spend` (real `adjust_credits`) | 5 | **5** (round 2: 6) |
| `streak_vs_spend` (`_grant_milestone(7)`, spend right after the load) | 9 | 9 |
| `plan_renew_vs_spend` (same period, no re-grant) | 4 | 4, and `grant.old_balance`=4 |
| `merge_vs_spend` (real `MergeService.execute`) | 11 | 11, and the orphan row is deleted |
| `rollover_pack_sequential` (the builder's flush-bug shape) | 160 | 160 |
| `revoke_sequential` | 13, plan floor_pass | 13, plan floor_pass |
| `rollover_balance_for_vs_spend` | 149 | **150** |
| `rollover_pack_vs_spend` | 159 | **160** |
| `rollover_balance_for_vs_pack` (a pack webhook is the concurrent writer) | 160 | **150** (the paid pack is erased) |
| rollover, sequential control | 149 | 149 |
| rollover, `_ensure_period` re-checked after the lock (control fix) | 149 / 159 | 149 / 159 |

The first streak attempt hooked `_lock_user_row`. It deadlocked the probe, because `award()`
already holds the row through its `users.reputation` write, and the hook joins a spend that waits
on that lock. That is an artefact of the harness, not of the product: in the real flow the spend
simply waits for the commit. I re-ran it with the spend placed right after the load.

## Real-provider refund probes (real `LLMGateway` + `OpenAICompatibleProvider`, `httpx.MockTransport`)

| Surface | Failure | Charged |
|---|---|---|
| 1-on-1 concierge | HTTP 503 / ConnectError | **0 / 0** (round 2: 1 / 1) |
| 1-on-1 fundamentals_analyst | HTTP 503 / ConnectError | 0 / 0 |
| Brief | 503 / 429 / ConnectError | 0 / 0 / 0 |

## Mutations (each reverted, tree re-checked clean)

| Mutation | Result |
|---|---|
| drop `populate_existing=True` | 2 failed, 10 passed (lock guard) |
| drop `session.flush()` | 9 failed, 33 passed (cr084 webhook + guard) |
| drop the Concierge outage `meta["stream_error"]` write | 1 failed, 13 passed (def113) |
| Brief refund back to a bare sync call | ratchet FAILED, `brief.py::event_stream` |
| PM-FLOOR: respawn-abandon refund disabled | probe refunded=0; `test_respawn_fails_loudly…` FAILED |

## RETRO-PM-FLOOR post-COMPLETE spot-check (no verdict owed)

- Conflict -> `PASS` with `reformat_calls=0`, including when the reformatter answers APPROVE.
- `extract_json_object` returns `ConflictingDecision` on the quoted-brace and non-action-first
  tails. A same-action echo stays APPROVE.
- A respawn snapshot failure now refunds 3 of the 3 credits charged.
- The matrix, sector, holdings and respawn probes are unchanged: `33 passed`.

## Full suite at `685dbdd0`

Full unit suite at `685dbdd0`. The melehost part ran in a throwaway container from the Alpha
image, 3 shards on tmpfs. The 5 git-dependent files ran on the Mac. All runs were bare, and I
read the exit codes directly:

```
melehost s0   2128 passed, 2 skipped              EXIT=0   (test_def200_ratchet green; red at ae468eff)
melehost s1   2672 passed, 3 skipped              EXIT=0
melehost s2   1 failed, 2015 passed, 4 skipped    EXIT=1   test_def247_displaced_stance_envelope.py::test_a_displaced_envelope_is_still_reported
Mac (5 git-dependent files)  34 passed            EXIT=0
total         6849 passed, 1 failed, 9 skipped
```

The one failure is the order-dependent `test_def247` failure diagnosed in round 2. It is
pre-existing: it fails the same way in shard order at `0accfeed`, passes alone, and passes in
the default order. It was recorded out of scope there and is not caused by this round. Nothing
in the suite fails because of round 3.

FOREIGN: not run. There is no `foreign/RETRO-SECURITY.r3` branch.
