<!-- intake draft TEMPLATE — the format noncoder.errors uses per real bug_report. Not a live item. CR052. -->
# errors-NNN — proposed DEF: <one-line symptom>   [TEMPLATE — copy per real bug]

PROPOSED-KIND: DEF
SOURCE: noncoder.errors
BUG-REF: bug:<8-char-uuid>        # the bug_reports row id (melehost); omit for prompt-spotted
TRIAGE: OPEN

**Symptom (user words):** <verbatim from the report>
**Category:** <ui_glitch|security|room|mandate|onboarding|infra|content|l10n|ux|data|other>
**Repro:** <steps that reproduce, or "not yet reproduced">
**Evidence:** <file:line suspicion, log excerpt, screenshot ref, http_audit count, affected build>
**Blast radius / severity (proposed):** <who is affected, how badly>
**Suspected owner:** <coder.api | coder.room | coder.mobile | coder.web | coder.store>

---
*Rules: surface + enrich only — never auto-fix (memory/feedback_track_r_bug_monitor.md), never mint
the DEF id (Architect does). Exclude CR035 room-benchmark synthetics + the 2026-05-24 seed rows
(memory/feedback_user_report_exclusions.md). Answer the Architect's `TRIAGE: NEEDS-INFO` `Q:` blocks
with repro detail before the DEF is minted.*
