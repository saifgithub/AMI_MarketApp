# E5 — device-matrix runbook (cable install)

Part of [CR004](CR004_release_readiness.md). E5 is the **only** open item on the Engagement
close-out gate, and that gate is what holds Stealth Alpha recruitment at 10–20 personal invites
([CR036 §2](../CR036_go_to_market_plan/CR036_go_to_market_plan.md)). It has been open since
2026-07-25 for want of device time, not for want of a plan.

Saiful, 2026-08-21 daily check-in: **"I can connect the phones to the Mac."** So this runbook is
written for cable install off the Mac, not TestFlight round-trips. It exists so the pass is a
mechanical hour: install, walk the list, mark ✅/❌, done.

The pass checklist itself stays where it already lives —
[`build_verification_execution.md`](build_verification_execution.md) §A2 — plus the **delta list**
below, which covers what shipped after that checklist was written (2026-07-25). Drills are §A3 of
the same file.

---

## 0. Before you plug anything in

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
curl -s https://api-alpha.agenticmarketintel.ai/v1/health          # backend up
curl -s https://api-alpha.agenticmarketintel.ai/v1/llm/status      # vllm, not mock
git log --oneline -1                                                # note the sha in the log below
grep '^version:' mobile/pubspec.yaml                                # note the build number
```

If health or llm/status is wrong, stop and fix that first — a device pass against a degraded
backend measures nothing.

## 1. Install (release builds only — never debug on a real device)

| Device | Command |
|---|---|
| iPhone 13 (`TESTING IPHONE 13`) | `scripts/install_iphone.sh` |
| iPhone 17 | `scripts/install_iphone.sh <device-id>` (`flutter devices` for the id) |
| Galaxy Note FE — Android 9 floor | `scripts/install_android.sh ce10171a8017590d01` |
| Galaxy A17 | `scripts/install_android.sh R5CY91AY99Y` |

`scripts/install_android.sh --list` finds the serial of anything not in that table.

**Go off-LAN for the pass** — cellular or a non-home Wi-Fi. On the LAN the app can reach melehost
directly and you will not exercise the Cloudflare Tunnel path testers actually use.

## 2. Walk the list

Per device: §A2 in [`build_verification_execution.md`](build_verification_execution.md), then the
delta below. Mark ✅/❌. **File every ❌ from the device** (long-press the app-version chip) so it
lands in `bug_reports` with the build, platform and screenshot attached — that is the same pipe
`/bug-monitor` and `/fix-bugs` read.

### Delta since the §A2 checklist was written (2026-07-25)

```
[ ] Floor v0.2: the answer carousel — SIM PORTFOLIO, YOUR TEAM'S CALLS, SECTOR WATCH, and the
    unactioned-convene scorecard each render with real numbers, not placeholders
[ ] Tester inbox (CR102): bell shows unread count; open a message; reply; a high-priority
    message raises the toast. Send yourself one with `scripts/messages.sh`
[ ] Portfolio Health (CR136): findings render; the methodology disclosure card is READABLE
    (see known-open DEF340 below before filing)
[ ] Mandate screen (CR129): the 7 resolved limits render, server-sourced
[ ] Resting orders (CR187): place a limit that will not fill → the book states what happened
[ ] Trades list (CR120): SHOW ALL on a long history does not hang or truncate silently
[ ] Credits exhausted → the winzip 402 card: amber countdown, lessons CTA, AMI speaks at 0
[ ] Push: a real notification arrives and deep-links (Android channel was DEF333 — verify)
[ ] Games standings, if the dark-launch build exposes them (see DEF343 below)
```

**Out of scope for this pass — flagged off in Alpha:** the structured Risk Officer
(`ROOM_RISK_OFFICER_ENABLED`), AdMob (`ADMOB_MODE` empty), and CR172 options beyond what slice 1–2
exposes. Do not chase them; if one is visible on device, that is itself the defect.

### Known-open — do NOT re-file these

| ID | What you will see |
|---|---|
| DEF340 | Portfolio Health methodology card: light-gray text on light-blue, unreadable |
| DEF341 | Watchlist: `GOOGL` wraps mid-symbol onto two lines |
| DEF342 | Brief Your Agent proposal: accept/reject row hidden behind Android system nav |
| DEF343 | Games standings: a tie reads as "I'm last" — no tie marker |
| DEF344 | Upgrade tap crashes when RevenueCat is unconfigured (payments track is parked) |

Anything else is new — file it.

## 3. Drills (once, from the Mac — not per device)

§A3 of [`build_verification_execution.md`](build_verification_execution.md): LLM down, market data
down, backend restart mid-Room, tunnel down, bad bearer. Record each result inline in that file.

## 4. Close the gate

E5 closes when **every device in the matrix has a recorded pass** and every ❌ carries a
`bug:<short-id>`. Then, per [CR036 §2](../CR036_go_to_market_plan/CR036_go_to_market_plan.md), the
remaining two graduation conditions are: zero open bugs sustained through the invite window, and a
meaningful slice of the cohort hitting ≥1 Convene the Room per week. Only then does recruitment
widen past personal invites.

## Log

| Date | Device | Build | Result | Notes |
|---|---|---|---|---|
| 2026-09-25 | n/a — automated, public API client only (no device) | `alpha-2026-09-25-4` / `685dbdd0` | §3 drills: 3 PASS / 2 FAIL | Saiful go, "Now, late night" (2026-09-25). Full run in [`build_verification_execution.md`](build_verification_execution.md) §A3. Drill 1 (LLM down) PARTIAL FAIL — Concierge 1-on-1 got branded AMI fallback, Brief got a raw `All connection attempts failed` string; credits refunded correctly on both → **DEF424**. Drill 2 (market data down) PASS — `mock_walk` source, quotes kept flowing. Drill 3 (restart mid-Room) FAIL — run cancelled with no verdict, 12 credits charged, **no refund**, startup-sweep auto-retry never engaged (the app's own SIGTERM-triggered cancel writes the row to `CANCELLED` before the sweep can see it as stuck-`RUNNING`) → **DEF425**. Drill 4 (tunnel down) PASS — CF 530 in ~0.3s, recovered on first poll after restart. Drill 5 (bad bearer) PASS — clean 401 JSON on 3 malformed-token variants, anon re-bootstrap worked immediately after. Alpha left healthy on `alpha-2026-09-25-4`, canonical env, postflight's 6 non-`tree` checks green throughout (the `tree` check's residual FAIL is pre-existing drift from 3 already-committed main commits not yet promoted, unrelated to these drills). Device-side notes for Saiful's own device walk (airplane-mode readable-offline-state, crash-loop behaviour on corrupt token) are out of scope for this automated pass per the original §A3 spec. |
| 2026-09-25 | iOS Simulator (iPhone 17, XCUITest, CR080/CR162 automated gate) | 0.1.0+111 (`6fa2dd0a`), Alpha `alpha-2026-09-25-4` | smoke: 6/6 passed. phase1 run 1: 8 passed / 4 skipped / 11 errors (2653s). phase1 run 2 (flake re-check, fresh app launch): 13 passed / 4 skipped / 2 failed / 4 errors (1181s). DEF375 baseline was 12 passed / 7 failed / 4 skipped (19 tests, 4m20s); this session's 23-test collection is larger (CR209/later additions), so raw counts aren't 1:1 comparable, but pass rate is markedly worse and both runs took 10-20x longer than baseline. | See E5-U1/E5-U2 below. Android leg blocked — see note. |

**E5-U1 — iOS system notification-permission dialog blocks the harness mid-session (both phase1 runs).** A native `UIAlertController` ("Notifications — AMI can notify you the moment a price alert fires or a Room verdict is ready. Turn on notifications?" / Not now / Turn on) appears at some point after the first 1-2 test modules run, confirmed in run 2's failure capture (`page_source/FAILURE_tests_test_00_smoke_hierarchy.py__test_floor_tab_is_default_landing.xml` — `label="Notifications"`, `label="Turn on notifications?"`, `label="Not now"`, `label="Turn on"`; screenshot at the matching `screenshots/FAILURE_..._state.png` shows it fully covering the Floor screen, bottom nav still visible underneath). It is a native OS dialog, not part of the Flutter accessibility tree the harness's `by_text`/`by_id` locators read, so once it appears every subsequent `wait_visible_text(driver, "FLOOR", ...)` call and every `ensure_onboarded`/`shell_is_up` check correctly finds nothing — not because the app broke, but because the app genuinely is covered. This cascades: each later test module's `driver` fixture calls `ensure_onboarded`, burns the full 480s budget, and errors. **Classification: harness gap, not a product bug.** The harness has no step that watches for or dismisses a native permission dialog (`base_page.py`'s `dismiss_tour_if_present` only handles in-app Flutter tour overlays). Re-run once to check flake (see run 2 above): reproduced in a different but related shape (this time causing a `FAILED` on `test_floor_tab_is_default_landing` directly plus the same error cascade on later modules) — so it is not a one-off, it recurs across fresh app launches with `noReset=True` retained app state. Evidence: `qa/appium/_runs/2026-09-25T012649Z-ios-rerun/page_source/FAILURE_tests_test_00_smoke_hierarchy.py__test_floor_tab_is_default_landing.xml`, `qa/appium/_runs/2026-09-25T012649Z-ios-rerun/screenshots/FAILURE_tests_test_00_smoke_hierarchy.py__test_floor_tab_is_default_landing__state.png`. Needs a DEF (harness fix: detect + dismiss the native notification-permission alert, similar in spirit to `dismiss_tour_if_present` but for a native alert rather than a Flutter overlay).

**E5-U2 — Journal (YOU segment) empty state overflows by 29px on iPhone 17 Simulator, debug build.** `screenshots/journal__default.png` from run 1 shows Flutter's own debug-mode render-overflow banner ("BOTTOM OVERFLOWED BY 29 PIXELS", black/yellow hazard stripe) across the Journal empty-state illustration/copy area (below "No entries yet."). This is exactly the non-scrolling-overflow class this harness (CR080) was built to catch. Caveat: the QA harness builds `--debug` (`scripts/build_qa_ios_sim.sh`, by design — see that script's own comment on why release-signing doesn't apply to a Simulator build), and Flutter's overflow banner is a debug-only rendering artifact — a release build would not show the yellow/black stripe, though the underlying layout overflow (if real) would still be there, just invisible. `test_scroll_overflow.py`'s own mechanical check for this never ran to completion against this exact spot due to E5-U1's cascade, so this is an incidental visual observation from a passing test's screenshot (`test_journal_renders_heading` passed), not a confirmed-by-assertion finding. Needs a human/Claude look at `journal_screen.dart`'s embedded empty-state layout before filing as a DEF — recorded here per the harness's own convention (findings are reviewed and promoted, not self-filed) rather than filed directly.

**Android leg — blocked, not run.** melehost's Galaxy A17 (`R5CY91AY99Y`) was not visible in `lsusb` or `adb devices -l` at any point this session (checked repeatedly across ~90 minutes; melehost uptime 7 days, so not a post-reboot enumeration gap) — physically disconnected. Also found and fixed in passing: `qa/appium/MANIFEST.sha256` was stale in git (pre-DEF382 hashes for `config/semantics_ids.py`/`pages/base_page.py`), which would have made a correct melehost delivery read as "edited in place"; fixed in `6fa2dd0a` and melehost's harness copy re-synced (was 3 weeks stale) and re-verified clean. No QA APK was built for Android this session (no device to install it on) — note for whoever picks this up: `scripts/share_apk_to_tester.sh` does not forward `AMI_QA_SEMANTICS`/`AMI_QA_SKIP_TOURS`, so a QA-flagged APK will need a one-off build the same way `build_qa_ios_sim.sh` does for iOS before the Android gate can run at all.
