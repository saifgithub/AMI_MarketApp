# AMI Trade — Appium UAT/usability harness

Black-box UI tests against the AMI Trade Android release APK, purely from a user's point of
view: does every screen scroll when it needs to, is every button reachable (not hidden under
the system nav bar), does the core journey hold together. Built under CR080 — see
`docs/forward_planning/CR080_appium_uat_harness/` for the why/what and the phased coverage
backlog.

This directory is the **source of truth in git**. It ships to melehost by rsync/scp, the same
"git is truth, transfer is mechanical" discipline `/promote-to-alpha` and CR079's
`share_apk_to_tester.sh` already use — never hand-edit the copy on melehost.

## Why Appium + UiAutomator2, not Flutter `integration_test`

The app has no `enableFlutterDriverExtension()` call anywhere (checked) and the release APK
isn't built with any test hook. So this harness treats AMI Trade like any black-box native
Android app: locators resolve by visible text (Flutter exposes rendered text to the Android
accessibility tree once an accessibility client — UiAutomator2's own server counts —
interrogates the window; no special build or driver plugin needed), backed up by
content-desc/clickable lookups and, last resort, coordinate taps.

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

`test_00_smoke_hierarchy.py` is a hard gate: it proves text locators resolve against the live
app and that the nav-bar band can be read. If it fails, don't run the rest — the documented
fallback (see the test file's docstring) is forcing a device accessibility service on before
trusting anything downstream.

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
