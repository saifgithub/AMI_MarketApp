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
| CR004 | COMPLETE | none | R53 · round 2 | COMPLETE (r2) — delivered subset D0/E1/B1 |
| CR009 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — B3/B4/B6 mobile; O1 addressed |
| CR010 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — B2/B5; M1 fixed, DEF042 filed |
| CR011 | COMPLETE | CR010 | R53 · round 1 | COMPLETE (r1) — C3 league surface; M2 addressed |
| CR012 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — C4 share cards; O1 (RTL) addressed |
| CR013 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — E3/D1 15 lesson animations; replay-tooltip i18n addressed |
| CR014 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — E3/D2+D3 motion identity; no findings |
| CR015 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — E4/D7 HexToast/toggle/logo; C1+bulk deferred; no findings |
| CR016 | COMPLETE | none | R53 · round 1 | COMPLETE (r1) — E4/D8 HexBottomNav; M1 (tap-height) addressed |
| DEF042 | AWAITING-AUDIT | none | R54 · round 1 | — · security; challenge answer+explanation leak (reopened CR010-O1); on main `85ec04e`, live `alpha-2026-07-11-2` |
| DEF039 | AWAITING-AUDIT | none | R54 · round 1 | — · reputation dedup partial index (reopened CR004-F2); on main `2208f99` + migration 0015 live |
| DEF040 | AWAITING-AUDIT | DEF039 | R54 · round 1 | — · merge current-week league recompute (reopened CR004-F5); on main `7ebc123` |
| DEF047 | AWAITING-AUDIT | none | R54 · round 1 | — · onboarding locale hint (CR004 Plan-A #2); on main `fd0ab6f` |
| DEF048 | AWAITING-AUDIT | none | R54 · round 1 | — · readback-edit 501 atomicity (CR004 Plan-A #6); on main `fd0ab6f` |
| DEF045 | AWAITING-AUDIT | none | R54 · round 1 | — · watchlist cold-start load; ⚠️ on BRANCH `claude/bug-fix-20260711-115553` `9712006`, not main |
| DEF046 | AWAITING-AUDIT | none | R54 · round 1 | — · watchlist swipe-delete; ⚠️ on BRANCH `claude/bug-fix-20260711-115553` `e2a3c1f`, not main |

_Lane scope for CR004 is the R52-delivered Engagement chunks (D0/E1/B1) only — see `CR004.architect.md`. Remaining CR004 chunks submit as their own future lanes._

_R54 batch (7 lanes): DEF039/040/042 are reopened prior audit findings (F2/F5/O1) on monetized currency/security — the priority set. DEF047/048 are onboarding (lower risk). DEF045/046 are user-reported mobile fixes still on the `/fix-bugs` branch — **their lanes point at branch SHAs; the auditor must check out the branch, or hold until Saiful merges to main.**_
