# CR080 — Appium UAT/usability harness + standing QA track

**Filed:** 2026-07-23 · **Track:** `AT:Q` (new) · **Status:** in_progress · **Depends on:** CR079

## Why

Saiful asked for a "UAT UI/UX Manager" capability: test scripts that exercise the app purely
from a user's point of view, hunting usability defects — his example, "screens that do not
scroll when they need to." No such role or tooling exists today. Manual device testing has
always been Saiful's alone (`docs/initial_specs/10_delivery/you_do_i_do.md`); Claude has only
ever written automated *unit*/widget tests, never driven the app as a user would.

Static review of `mobile/lib/screens/**` already turned up concrete candidates before a single
test ran: `screens/auth/merge_sheet.dart` and `screens/room/convene_sheet.dart` are modal sheets
with no scroll wrapper around variable-length content; `screens/agent/agent_unlocked_screen.dart`
is a fixed `Column`+`Spacer` layout with no scroll fallback. There's already a precedent bug of
exactly this shape — **DEF075** (a modal-sheet button rendered under the Android system nav bar,
unclickable) — fixed and guarded by one widget test (`sheet_insets_test.dart`), but that test
only proves the layout math against a synthetic `MediaQuery`, not the rendered result on a real
device.

CR079 (same day) built the delivery half of this: every build path now scps a fresh release APK
to `saiful@192.168.20.59:/home/saiful/hermes_folder/project/AMI_MarketApps/apk/`, explicitly
because — Saiful's words — "that is our automated tester." CR080 builds the tester itself: the
Appium scripts that actually drive that APK on the Galaxy A17 already sitting there on USB, plus
the standing track (`Q`) to run it recurringly pre-release.

## What

- **New track `Q`** ("QA/UAT") in `.claude/session-config.yml` — `HANDOVER_Q.md`,
  `history_dir: history/`, `project_plan_path` pointing back at this doc as the living
  screen/flow coverage backlog.
- **`qa/appium/`** — a Python + pytest + Appium-Python-Client harness, source-of-truth in git,
  shipped to melehost's `.../AMI_MarketApps/appium/` the same way CR079 ships the APK: git is
  truth, transfer is a mechanical step, never hand-authored on the remote host.
- **Black-box Appium + UiAutomator2** against the existing release APK — no
  `enableFlutterDriverExtension()` in the app, so this is tested exactly like any native Android
  app: text-based locators (Flutter exposes rendered text to the accessibility tree once
  UiAutomator2's own accessibility interrogation runs, no special build or driver plugin needed),
  screenshots, and gesture-driven checks.
- **Two mechanical usability checks**, the ones Saiful asked for by name:
  - *Non-scrolling overflow* — hierarchy check for a `scrollable` ancestor + a masked
    before/after screenshot diff around a calibrated swipe (masking `home_shell.dart`'s
    always-animating `TickerTape`, which otherwise reads as false movement). Flags only when
    nothing moved, nothing scrollable exists, and content reaches the fold.
  - *Nav-bar overlap* (the DEF075 class) — reads the real nav-bar band from
    `adb shell dumpsys window windows` (Flutter draws edge-to-edge behind the bar, so the
    FlutterView's own bounds carry no signal) and flags any interactive element whose bounds
    intrude on it, across every reachable modal sheet.
- **Reporting**: `hermes_folder/reports/appium/<run_id>/` — `report.html` (pytest-html),
  screenshots, raw accessibility-tree dumps, and a `summary.json` using `def_list.md`'s existing
  `ui_glitch`/`ux` category vocabulary. The harness never files a defect itself — findings are
  human/Claude-reviewed and promoted to `DEF###` (`Source = prompt`).
- **Test data**: Phase 1 needs no credentials (anonymous-first onboarding, `pm clear` for a cold
  session). The synthetic test account gets tagged so it can be added to the existing
  `feedback_user_report_exclusions` filter (same pattern as CR035's room-benchmark rows). Phase 2
  flows that need real credentials (sign-in test inbox, Alpaca paper-trading keys) are flagged as
  pending Saiful input, not fabricated — committed as `test_data/.env.example` placeholders only.

## Not changed

- App code — this CR ships test tooling only; nothing in `mobile/lib/` changes.
- CR079's APK pipeline — CR080 consumes its output (`.../apk/app-release.apk`), doesn't alter it.
- The existing manual device-pass checklist (CR004's A2) — this harness mirrors its journey for
  mechanical coverage, it doesn't replace the human pass.

## Phasing (this doc is the coverage backlog track `Q` ticks off)

- **Phase 1** (this session): harness scaffold, GO/NO-GO locator gate, both mechanical checks on
  the 3 flagged screens + 5 bottom-nav tabs + reachable modal sheets (convene / trade-ticket /
  brief / bug-report), one clean report reviewed and any real findings filed as defects.
- **Phase 2** (next `Q` session): full onboarding cold-start, Room 12-agent run-to-verdict, trade
  submission, `chart_fullscreen` rotation regression, seeded-account `merge_sheet` case, sign-in/
  Alpaca flows once Saiful supplies credentials.
- **Phase 3** (standing): full 25-screen sweep, multi-device matrix (add the Galaxy Note FE),
  visual-regression baselining across builds, `ms`/`ar` + RTL sweeps, scheduled recurring runs.

## Acceptance

1. `.claude/session-config.yml` has a `Q` track; `/start-fresh Q` resolves without error.
2. `qa/appium/` exists in git and mirrors 1:1 onto melehost's
   `.../AMI_MarketApps/appium/` after an rsync.
3. `test_00_smoke_hierarchy.py` passes against the live Galaxy A17 (`R5CY91AY99Y`) — proves
   text locators resolve and the nav-bar read parses.
4. `test_sheets_navbar.py` + `test_scroll_overflow.py` run clean and produce
   `report.html` + `summary.json` + annotated screenshots.
5. Any confirmed usability defect from that run is filed as `DEF###` (`ui_glitch`/`ux`),
   specifically confirming or ruling out the three static-analysis risk candidates above.
