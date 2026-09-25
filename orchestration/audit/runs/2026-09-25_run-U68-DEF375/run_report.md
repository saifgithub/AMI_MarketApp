<!--
run_report.md: auditor run report for DEF375 round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/DEF375.auditor.md.
-->

# 2026-09-25: DEF375 round 1 (auditor U68)

**SHA audited:** lane `5e1b2ae6`, shipped in mobile `+111`. **Verdict:** `COMPLETE`, with 0 BLOCKER,
0 MAJOR and 1 MINOR.

| Run (scratch worktree `audit-U68-L`, Mac `flutter test`) | Result |
|---|---|
| tour_qa_config, tour_service_qa_skip, tour_ids and nav_change tests | 29 passed, EXIT=0 |
| Full mobile suite at +111 | 1688 passed, EXIT=0 |
| M1: production refusal removed | 1 failed |
| M2: `hasSeen` ignores the QA skip | 2 failed |
| M3: `'production'` parsed as internal | 1 failed |

## Reads

- **Where `AMI_QA_SKIP_TOURS` is forwarded:** only `build_qa_ios_sim.sh`. It is absent from all
  five shipping/install scripts, and none of them has a generic define passthrough.
- **`markSeen` guards:** all six call sites are guarded by `hasSeen` on the line before.

## Not measured

The iOS UAT gate run with the flag (a Hermes/Appium run on melehost's device).

FOREIGN: not run.
