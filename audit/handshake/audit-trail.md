<!--
audit-trail.md — the ONE chronological ledger across all audit-handshake lanes
(PROTOCOL.md guardrail 5). Auditor (track U) appends one row per verdict. Newest
at the bottom. Owner: AMI Trade AUDITOR.
-->

# Audit handshake — verdict ledger

| When (KL) | Item | Round | SHA | Verdict | Headline |
|---|---|---|---|---|---|
| 2026-07-09 | CR004 | 1 | `caa014c` | AWAITING_FIXES | F1 MAJOR (reproduced): streak-milestone credits re-granted under the 25/day reputation cap — zero-write clip defeats the idempotency guard; +100 credits per league-screen refresh. Plus F2–F4 MINOR, F5/F6 observations. Backend 578 tests + flutter analyze reproduced; melehost DB state gated by auto-mode. |
| 2026-07-09 | CR004 | 2 | `dca45a9` | COMPLETE | F1 FIXED `6286937` (`always_record` persists the 0-point guard row under cap) — auditor pin now PASSES; F4 FIXED `dca45a9`; F3 doc-fixed; F2/F5 deferred to DEF039/DEF040 (filed, open); F6 accepted-risk. 578 passed (no regression); melehost migration `c3d4e5f60014` + 4 tables REPRODUCED. Observation: F1 fix lacks an in-suite test (covered by the auditor pin). |
| 2026-07-09 | CR009 | 1 | `7a8aaf7` | COMPLETE | Mobile B3/B4/B6 bundle (Room roster, dead-end removal + DEF041 Brief refine + D-062 dark pin, empty states). Reproduced: flutter analyze 4 pre-existing infos / 0 new, flutter test 1 passed; clean l10n purge (0 dangling refs); kAllAgents sublist(0,12)/.last safe; D-062 pin + DEF041 refine + B3 roster + B6 widget all confirmed by source read. Registers OK; DEF041 isolated. One MINOR: theme_provider.dart orphaned by D-062 (O1). Runtime visuals NEEDS-DEVICE-CHECK. |
