# CR263 — Whole-app UAT script, executed against the mobile app and the live backend

**Status:** in-progress · **Filed:** 2026-10-19 · **Track:** Q (UAT)

## What
1. One UAT script for the whole app. Source of truth is `qa/uat/cases/<area>.yaml`. `qa/uat/render.py` generates `qa/uat/UAT_SCRIPT.md` from it; never edit that file by hand.
2. The script is executed by three runners:
   1. **API layer:** `qa/uat/api/`, pytest against live Alpha. It uses tagged `uat` users.
   2. **Device layer:** `qa/appium/tests/`, the existing CR080/CR162 harness. Android runs on the A17 on the melehost rig; iOS runs on the Simulator.
   3. **Manual layer:** the iPhone checklist section of `UAT_SCRIPT.md`, for real purchases, push, Apple/Google sign-in and TestFlight. This replaces the CR004 §A2 checklist.
3. `scripts/uat/run_uat.sh` runs the layers and writes one report per UAT ID to `qa/uat/_runs/<ts>/`.

## Why
Saiful asked on 2026-10-19 for "the UAT test script for the whole application… used to run and test the mobile app, and the back end". Before this CR:
1. Every real journey in the device harness was `@skip` (onboarding, the Room, 1-on-1, Brief, sign-in, Alpaca).
2. The live backend was covered by only three smoke curls plus `postflight.py`.
3. The 17-item CR004 manual checklist had no automated equivalent.

## Decisions (Saiful, 2026-10-19)
1. Device testing is automated on the rig and the iOS Simulator. A short manual checklist covers what can only be done on an iPhone.
2. The API suite may create users on Alpha and spend real LLM calls. Each user is tagged `last_app_version='uat'` and `device_model='ami-uat'`, and suspended at teardown. These users are excluded from real-user counts in the same way as CR035's `room-benchmark` rows.
3. Credentials are supplied. The Alpaca paper key is stored in the git-ignored `qa/uat/.uat.env` (the repo is public) and in the rig's `qa/appium/test_data/.env`. The test inbox is still to come.

## Guards
`qa/uat/tests_offline/test_catalogue.py` checks four things:
1. The schema is valid and IDs are unique.
2. `UAT_SCRIPT.md` is freshly rendered from the YAML.
3. Every `active` api or device case is cited by a test in the matching runner, using `@pytest.mark.uat("<id>")`.
4. No test cites an unknown case or a case from the wrong layer.

A case with no test behind it is a script line nobody runs, which is the gap this CR closes.

## Rules for case authors
1. Test the goal the case is meant to guarantee, not just the HTTP status. For example: an out-of-credits Room run must return 402 and must not produce a fake verdict (the DEF059 class). Brief must not be able to weaken the mandate floor.
2. A real failure gets filed as a DEF. Do not patch app code inside this CR, and do not weaken a test to make it pass.
3. Mark a case `status: blocked` with `blocked_on:` only when an external input is missing. Never use it to hide a failure.

## Acceptance
1. `pytest qa/uat/tests_offline` passes.
2. `run_uat.sh --api` runs every active API case against Alpha, and teardown leaves no unsuspended `uat` users.
3. `run_uat.sh --device android` and `--device ios` run every active device case and capture screenshots.
4. Saiful runs the manual checklist once.

## Findings log
1. 2026-10-19: `IOS_TESTFLIGHT_JOIN_URL` is unset on Alpha. The iOS forced-update button falls back to the generic TestFlight page; this is CR121's deliberate, logged fallback. Saiful needs to set the public TestFlight join link.

## Release gate + nightly (Saiful, 2026-10-19: "before sending the app to testflight, play store and promote-to-alpha, the test scripts must be updated. the added/updated tests must have been run … and a full test run using the simulator daily, say at 3am")
1. `scripts/uat/uat_gate.py --for alpha|testflight|playstore|alpha-post` runs three checks, in order:
   1. Catalogue guards, including "every screen/router belongs to an area".
   2. Script updated: every changed source file's area must have changed its cases/tests, or the commit carries a `UAT-Impact: none (<reason>)` trailer.
   3. Tests run: every active case for the activity has a passing ledger entry at its current fingerprint. The fingerprint covers the case, its own test functions plus their file's shared code, and the area's covered sources.
2. Where it is wired:
   1. `build_testflight.sh` requires api + iOS (Android stands in while the iOS Simulator is paused, Saiful 2026-10-20).
   2. `publish_playstore.sh` requires api + Android.
   3. `/promote-to-alpha` step 1 runs `alpha` (device evidence before the deploy). Step 7d runs `alpha-post`: changed API cases against the deployed code.
3. Escape hatch: `UAT_GATE_OVERRIDE="<reason>"`, logged to `.deliveryos/uat_overrides.log`.
4. Ledger: git-ignored `.deliveryos/uat_ledger.json`. Only `ledger.py record` writes to it. The results plugin writes after every test, so a killed run keeps the evidence it has gathered.
5. Nightly: LaunchAgent `ai.agenticmarketintel.uat-nightly` runs at 03:00 and calls `scripts/uat/nightly.sh` → `run_uat.sh --all` (API + iOS Simulator). macOS privacy controls block a launchd-started bash from reading the external volume, so the job goes through Terminal. It posts a macOS notification and prunes runs older than 14 days. The Mac wake needs `sudo pmset repeat wakeorpoweron MTWRFSU 02:55:00`.

## Findings log (cont.)
2. 2026-10-19 full API run: 168 passed, 9 known xfails (each with a DEF). Filed DEF458–464, DEF466 (iOS accessibility tree goes dark at Settings > PROFILE) and DEF467 (1-on-1/Brief streams stall with no keepalive). DEF465 was the toolchain failure (Xcode 27 lipo); fixed.
3. Open decisions for Saiful:
   1. Streak has no HTTP surface (DAILY-005 blocked).
   2. UAT-only seeding of inbox/notification rows (INBOX-004/005 blocked).
   3. Health 402/daily-cap needs plan gate mode (HLTH-010 blocked).
   4. A `mock_walk` quote for unknown tickers vs a 404.
4. Next: device-layer UAT cases (Appium journeys cited by UAT ids), the Android rig wired into `run_uat.sh`, and the test inbox for AUTH-020–022 / ONB-030 / ALPACA-003.
