<!--
INDEX.md — architect-owned glanceable state table for the audit handshake (CR005).
Regenerable from the lane files via `sh audit/handshake/watcher.sh state`; kept here so the
queue is visible without deriving from N files. May lag the auditor's verdicts on a bounce
(expected — detect a returned verdict by the auditor lane's VERDICT keyword, never by this
table).
-->

# Audit handshake lane index

| Item | State | Depends on | Submitted | Verdict |
|---|---|---|---|---|
| CR004 | AWAITING_AUDIT | none | R53 · round 2 | AWAITING_FIXES (r1: 1 MAJOR fixed) |

_Lane scope for CR004 is the R52-delivered Engagement chunks (D0/E1/B1) only — see `CR004.architect.md`. Remaining CR004 chunks submit as their own future lanes._
