<!--
run_report.md: auditor run report for DEF425 round 1 (U68). It holds the evidence behind
orchestration/audit/cr/DEF425.auditor.md.
-->

# 2026-09-25: DEF425 round 1 (auditor U68)

**SHA audited:** fix `18e1c0a3`, merged `b5de455c`, main `16990d51`. **Verdict:** `AWAITING_FIXES`,
with 0 BLOCKER, 1 MAJOR and 1 MINOR.

## Throwaway stack (melehost)

- **Network, database, cache:** `audit_u68_q_net`, Postgres `audit_u68_q_pg` (at head
  `m111a0def416x417`) and Redis `audit_u68_q_redis`.
- **API:** `audit_u68_q_api`, the Alpha image running `uvicorn` on a `git archive 16990d51` tree,
  with `AMI_ENV=local`, the mock LLM provider and `USE_REAL_MARKET_DATA=false`. AAPL and MSFT were
  seeded into `ticker_reference`.
- **Driver:** a scratch script that creates an anonymous user through `/v1/auth/anon` and convenes
  through `/v1/room/stream` (SSE).
- **SIGTERM:** `docker stop -t 10`.
- Everything was removed at the end.

## Drills

| Drill | Result |
|---|---|
| Baseline, full run | completed in 24s, 8 credits (13 → 5) |
| D1: SIGTERM at ~8s, immediate restart | `room_cancelled_shutdown` logged; the row stays `running`, retry 0, balance 5 at +20s and +80s. Re-convening the same ticker returns the same dead run id and the stream ends `done` with no verdict. Journal: "Room on AAPL — running" |
| D2: same row aged 31 min, restart | swept, respawned, completed REJECT, one `credits_spent`. Journal now holds 2 entries (running + REJECT) |
| D3: SIGTERM, row at retry budget and aged, boot twice | failed, refunded 5 → 13 once, no second refund on boot 2. Journal still says "running" |
| D4: client disconnects at 5s, no restart | completed, charged once, 1 journal entry |

## Tests

`test_def425_shutdown_cancel_no_refund_gap.py` and `test_def424_llm_down_branded_fallback.py`:
13 passed, EXIT=0. The DEF425 sweep tests backdate `started_at` by 1 hour (`:188,245,296`).

FOREIGN: not run.
