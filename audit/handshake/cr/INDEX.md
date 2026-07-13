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
| DEF042 | COMPLETE | none | R54 · round 1 | COMPLETE (r1) — challenge answer+explanation leak closed (all 4 routes); M1 test gap addressed (`58bf138`) |
| DEF039 | COMPLETE | none | R54 · round 1 | COMPLETE (r1) — reputation dedup partial index; O1 → minted DEF049 |
| DEF040 | COMPLETE | DEF039 | R54 · round 1 | COMPLETE (r1) — merge current-week league recompute; M1 (past-week) noted, not minted |
| DEF047 | COMPLETE | none | R54 · round 1 | COMPLETE (r1) — onboarding locale hint; O1 → minted DEF050 |
| DEF048 | COMPLETE | none | R54 · round 1 | COMPLETE (r1) — readback-edit 501 atomicity |
| DEF045 | COMPLETE | none | R54 · round 1 | COMPLETE (r1, pending-merge) — **merged to main `bd851b3` unchanged; verdict now unconditional** |
| DEF046 | COMPLETE | none | R54 · round 1 | COMPLETE (r1, pending-merge) — **merged to main `bd851b3` unchanged; verdict now unconditional** |
| DEF049 | COMPLETE | DEF039 | R54 · round 1 | COMPLETE (r1) — milestone credit double-grant under concurrency (from DEF039 O1); on main `58bf138`, **not yet promoted**. **Index was stale here — audited COMPLETE 2026-07-11, never reflected until R58's reconciliation pass.** |
| DEF050 | COMPLETE | none | R54 · round 1 | COMPLETE (r1) — unused `assets/icons/` pubspec line (from shared O1), verified from a fresh worktree; on main `58bf138`. **Index was stale here too — same R58 reconciliation.** |
| CR023 | COMPLETE | none | R58 · round 1 | COMPLETE (r1) — News Analyst real feed (Yahoo + Alpha Vantage), submitted late — shipped R57, opened + audited R58; on main `4b153a2`, **not yet promoted** |
| CR024 | COMPLETE | none | R58 · round 1 | COMPLETE (r1) — Social Media Analyst real feed (Adanos Reddit sentiment) + scripted-fallback platform-naming fix, submitted late — shipped R57, opened + audited R58; on main `c942120`, **not yet promoted**. Auditor's non-blocking observation: snippet-safety invariant is correct by construction but not pinned by a dedicated test — recommended, not required. |
| DEF051 | COMPLETE | none | R58 · round 1 | COMPLETE (r1) — Room's fake $100k/0%-drawdown compliance-check input, resolved server-side via SimEngine; on main `22c84c6`, **not yet promoted, safety-floor-relevant** |
| DEF052 | AWAITING-AUDIT | none | R58 · round 1 | — · Market Analyst real technicals (RSI/trend/volume/support-breakout from yfinance OHLCV), MACD/Bollinger Bands dropped from prompt; on main `f367e26`, **not yet promoted** |

_Lane scope for CR004 is the R52-delivered Engagement chunks (D0/E1/B1) only — see `CR004.architect.md`. Remaining CR004 chunks submit as their own future lanes._

_R54 batch: DEF039/040/042/047/048 audited COMPLETE round 1. DEF045/046 audited COMPLETE (pending-merge) and are now **merged to main `bd851b3`** via clean `--no-ff` (diffs unchanged → verdicts stand). Two follow-up lanes minted from the auditor's OUT-OF-SCOPE findings: **DEF049** (DEF039 O1 — monetized credit double-grant, fixed) + **DEF050** (shared O1 — pubspec asset dir). DEF049 is on main but **awaits `/promote-to-alpha`** to reach the live server._

_R58 batch: CR023/CR024/DEF051 all shipped R57 but were never opened as lanes before that session wrapped — opened now, R58, once Saiful flagged the gap. All three touch the same risk category (12-agent data truthfulness / safety-floor input) that motivated this handshake in the first place, so this batch skipped no fewer checks than usual — it just ran the self-check + submission one session late. Track U audited all three COMPLETE round 1 the same day (2026-07-13), independently reproducing test counts in isolated worktrees, re-verifying real API response shapes, and confirming the DEF051 regression tests fail against a reverted fix. All three on main, all three **not yet promoted to Alpha**; DEF051 is the highest-priority of the three (safety-floor compliance-check input, not a narrative honesty gap)._

_R58 reconciliation: this same pass discovered DEF049/DEF050 had been sitting COMPLETE in their own lane files since 2026-07-11 (R54) without this table ever being updated to match — a stale-INDEX gap, not a stale-audit gap (the verdicts themselves were always current; only this glanceable table lagged). Fixed here. Worth remembering: this table is regenerable via `sh audit/handshake/watcher.sh state` and should be spot-checked against that output at the top of any session that touches the handshake, not assumed current._
