<!--
run_report.md: auditor run report for DEF425 round 2 (U68). It holds the evidence behind
orchestration/audit/cr/DEF425.auditor.md.
-->

# 2026-09-25: DEF425 round 2 (auditor U68)

**SHA audited:** fix `9160660f`, merged `d6a3b050`, drilled at `main` `3bfa4362` (the lane files
are unchanged at `2b34d61f`). **Verdict:** `AWAITING_FIXES`, with 0 BLOCKER, 1 MAJOR and 1 MINOR.

**Throwaway stack:** `audit_u68_q_*` on melehost, with the API on the HEAD tree, its own Postgres
migrated to `def425a0interrupt1`, and Redis. It used the mock LLM (a Room takes about 24s for
8 credits). Every stop was a real `docker stop -t 10`. That is what `/promote-to-alpha`'s
`compose up -d --build` does, and neither the compose file nor the Dockerfile sets a stop grace
or a uvicorn shutdown timeout.

| Drill | Setup | Result |
|---|---|---|
| A | client connected through the SIGTERM | stop 11s (SIGKILL after "Waiting for connections to close"); no mark; at boot +45s: running, retry 0, balance 5 (MAJOR-1) |
| A2 | as A, uvicorn `--timeout-graceful-shutdown 5` | marked; boot claims it; completed REJECT, charged once, one journal entry |
| B | client dropped, then a re-convene at boot +8s | marked, claimed at boot (retry 1), re-convene attaches to the retry, completed REJECT, one journal entry |
| C | SIGTERM, boot, SIGTERM mid-retry, boot, boot | failed and refunded once (5→13), no second refund; journal holds only "Room on MSFT — running" (MINOR-1) |
| Mutation | the shutdown branch does not stamp `interrupted_at` | 4 failed |
| Tests at `2b34d61f` | `test_def425_…` + `test_room_runner` | 114 passed, EXIT=0 |

FOREIGN: not run.
