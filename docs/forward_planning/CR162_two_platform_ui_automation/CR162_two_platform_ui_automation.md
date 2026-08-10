# CR162 — Two-platform automated UI testing (Android + iPhone)

**Filed:** 2026-08-10 · **Track:** `AT:R66` (work lands in track `Q`'s harness) · **Status:** in_progress · **Depends on:** CR080, CR079

## Why

Saiful asked for research on how to do automated testing on Android and iPhone. The
research produced one finding that changes what is buildable, so this CR builds it.

**Android is already solved.** CR080 shipped `qa/appium/` — Appium + UiAutomator2, 11 test
modules, black-box against the release APK on the Galaxy A17. **iOS is at zero**:
`mobile/ios/RunnerTests/RunnerTests.swift` is the untouched Flutter template stub, and every
iOS check has always been Saiful manually driving a phone.

That gap is not neglect. It is a Flutter engine limitation:

Flutter paints to a canvas and has no native widgets, so every black-box tool (Appium
UiAutomator2/XCUITest, Maestro, XCUITest directly) reads the **accessibility semantics
tree**, not a widget tree. On Android that tree is built as soon as an accessibility client
interrogates the window — which is exactly why CR080's harness needed no app changes at
all. **On iOS the engine gates it:**

```objc
bool enabled = UIAccessibilityIsVoiceOverRunning() || UIAccessibilityIsSwitchControlRunning();
```

So on a real iPhone with no VoiceOver running, XCUITest sees the entire app as **one opaque
`FlutterView`** and the page source comes back empty.
[flutter#25485](https://github.com/flutter/flutter/issues/25485) — filed December 2018,
**still open**. Signing and tooling are not the blocker; this is.

**The unlock** is one call from Dart, which forces semantics collection regardless of
whether any assistive technology is running:

```dart
SemanticsBinding.instance.ensureSemantics();
```

> *"Creates a new SemanticsHandle and requests the collection of semantics information.
> Semantics information are only collected when there are clients interested in them."*
> — [Flutter API](https://api.flutter.dev/flutter/semantics/SemanticsBinding/ensureSemantics.html)

Behind a `--dart-define`, that is ~10 lines and shipping builds are unaffected.

**The second half** is `SemanticsProperties.identifier` (Flutter ≥3.19; we are on 3.41.9).
It maps to **`resource-id` on Android** and **`accessibilityIdentifier` on iOS**, ships in
release builds, and is never shown to users. That gives *one* locator strategy that works
identically on both platforms — which is what lets this CR extend the existing harness
instead of forking a second one.

It also fixes a real Android problem. Today the app has **no stable test IDs whatsoever**
(0 occurrences of `Key('` in `mobile/lib`, 0 of `identifier:`, 9 files using `Semantics(`),
so `helpers/locators.py` finds everything by *rendered text*. That is why
`config/locales.py` has to carry every EN/AR/MS string verbatim just to tap a bottom-nav
tab: navigation is coupled to translation. Every ARB copy edit is a potential harness
break. IDs de-couple them.

### This CR supersedes CR080's "app code — not changed" boundary

CR080's `## Not changed` section states: *"App code — this CR ships test tooling only;
nothing in `mobile/lib/` changes."* That was correct for Android, where no app change was
needed. It is not achievable for iOS. **CR162 explicitly and knowingly amends that
boundary**, so a later reader does not mistake these edits for undocumented drift. The
amendment is deliberately narrow: a dart-define gate that is inert by default, plus
identifiers that are inert by construction.

### Rejected alternatives

- **Patrol** — the strongest Flutter-native E2E tool in 2026 (Dart, handles native
  permission dialogs, both platforms, integrates with Firebase Test Lab / BrowserStack).
  Rejected because it requires **instrumented builds**, which discards CR080's deliberate
  "test the actual release artifact" property, and because it means rewriting the whole
  Python harness in Dart. Re-openable if the black-box approach hits a ceiling.
- **Maestro** — does **not** natively support real iOS devices at all; local iOS physical
  device testing over USB is unsupported, only simulators or a cloud vendor. Same Flutter
  semantics problem underneath, with less control over it.
- **Cloud device farms** — BrowserStack Automate ~$129/mo/parallel, Sauce Labs RDC from
  $199/mo, Firebase Test Lab $5/device-hour physical (and weak on iOS coverage). These buy
  *device-matrix breadth*, which is not the missing thing; the missing thing is any iOS
  coverage at all. They also mean uploading a pre-launch stealth-alpha build to a third
  party. Revisit at beta when a matrix genuinely matters.
- **GitHub-hosted macOS runners for device CI** — $0.062/min with a 10× minute multiplier
  against the free tier, versus $0.006/min on Linux. The device suites stay local; only
  `flutter analyze` + `flutter test` go to CI, on Linux.

## What

### Phase 0 — app-side foundation (`mobile/lib/`)

- **QA semantics gate** in `mobile/lib/main.dart`, immediately after
  `WidgetsFlutterBinding.ensureInitialized()`: `--dart-define=AMI_QA_SEMANTICS=1` calls
  `SemanticsBinding.instance.ensureSemantics()`. Defaults to `false`, so TestFlight and Play
  builds are behaviourally identical to today.
- **Stable test IDs** — `Semantics(identifier: 'ami.<area>.<thing>')` on the surfaces the
  harness already drives: `hex_bottom_nav.dart` (already wraps in `Semantics`, so this is one
  added field), `hex_button.dart`, and the modal sheets the nav-bar check walks. Deliberately
  narrow — this is not an app-wide sweep. `identifier` forces its own `SemanticsNode`, so it
  never merges into an ancestor.
- **Structural guard** — a widget test asserting the bottom-nav identifiers exist, so a
  refactor that drops them fails on the Mac in seconds rather than as a confusing red device
  run days later. Per CLAUDE.md's "degrade loudly" rule, the gate must fail visibly.

### Phase 1 — make `qa/appium/` two-platform

Refactor, do not fork. The Android coupling is concentrated in four files:

- `config/devices.py` — `DeviceProfile` gains a `platform` field; add an iOS-simulator
  profile. **Note the bundle-id mismatch**: iOS is `ai.agenticmarketintel.amiTrade`,
  Android is `ai.agenticmarketintel.ami_trade`.
- `config/capabilities.py` — branch to `XCUITestOptions`. Every Android flag there earned its
  place from a specific gotcha (notably `waitForIdleTimeout=100` for `home_shell.dart`'s
  always-animating `TickerTape`); the iOS analogue is `waitForQuiescence=False`. Record the
  *why* in the docstring the same way the existing one does.
- `helpers/locators.py` — **the strategic change.** Add `by_id()` on
  `AppiumBy.ACCESSIBILITY_ID`, which resolves `resource-id` on Android and
  `accessibilityIdentifier` on iOS from one call. Keep the text helpers — the locale matrix
  legitimately asserts on visible text — but move *navigation* onto IDs, de-coupling
  `pages/base_page.py::open_tab()` from `LOCALES[locale].tab_labels`.
- `helpers/device.py` — adb/`dumpsys` only today; add an `xcrun simctl` path. iOS has no
  system nav bar, so the DEF075-class check in `helpers/layout.py` becomes bottom-safe-area
  (home-indicator) intrusion with a per-platform band source.
- `conftest.py` + `pyproject.toml` — `--platform` option (env `AMI_PLATFORM`, default
  `android`) and an `ios` marker.

### Phase 2 — iOS Simulator bring-up on the Mac

Appium 3 + XCUITest driver ≥10 (Node 25 and Xcode 26.6 are already installed; Appium is
not). A `scripts/build_qa_ios_sim.sh` building with `AMI_QA_SEMANTICS=1`. Port
`test_00_smoke_hierarchy.py` **first** — it is the GO/NO-GO gate and the thing that proves
the semantics unlock actually worked; it must fail naming `AMI_QA_SEMANTICS` when the tree
comes back opaque, never with a bare `NoSuchElement`. Then nav-bar, scroll-overflow, the 5
tab smokes, and the locale matrix last.

### Phase 3 — two standing gaps

- **CI that runs the mobile tests that already exist.** `mobile/test/` holds 70 files /
  ~525 cases and **nothing runs them automatically** — `.github/workflows/deploy-beta.yml`
  is the only workflow, is `workflow_dispatch`-only, and runs backend pytest alone. A
  `ubuntu-latest` job doing `flutter analyze lib/` + `flutter test`. Highest
  value-per-effort item in this CR.
- **melehost drift guard.** CR080 records the remote harness copy being hand-edited
  **twice**, the second time producing a bogus "27 FAIL / 2 PASS" report from a single
  `TypeError`, and notes this is a second occurrence with *"no guard designed yet"*. Add a
  pre-run check that refuses to run when the remote copy diverges from git, per the
  `failure_patterns.md` second-occurrence-gets-a-guard rule.

## Not changed

- CR080's harness *design* — black-box against the real release artifact, human-reviewed
  findings promoted to `DEF###`, reports under `hermes_folder/reports/appium/`. All kept.
- CR079's APK delivery pipeline.
- The Android test suite's behaviour. The Phase 1 refactor must leave it passing unchanged;
  that is an acceptance criterion, not an aspiration.
- Shipping build behaviour. `AMI_QA_SEMANTICS` is off unless explicitly passed.

## Out of scope (stated, not silently dropped)

- **Real iPhone via WebDriverAgent — NOT PLANNED (decided 2026-08-10).** Saiful: *"we will
  only use test flight and play bstore from now. dogfood eating."* Cable install is retired
  as a path to his devices, so the only iOS builds that exist are store builds — and a store
  build cannot carry `--dart-define=AMI_QA_SEMANTICS=1`, because that flag forces the
  semantics tree on permanently and has no business in a build real testers receive.
  **iOS automation is therefore simulator-only by construction, not by sequencing.** That is
  a sufficient answer rather than a compromise: the Simulator needs no WDA signing, no
  Developer Mode, and no device kept unlocked, and the gate runs there in 4.81s.
  `IPHONE_17` stays in `config/devices.py` in case the constraint changes; nothing else
  depends on it.
- Patrol, cloud device farms, iOS golden/screenshot regression.
- Appium Phase 2 flows still blocked on credentials (`qa/appium/test_data/README.md`).

## Acceptance

1. `flutter analyze lib/` and `flutter test` pass on the Mac with the Phase 0 changes, and a
   release build with no `--dart-define` has semantics collection **off**.
2. A widget test fails if the bottom-nav identifiers are removed.
3. The existing Android suite (`-m smoke`, `-m phase1`) passes **unchanged** after the
   Phase 1 refactor.
4. **The single acceptance question:** with `AMI_QA_SEMANTICS=1`, an Appium XCUITest page
   source of the running app contains the bottom-nav identifiers as addressable elements;
   with the flag off, it collapses to one `FlutterView`. If the first fails, stop and
   report — do not paper over it with coordinate taps.
5. CI runs `flutter analyze` + `flutter test` on push, on Linux.
6. The drift guard refuses to run against a hand-edited remote harness copy.

## Results (measured 2026-08-10, iPhone 17 Simulator / iOS 26.5, Appium 3.6.0 + XCUITest 12.3.0)

### CORRECTION (2026-08-10, found during CR163) — what was actually proven

This section originally claimed `ensureSemantics()` was proven to work. **It was not.**

`--dart-define=AMI_QA_SEMANTICS=1` was read with `bool.fromEnvironment`, which accepts only
the exact literals `'true'` / `'false'`. **`1` evaluates to `false`** (verified directly with
`dart run --define`). So the gate was dead in every build made that day and
`ensureSemantics()` never ran.

Everything below still happened — the tree was populated, the identifiers resolved, the gate
went green. But the cause was the **iOS Simulator**, which exposes the semantics tree without
VoiceOver. flutter#25485 says as much in its own report: the problem reproduces on physical
devices, not simulators.

What that changes, precisely:

- **The Simulator suite is unaffected and remains valid.** Identifiers resolve there with or
  without the flag, so the green gate, the 4.81s runtime and the DEF249 findings all stand.
- **`ensureSemantics()` is untested.** It is retained because it is correct in principle and
  costs nothing, but nothing here demonstrates it works. Since real-device iOS is out of
  scope (store-only distribution), there is no longer a path on which to test it.
- **The flag is now load-bearing for a different reason** — CR163's error sink genuinely
  depends on it, which is what surfaced this: a missing sink file is a hard failure, whereas
  a dead semantics flag produced no symptom at all.
- **The parse is fixed** (`main.dart` reads it as a string and accepts `1`/`true`/`yes`/`on`)
  and pinned by `mobile/test/qa/qa_flag_parsing_test.dart`.

The lesson is the reusable part: a flag whose failure mode is *silently off* was spelled the
strict way, and the feature that depended on it happened to work anyway. It took a second
feature depending on the same flag — one that failed loudly — to reveal it.

### The gate passes, and identifiers resolve on iOS

With `--dart-define=AMI_QA_SEMANTICS=1`, the app presents a fully populated accessibility
tree to XCUITest — **48 element nodes** carrying real content, not one opaque `FlutterView`:

```xml
<XCUIElementTypeStaticText value="AMI TRADE" …/>
<XCUIElementTypeStaticText value="CONCIERGE&#10;What's bringing you here?" …/>
```

And after completing onboarding, all five navigation identifiers are addressable:

```xml
<XCUIElementTypeButton name="ami.nav.floor"     label="FLOOR" traits="Selected, Button" y="747"/>
<XCUIElementTypeButton name="ami.nav.portfolio" …  y="747"/>
<XCUIElementTypeButton name="ami.nav.journal"   …  y="747"/>
<XCUIElementTypeButton name="ami.nav.lessons"   …  y="747"/>
<XCUIElementTypeButton name="ami.nav.settings"  …  y="747"/>
```

`SemanticsBinding.ensureSemantics()` + `SemanticsProperties.identifier` is a working
mechanism for black-box iOS automation of a Flutter release build. That was the open
question this CR existed to settle.

### What the first run cost, and what it bought

Bring-up surfaced five distinct problems. Four were in the harness or the toolchain; **two
were real defects in the app** (DEF249), and those are the ones worth noting:

| Problem | Where |
|---|---|
| `@appium/logger` unresolvable in the xcuitest driver's tree | toolchain — `npm i @appium/logger` in `~/.appium` |
| `content-desc` / `class` are Android-only attributes; XCUITest 500s on them | harness — `element_description()` / `is_text_input()` now dispatch |
| Concierge chips exposed as static text, not buttons | **app — DEF249** |
| Bottom-nav labels announced twice (`label="FLOOR\nFLOOR"`) | **app — DEF249**, predates this CR |
| Onboarding walk tapped `candidates[0]` — a chip from an already-answered turn | harness — now picks the bottom-most labelled control |

Both DEF249 findings are invisible to Android testing by construction (its bridge marks any
tappable node `clickable` regardless of semantics, and the child `Text` keeps its own node
there) and invisible to widget tests, which see Flutter's tree rather than the platform's.
The very first iOS run paying for itself twice over is the strongest argument for the CR.

### The gate is green

```
tests/test_00_smoke_hierarchy.py::test_semantics_identifiers_resolve   PASSED
tests/test_00_smoke_hierarchy.py::test_hierarchy_is_not_one_opaque_view PASSED
tests/test_00_smoke_hierarchy.py::test_bottom_nav_text_resolves        PASSED
tests/test_00_smoke_hierarchy.py::test_bottom_band_is_plausible        PASSED
tests/test_00_smoke_hierarchy.py::test_scale_is_plausible              PASSED
tests/test_00_smoke_hierarchy.py::test_floor_tab_is_default_landing    PASSED
============================== 6 passed in 4.81s ===============================
```

**4.81 seconds.** Worth stating plainly, because the bring-up runs took eight minutes each
and invited the wrong conclusion: iOS is *not* an order of magnitude slower than Android in
steady state. All of that time was the one-off Concierge walk plus first-session
WebDriverAgent startup. With `noReset=True` the interview is walked once per fresh install
and every later session takes the ~5s early return. Budget the iOS suite like the Android
one; budget the *first* run after a wipe at ~10 minutes.

### Known-open, stated rather than quietly dropped

- Only the smoke gate has been run on iOS. `-m phase1` (the five tab smokes), the nav-bar
  and scroll-overflow checks, and the locale matrix are ported but unrun on this platform.
- `scrollable_exists()` still returns `None` (undetermined) on iOS. The positive signal is
  now confirmed real — the Concierge screen emitted 4 `XCUIElementTypeScrollView` — but one
  screen does not establish that *every* scrollable surfaces as one, which is the claim a
  `False` would rest on.
- `TOP_CHROME_PT` / `BOTTOM_NAV_PT` in `pages/base_page.py` are provisional constants,
  deliberately generous so the always-animating `TickerTape` cannot land inside a diff band
  and read as false movement.

## Sources

- [flutter#25485 — iOS should provide a way to enable the semantic tree for testing frameworks](https://github.com/flutter/flutter/issues/25485)
- [SemanticsBinding.ensureSemantics](https://api.flutter.dev/flutter/semantics/SemanticsBinding/ensureSemantics.html)
- [SemanticsProperties.identifier](https://api.flutter.dev/flutter/semantics/SemanticsProperties/identifier.html)
- [Appium XCUITest driver — device setup](https://appium.github.io/appium-xcuitest-driver/12.1/getting-started/device-setup/)
- [Patrol documentation](https://patrol.leancode.co/documentation)
- [Firebase Test Lab](https://firebase.google.com/docs/test-lab) · [GitHub Actions 2026 pricing](https://github.com/resources/insights/2026-pricing-changes-for-github-actions)
