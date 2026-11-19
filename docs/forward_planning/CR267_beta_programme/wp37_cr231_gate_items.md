# WP-37 — CR231 gate items: CR221, CR222, CR228 closure and the E5 device matrix

Record for CR267 WP-37, 2026-11-19 (AT:B1 CR267). Closure criteria are CR245 §12 (check-in of 2026-09-30). Nothing here re-measured a model run; the one new computation is the CR228 scorer on committed data.

## 1. Decisions

| CR | Decision | Row |
|---|---|---|
| CR228 | **done** | flipped |
| CR221 | **done** | flipped |
| CR222 | **not done** | stays `in_progress`, remainder written into the row |

### CR228 — done

1. CR245 §12 asked for one thing: run `score_dial.py` on the 5-arm data and record PASS or FAIL by its letter.
2. Run on melehost's production pilot (`results/melehost_pilot_20260926/`, commit `4257d855`; criterion committed in `556d0292` before the run). Output saved as `docs/forward_planning/CR228_risk_appetite_differentiation/results/pilot_dial_scored_2026-11-19.txt`.
3. n=27 paired tickers. Mean `approve_votes` R1 to R5: 0.19, 0.41, 0.56, 1.52, 1.78. Approve rate 0%, 0%, 11%, 33%, 48%. Page's L=1322.0, one-sided p<0.0001; means non-decreasing. **VERDICT: PASS.**
4. Audit: CR228 COMPLETE round 6 (`de1b8467`). README status line and a Closure section updated.
5. Caveat kept in the README: Steps 2-4 ran combined, so the pilot does not separate the prompt branch from the structural vote threshold. Not a closure condition.

### CR221 — done

1. CR245 §12: "flip the row and fix that text". Done: header now carries a closure record, and the stale "All three flags remain OFF" line is marked superseded.
2. Evidence: slots 1-5 built; audits COMPLETE for SLOT4 (`1a3b6a6a`), SLOT2 (`19dd1784`), SLOT5 (`8caa0334`) and RETRO-CR221-S13 covering slots 1/3 (`92a7c6c0`); §7 measured through round 5 (`0e626aeb`); Saiful's decision to flip five flags (`177cc0c2`); the flip recorded on Alpha with ingest tallies (`075a0901`); slots 6-9 split to CR238 (`0a02d8f4`, proposed).
3. Residuals, none a closure condition: H2 (Fed path) is the one item with no free source and stays a declared absence; the 8-K re-scan cron is due before about 2027-03-24 and needs Saiful's go for a melehost cron; H1/H3 ride FRED per the 2026-09-23 ruling, CR229 probes alternatives.
4. Not re-verified here: that the five flags are still on in Alpha's live env (no ssh in this lane). The record is the 2026-09-25 flip.

### CR222 — not done; what remains

Slices B, C and D are built and audited COMPLETE (C `e05a5b79`, D `7d2b8852`, B `2f9afda3`). CR245 §12 left "closed" for Saiful to define. Against either reading:

1. **Saiful decides** whether closed means built-and-audited or flags on. This is his call (the toll is a money path; the Day Trader exemption is his ruling).
2. **Built-and-audited reading:** still not met, because slice A (pre-registration) has no audit lane and its mobile ticket fields are not built (the CR222-B lane header says so).
3. **Flags-on reading:** the 2026-09-25 memo planned to flip `PORTFOLIO_PASSIVE_TWIN_ENABLED` and `PORTFOLIO_BEHAVIOUR_DIAGNOSTICS_ENABLED` after the B/D audits; both are COMPLETE and no flip is recorded. The toll and pre-registration stay off by plan.
4. **Before the toll is ever flipped:** CR222-C MINOR-1 (the safety net for shorts and options) and MINOR-2 (the two lanes disagree about round-trip cost) must be fixed; the auditor said so in the verdict.
5. The acceptance line "live check on Alpha that each flag is off after promotion" has no record.

Cheapest path to done: Saiful picks the reading; if built-and-audited, add a slice A audit lane (and decide whether the mobile fields are in or out of scope, since the Day Trader exemption and Beta may make slice A a follow-on CR); if flags-on, flip B and D with a recorded container-env check.

## 2. E5 device matrix

The melehost Android rig is disconnected, so device runs go through the AMI AI Suite phones under `device_lab_protocol.md`. The runbook's list was cut into two tester packets, written to the session scratchpad (operational, not in the repo):

1. `AMI-DL-3_android_e5_packet.md` — Android, run id `AMI-DL-3`.
2. `AMI-DL-4_ios_e5_packet.md` — iPhone, run id `AMI-DL-4`.

Same style as AMI-DL-1/2. Expected build 0.1.0 (117), as in `mobile/pubspec.yaml` on the branch; the booking message names the final one. Booking per protocol 1: one `PHONE BOOKING REQUEST` per phone, after AMI-DL-1/2 have proven the Alpha DNS path. Length is an estimate (about 2 hours plus the 15-minute hand-back), not measured.

### What the testers can run (Part A, 15 cases, both platforms)

Gateway lessons unlocking an agent; 1-ON-1; Brief diff, accept and rollback; a full Room with a mid-run close and reconnect; verdict to trade ticket; Portfolio and LIVE pill; ticker detail charts; watchlist persistence; daily challenge; Journal filters, undo and trash; mandate edit persistence; Floor carousel; Portfolio Health and its methodology card; the seven resolved limits; a resting limit order.

### What they cannot (Part B, blocked up front: 14 Android, 15 iPhone)

1. Fresh-state onboarding and tour (needs reinstall or cleared data).
2. Sign-in claim, merge sheet, sign-out (needs an account).
3. Alpaca paper link (needs keys).
4. Bug report with a photo (operators file nothing; photo needs gallery access).
5. Airplane-mode offline pass (OS network setting).
6. Fullscreen chart rotation.
7. News row opens the browser (leaves the app).
8. Tester inbox CR102 (needs an admin send to the device's user).
9. Trades list SHOW ALL on a long history (needs a history; seeding is a shortcut).
10. Credits-exhausted 402 card (needs a spent account).
11. Push arrival and tap (OS permission dialog and a server trigger; DND is on).
12. Games standings (compile flag not in a store build).
13. Off-LAN cellular pass (phones stay on the Suite LAN).
14. Matrix devices the lab phones are not (iPhone 13/17, Galaxy Note FE Android 9 floor, A17).
15. iPhone only: the Language switch, blocked by DEF466 (open).

### For Saiful by hand

All of Part B, on his own phones. Smallest useful set, in order of what it protects: 1 (onboarding on a fresh install), 2, 11 and 13 (account, push, and one cellular pass: the paths testers will actually hit), then 8, 9, 10, 12 and 14 as the matrix needs. Two decisions: whether the Beta matrix is redefined to the lab phones plus Saiful's own, and whether to ask the Suite's stakeholder for a news-link grant (item 7). The Mac-side drills (runbook §3) ran 2026-09-25 with two FAILs, DEF424 and DEF425, both now `fixed`; a re-run of drills 1 and 3 is not recorded.

### Known-open changes since the runbook

DEF340, DEF341, DEF342 and DEF343 are now `fixed` (the runbook lists them as known-open); DEF344 is still open (payments parked); DEF466 (iOS accessibility tree) is open and shapes the iPhone packet.

## 3. Acceptance, WP-37

1. "Rows closed": two of three. CR222 needs Saiful's definition of closed first.
2. "Matrix results recorded": not yet. Packets are ready; no lab run has happened, and no result is claimed.

## Rulings, 2026-11-19 (Saiful)

1. CR222: "audited is enough". Closed on slices B, C, D; slice A and the toll prerequisites moved to CR280.
2. E5 matrix for Beta: the lab phones (AMI-DL-3 Android, AMI-DL-4 iPhone, 15 cases each) plus four items Saiful does by hand: fresh-install onboarding, sign-in claim, push arrival and tap, one off-LAN cellular pass.
