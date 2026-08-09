# AMI Trade — Appium UAT/usability harness

Black-box UI tests against the AMI Trade release build, purely from a user's point of
view: does every screen scroll when it needs to, is every button reachable (not hidden under
the system nav bar or the home indicator), does the core journey hold together. Built under
CR080 (Android) and extended to iOS under CR162 — see
`docs/forward_planning/CR080_appium_uat_harness/` for the phased coverage backlog and
`docs/forward_planning/CR162_two_platform_ui_automation/` for the two-platform work.

| | Android | iOS |
|---|---|---|
| Driver | UiAutomator2 | XCUITest |
| Device | Galaxy A17 on melehost (USB) | Simulator on the Mac; real iPhone once WDA is signed |
| Build | plain release APK | needs `--dart-define=AMI_QA_SEMANTICS=1` — see below |
| Select | default, or `--platform=android` | `--platform=ios` / `AMI_PLATFORM=ios` |

This directory is the **source of truth in git**. It ships to melehost by rsync/scp, the same
"git is truth, transfer is mechanical" discipline `/promote-to-alpha` and CR079's
`share_apk_to_tester.sh` already use — never hand-edit the copy on melehost. That is now
**enforced**: `tools/harness_manifest.py` records a SHA-256 per delivered file and
`pytest_sessionstart` refuses to run a copy that has been edited in place (CR080 lost a
session to this twice; the second time one locally-introduced `TypeError` was reported as 27
application failures, none of which were real). Extra files you add on the rig are fine —
modified delivered files are not. After changing anything here, run
`python3 tools/harness_manifest.py write` and commit the manifest; CI fails on a stale one.

## Why black-box Appium, not Flutter `integration_test`

The app has no `enableFlutterDriverExtension()` call anywhere and the release build carries no
test hook, so this harness drives AMI Trade the way any black-box native test would — against
the same artifact users get, not an instrumented one.

Flutter paints to a canvas rather than emitting native widgets, so on both platforms the only
thing a black-box driver can see is the **accessibility semantics tree**. The two platforms
differ in kind here, and it is the single most important thing to understand about this
harness:

- **Android** builds that tree as soon as an accessibility client (UiAutomator2's own server)
  interrogates the window. No app cooperation needed — which is why CR080 shipped without
  touching `mobile/lib/` at all.
- **iOS does not.** The engine gates it on
  `UIAccessibilityIsVoiceOverRunning() || UIAccessibilityIsSwitchControlRunning()`
  ([flutter#25485](https://github.com/flutter/flutter/issues/25485), open since 2018). Without
  VoiceOver actually running, XCUITest sees the entire app as **one opaque `FlutterView` with
  an empty page source**. This is why iOS automation was at zero before CR162, and it is not
  a signing or tooling problem.

CR162's fix: `--dart-define=AMI_QA_SEMANTICS=1` makes `mobile/lib/main.dart` call
`SemanticsBinding.instance.ensureSemantics()`, forcing the tree on. Off by default, so
shipping builds are unaffected. `scripts/build_qa_ios_sim.sh` passes it.

### Locators: identifiers first, text second

The app sets `Semantics(identifier:)` on its navigation surfaces
(`mobile/lib/qa/semantics_ids.dart`, mirrored here in `config/semantics_ids.py`). Flutter maps
that to **`resource-id` on Android** and **`accessibilityIdentifier` on iOS** — note those are
*different Appium strategies*, not one: `AppiumBy.ACCESSIBILITY_ID` means `content-desc` on
Android and would silently match nothing. `helpers/locators.py::by_id()` dispatches correctly
and `tests_offline/` guards that it keeps doing so.

Text locators still exist, because `test_locale_matrix.py` asserts on rendered copy and that
*is* the thing under test there. But navigation goes through identifiers, which de-couples it
from translation — previously `config/locales.py` had to carry every EN/AR/MS string verbatim
just to tap a bottom-nav tab, so any ARB copy edit could break the suite.

## One-time melehost bootstrap

Everything here runs **on melehost** (`ssh melehost`), because that's where the target device
(Galaxy A17, serial `R5CY91AY99Y`) is attached over USB. Nothing here touches the `ami_*`
Docker stack — Appium talks to adb/USB only.

```bash
# Node is at ~/.local/bin (not on PATH for non-interactive ssh) — use a login shell.
ssh melehost
bash -lc '
  npm install -g appium
  appium driver install uiautomator2
  appium --version
'

# Python side, in this directory once rsync'd:
cd ~/hermes_folder/project/AMI_MarketApps/appium
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pin the device locale to en-US — most locators in this harness are English
# strings and expect the app's default (no in-app override set) to render in
# English. Do this once per device/reset:
adb -s R5CY91AY99Y shell settings put system system_locales en-US
# Note: AMI Trade's language picker (Settings -> Language) is an app-level
# override independent of this device setting — see "Multi-language matrix"
# below. Pinning the device locale only fixes what Phase 1's *default* state
# looks like; it doesn't need to change for AR/MS testing.

# Confirm the device is visible:
adb devices -l
```

## Running

Start an Appium server (one terminal, left running):

```bash
bash -lc 'appium --address 127.0.0.1 --port 4723'
```

Run the suite (another terminal/session):

```bash
cd ~/hermes_folder/project/AMI_MarketApps/appium
source .venv/bin/activate
export AMI_REPORT_DIR="$HOME/hermes_folder/reports/appium/$(date -u +%Y-%m-%dT%H%M%SZ)"
mkdir -p "$AMI_REPORT_DIR"
pytest -m phase1 -v
```

Or a single mechanical check:

```bash
pytest tests/test_00_smoke_hierarchy.py -v          # GO/NO-GO gate — run this first, always
pytest tests/test_sheets_navbar.py -v                # DEF075-class nav-bar overlap
pytest tests/test_scroll_overflow.py -v              # non-scrolling-overflow candidates
```

`test_00_smoke_hierarchy.py` is a hard gate. It proves the semantics identifiers resolve
against the live app, that the hierarchy is not a single opaque view, that text locators work,
and that the bottom-obstruction band and points-per-pixel scale are plausible. If it fails,
don't run the rest — every downstream failure would look like an app bug and would not be one.
Its assertion messages name the likely cause (missing `AMI_QA_SEMANTICS`, a stale build, or
Dart/Python identifier drift) rather than leaving you to guess.

## Running on iOS (the Mac)

One-time, on the Mac — Xcode and Node are already there:

```bash
npm install -g appium@latest
appium driver install xcuitest          # XCUITest >=10 requires Appium 3
cd qa/appium && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Per run:

```bash
# 1. Build + install the QA app. The dart-define is the whole point — see above.
scripts/build_qa_ios_sim.sh --sim "iPhone 17"

# 2. Appium server, left running in its own terminal
appium --address 127.0.0.1 --port 4723

# 3. The suite
cd qa/appium
export AMI_REPORT_DIR="/tmp/appium/$(date -u +%Y-%m-%dT%H%M%SZ)-ios"
AMI_PLATFORM=ios .venv/bin/python -m pytest -m smoke -v     # gate first, always
AMI_PLATFORM=ios .venv/bin/python -m pytest -m phase1 -v
```

`AMI_IOS_SIM_NAME` picks a different simulator (default `iPhone 17`). The UDID is resolved by
name at run time and never committed — a simulator UDID is machine-specific.

**The real iPhone 17 is not wired up yet.** It needs WebDriverAgent signed against Saiful's
Apple developer account plus Developer Mode on the device. The profile is already in
`config/devices.py` (`IPHONE_17`), so that follow-up is a profile selection plus signing
capabilities, not new code.

### Two iOS caveats that are not bugs

- **`scrollable_exists()` returns `None`, not `False`, on iOS.** Flutter's iOS accessibility
  bridge does not reliably surface a scrollable container, so "found none" does not license
  "nothing scrolls". Scroll-overflow findings from an iOS run are therefore recorded at `low`
  severity with `scrollable_check: "undetermined"` and want a human look before filing.
- **The bottom band is a constant on iOS, not a measurement.** Android reads the real nav-bar
  inset from the window manager; iOS exposes no equivalent, so the 34pt home-indicator
  constant is used and `navbar_top_y_measured: false` says so in `summary.json`.

## Output

Every run writes to `$AMI_REPORT_DIR` (default `hermes_folder/reports/appium/<run_id>/`):

- `report.html` — self-contained pytest-html report.
- `screenshots/<screen>__<state>.png` — one per screen visited, plus annotated evidence for
  flagged nav-bar-overlap / scroll-overflow findings.
- `page_source/<screen>.xml` — raw accessibility-tree dumps (lets a later session locate
  elements without re-running the device).
- `summary.json` — machine-readable findings, using `docs/defect/def_list.md`'s existing
  `ui_glitch`/`ux` category vocabulary as `suggested_category`.

**This harness never files a `DEF###` itself.** A human (or a later Claude session) reviews
`summary.json` + the annotated screenshots and promotes confirmed findings into the defect
register (`Source = prompt`).

## Multi-language matrix (Phase 3)

AMI Trade ships 3 languages (EN, AR, MS — `mobile/lib/l10n/app_{en,ar,ms}.arb`). The bottom-nav
labels, tab headings, and hard-asserted content strings for each are in `config/locales.py`,
copied verbatim from the live ARBs — see that file's docstring for real translation gaps already
found this way (untranslated "Floor" tab, a mixed-script Convene sheet heading in AR/MS).

```bash
pytest -m locale -v          # EN + AR + MS: content probe, scroll-overflow, nav-bar overlap,
                              # RTL bottom-nav mirroring — across the 5 tabs + Convene sheet
```

This switches the **in-app** language override (Settings -> Language) per locale, not the device
locale — matches how a real user changes language, and needs no relaunch. Every mechanical check
Phase 1 already proved out on English re-runs per locale, because translated strings change
length: a header that fits in English can overflow or wrap once translated, which is exactly
Saiful's original ask ("screens that do not scroll when they need to") triggered by locale
instead of by data volume. `test_bottom_nav_mirrors_under_rtl` additionally hard-asserts that
Arabic mirrors the bottom nav left/right, since that's a structural Flutter guarantee for the
plain `Row` `HexBottomNav` uses (`mobile/lib/widgets/hex/hex_bottom_nav.dart`), not a heuristic —
a mismatch there is a confirmed bug, not a human-triage candidate.

## Test data

See `test_data/README.md`. Phase 1 needs no credentials — anonymous-first onboarding, cold
session via `adb shell pm clear`. Phase 2 flows (sign-in, Alpaca-connect) need real credentials
that must come from Saiful; never fabricate them.

## Phasing

See CR080's coverage backlog. Phase 1 (this pass): GO/NO-GO gate, both mechanical checks on the
three static-analysis-flagged screens (`agent_unlocked_screen`, `convene_sheet`, and
`merge_sheet` — the last one only reachable with seeded backend state, so it stays on the
existing widget-test guard for Phase 1) plus the 5 bottom-nav tabs and reachable modal sheets.
