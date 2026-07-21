<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# noncoder.errors

```
role: noncoder
sub_kind: requester
spec: user-reported error / bug intake + diagnosis
kind: requester (DEF)
owns: orchestration/intake/errors-*.md  (drafts only — never source, never a lane)
source: melehost bug_reports table (status open/in_progress/pending_review)
wip_cap: n/a
auditor: n/a
live_handle:
commit_tag: AT:noncoder.errors
active_lanes: []
```

**Feeds DEFs in; never builds, never auto-fixes** (per `memory/feedback_track_r_bug_monitor.md`).
Poll `bug_reports` (exclude the CR035 room-benchmark synthetics + the seed rows per
`memory/feedback_user_report_exclusions.md`), diagnose, and draft `intake/errors-NNN.md` with the
`bug:<id>`, category, evidence (file:line, logs, repro), and proposed severity. The Architect
triages → mints the DEF → dispatches to a coder. Answer `TRIAGE: NEEDS-INFO` `Q:` blocks promptly
(this is Saiful's example: the Architect can query you back for repro detail before minting).
