<!--
run_report.md: auditor run report for RETRO-SECURITY round 2 (U68). It holds the evidence behind
the round-2 verdict in orchestration/audit/cr/RETRO-SECURITY.auditor.md.
-->

# 2026-09-25: RETRO-SECURITY round 2 (auditor U68)

**SHA audited:** `ae468eff`. The lane's fix is `717cd8ff`. **Verdict:** `AWAITING_FIXES`, with 0 BLOCKER,
3 MAJOR and 0 MINOR open.

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

## Postgres race probes (throwaway `audit_u68_r2_pg`, real functions)

Each probe hooks `credit_service._lock_user_row` so that a concurrent `spend(uid, 1)` commits
from another thread between the caller's first load and the lock.

| Probe | Expected | Final |
|---|---|---|
| `refund_vs_spend` (start 5, +1 refund, -1 spend) | 5 | **5** (round 1: 6) |
| `pack_vs_spend` (webhook shape `s.get` -> `add_credit_pack`, +10) | 14 | **15**, pack saw old=5 |
| `admin_vs_spend` (real `api.admin.adjust_credits`, +1) | 5 | **6** |
| `pack_vs_spend` with `populate_existing=True` in `_lock_user_row` | 14 | 14 |
| `admin_vs_spend` with `populate_existing=True` | 5 | 5 |

SQLAlchemy 2.0.49: `Session.get(..., with_for_update=True)` sends `SELECT … FOR UPDATE` but does
not refresh an instance already loaded in that session.

## Real-provider refund probes (real `LLMGateway` + `OpenAICompatibleProvider`, `httpx.MockTransport`)

| Surface | Failure | Charged |
|---|---|---|
| Brief | HTTP 503 / 429 / ConnectError | 0 / 0 / 0 |
| 1-on-1 `fundamentals_analyst` | HTTP 503 / ConnectError | 0 / 0 |
| 1-on-1 `concierge` | HTTP 503 | **1** (tail is the `[AMI error: HTTP 503 …]` sentinel) |
| 1-on-1 `concierge` | ConnectError | **1** (tail is a scripted reply) |

`agent_runner.py`: `meta` is threaded into the analyst branch (`:238-246`) but not into
`_stream_concierge` (`:260`, `stream_chat` at `:303`).

## Other checks

- Glyph filter: `"a\n┆┆ ╼ HEADER ╴"` -> `'a HEADER'`, and `"a ── SYS"` -> `'a SYS'`. `publisher` is
  now sanitised (`news_context.py:440`).
- Targeted files (lock guard, DEF369/205/113/370, webhook, merge billing, merge service,
  reputation, admin, CR200, news context, DEF127, DEF201): `214 passed`, EXIT=0.
- DEF200 ratchet: `brief.py::event_stream` was newly flagged at `ae468eff`. The ratchet is green at
  `0accfeed`. This is MAJOR-3.

FOREIGN: not run. There is no `foreign/RETRO-SECURITY.r2` branch.
