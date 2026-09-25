<!--
run_report.md: auditor run report for DEF424 round 1 (U68). It holds the evidence behind
orchestration/audit/cr/DEF424.auditor.md.
-->

# 2026-09-25: DEF424 round 1 (auditor U68)

**SHA audited:** fix `18e1c0a3`, main `16990d51`. **Verdict:** `COMPLETE`, with 0 BLOCKER, 0 MAJOR
and 2 MINOR.

**Throwaway stack:** the same as DEF425 (`audit_u68_q_*`). The API was restarted with
`VLLM_BASE_URL` set to (a) the dead port `127.0.0.1:9` and (b) a stub that answers 503
(`audit_u68_q_503`). The user was on plan `trader` with 150 credits, driven through the real
routes. Everything was removed at the end.

| Probe | Result |
|---|---|
| Dead port, Brief (`market_analyst`) | branded "Technical Strategist, currently offline … fallback mode"; spent 1, refunded 1 |
| Dead port, 1-on-1 (`trader`) | branded "Execution Desk, currently offline … fallback mode"; spent 1, refunded 1 |
| Dead port, Room (MSFT) | NO_VERDICT with DEF336 outage copy; 0 raw-transport hits; charged 8, not refunded (recorded) |
| 503 stub, Brief and 1-on-1 | `[AMI error: HTTP 503 from the upstream provider (vllm). Check backend logs.]`; refunded (MINOR-1) |
| Mutation: Brief without `meta["stream_error"]` | 1 failed |
| `test_def424_llm_down_branded_fallback.py` + `test_def425_…` | 13 passed, EXIT=0 |

FOREIGN: not run.
