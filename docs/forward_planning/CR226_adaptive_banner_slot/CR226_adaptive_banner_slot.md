# CR226 — Global anchored banner slot, adaptive sizing, and a text-scale clamp

## What

Adds the **one globally-visible ad placement** the spec currently lacks: a 50dp anchored
adaptive AdMob banner mounted between the bottom nav and the ticker tape in
`home_shell.dart`. Sized from real available width so it is correct on every phone, on
folding devices' cover and inner screens, and on any future resize. Ships with a
**text-scale clamp on the app's fixed-height chrome**, which this design work surfaced as
an existing unguarded gap.

Three parts, deliberately in one CR because they land in the same widgets and the ad slot
is what makes the third one visible:

1. The banner slot itself (shell change + `ads.md` placement-table amendment)
2. Adaptive width/height derivation + reload-on-resize
3. A `textScaler` clamp on chrome, so the new slot lands next to chrome that does not
   overflow at accessibility text sizes

## Why

**The spec has no global placement.** `docs/initial_specs/06_monetization/ads.md` lists six
approved placements — between lessons, Daily Challenge results, Journal empty state, Sim
Portfolio empty state, Academy Hub bottom, Wallet & Plan. Every one is a specific screen or
a specific empty state. Floor Pass's revenue model therefore depends entirely on a user
reaching particular screens. Saiful asked (2026-09-22) for a placement visible across all
screens; this is that placement.

**The bottom-of-shell slot is the only candidate that is structurally safe.** Two
alternatives were mocked and rejected in the same session:

- *Header strip* (between title and trailing actions in `ami_screen_header.dart`): the
  usable gap is ~150–200dp wide, below the 320×50 minimum for any standard unit, so it
  could only ever carry custom-rendered house inventory — no programmatic fill. Worse, the
  header is shared with Settings and Mandate routes, both ad-banned, so it would need a
  per-screen suppression list.
- *Inside the ticker tape* (`ticker_tape.dart`): trivial to build — the tape is a `Row` of
  160dp items — and the worst option on brand grounds. It would place paid content inside a
  stream of live market quotes in the same 10pt mono, violating `ads.md`'s own
  "don't mimic native UI" rule at the one place in the app where confusion is most costly,
  in a financial app, under store review. The tape is also 28dp tall; no ad unit is.

The shell slot avoids both problems, and it inherits the forbidden-context bans from the
navigation architecture rather than from a list: `home_shell.dart:125` already documents
(for DEF190) that *"the nav lives in THIS Scaffold, below the pushed route."* Concierge,
Convene the Room, 1-on-1, Brief Your Agent, Mandate flows and the trade ticket are all
pushed routes that cover this Scaffold — so they hide the banner structurally. Per
CLAUDE.md, an instruction is not a control; this placement needs no new control because the
existing navigation gives it one.

**Adaptive sizing is not optional on folding hardware.** AdMob's anchored adaptive banner
derives height from the width it is given, capped at 150dp or 20% of screen height. Across
phones (375–430dp wide) that is a flat 50dp and nothing needs to adapt. On an unfolded
Galaxy Z Fold 7 (984 × 1092dp logical) it is ~90dp. A banner sized once at launch is simply
wrong after an unfold, so the width must come from a `LayoutBuilder` and the ad must be
disposed and reloaded on resize.

**The text-scale finding.** `app.dart:49` builds the `MaterialApp` with no `builder:`, and
`textScaler` is set nowhere in the app except `share_service.dart:172` (pinned to 1.0 for
offscreen PNG export, which is correct there). Flutter's default therefore applies: the OS
font-size setting multiplies every `fontSize` in the app, unbounded — iOS Dynamic Type
reaches ~3.1×, Android's slider 2.0×. Meanwhile the chrome is fixed: `ami_screen_header.dart:61`
and `hex_bottom_nav.dart:51` are both `height: 64`, `ticker_tape.dart:21` is `_kTapeHeight = 28.0`,
`chip_row.dart:22` is `height: 48`. At 2× a 12pt `labelMono` title renders at 24pt inside a
64dp box that also holds an icon and padding.

Only one of those surfaces is currently protected, and incidentally: `hex_bottom_nav.dart:102`
wraps its label in a `FittedBox(scaleDown)` — added for **DEF043**, where `labelMono`'s 1.8
letter-spacing made "PORTFOLIO" wrap. It absorbs text scaling as a side effect, not by
design. `ami_screen_header.dart` guards only its *subtitle* (`maxLines: 1` + ellipsis, added
after a caller overflowed the row by 326px); **the title itself has no guard at all.**

This is pre-existing and not caused by ads. It is folded in here because the banner sits
directly against that chrome, and shipping a bordered ad next to chrome that overflows at
accessibility sizes makes an existing defect look like a new one.

## Scope

Mobile-only, iOS + Android-GMS. **Depends on CR225** — there is no point adding an ad slot
while `google_mobile_ads` is unlinked; until CR225 lands this slot would serve house
inventory only.

In scope:

1. **Shell slot** — a third child in the `Column` at `home_shell.dart:146-175`, between the
   nav `Container` and `TickerTape`. Gated on `effective_plan` exactly as CR122's existing
   placements are; no ad for any paying plan including `trial_trader`.
2. **Adaptive sizing** — width from a `LayoutBuilder` (not `MediaQuery.of(context).size.width`,
   which is the whole screen and ignores safe-area and any future split-pane), passed to
   `AdSize.getCurrentOrientationAnchoredAdaptiveBannerAdSize(width)`. Ad disposed and reloaded
   when the constraint width changes.
3. **`ads.md` amendment** — a seventh row in the "Where ads appear" table for the global
   anchored banner, with the pushed-route rationale recorded so a later reader does not
   re-litigate why this one is allowed to be global when the other six are not.
4. **Text-scale clamp** — a `builder:` on `MaterialApp` clamping `textScaler` for the app's
   fixed-height chrome. Recommended bound ~1.3× on chrome while leaving body/lesson content
   free to scale, since clamping everything globally would defeat the accessibility setting
   rather than accommodate it. Exact mechanism at implementation time: either a global clamp
   with chrome-local overrides, or `MediaQuery.withClampedTextScaling` scoped around the
   header/nav/tape subtrees. The header title also gains the `maxLines`/ellipsis guard its
   subtitle already has.

Out of scope:

- **Two-pane / foldable layout.** An unfolded Fold currently renders the phone layout
  stretched across 984dp, and `main.dart:69`'s portrait lock does not prevent it — locking
  `portraitUp` stops rotation, not a window resize. That is a real gap, it predates this CR,
  and it touches every screen in the app. It is `main.dart:69`'s own comment
  (*"horizontal layouts come later"*) coming due, and belongs in its own CR. The banner is
  correct on those devices either way, which is precisely why it need not wait for them.
- Android-HMS / Huawei Ads Kit (v1.1-aligned, per decision log)
- Rewarded ads (D-036), direct-deal inventory (CR122 deferred)
- Any change to the existing six placements, frequency caps, content policy, or house-ad
  targeting

## Changes (planned)

- `mobile/lib/screens/home_shell.dart` — new banner child in the bottom `Column`; plan gate.
- `mobile/lib/widgets/ads/` — a new anchored-banner widget owning the `LayoutBuilder`,
  the size derivation, and dispose/reload on width change.
- `mobile/lib/app.dart` — `builder:` on `MaterialApp` for the text-scale clamp.
- `mobile/lib/widgets/hex/ami_screen_header.dart` — `maxLines: 1` + ellipsis on the title.
- `docs/initial_specs/06_monetization/ads.md` — seventh placement row + rationale.
- Tests: plan-gating table-driven over every `Plan`; size derivation across the width table
  below; the structural forbidden-context guard extended to assert the banner is absent on
  pushed routes; a text-scale widget test rendering chrome at 1.0×/2.0×/3.1× asserting no
  overflow.

## Reference — measured form factors

| Form factor | Logical size | Banner | 20% cap | Adaptation |
|---|---|---|---|---|
| iPhone SE / 13 mini | 375 × 667 | 50dp | 133dp | none |
| iPhone 13 / 15 / 17 | 390 × 844 | 50dp | 169dp | none |
| iPhone Pro Max | 430 × 932 | 50dp | 186dp | none |
| Pixel / Galaxy S | 412 × 915 | 50dp | 183dp | none |
| Z Fold 7 — cover | 540 × 1260 | 50dp | 252dp | none |
| Z Fold 7 — inner | 984 × 1092 | ~90dp | 218dp | width-derived |
| iPhone Fold — inner | ~1024 × 1450 *(leaked, unannounced)* | ~90dp | 290dp | width-derived |

The iPhone Fold row is from leaked specs — Apple has not announced the device. The
width-derived sizing holds regardless of the exact numbers, which is the point of deriving
rather than hard-coding.

## Acceptance

- Banner renders in the shell on iOS and Android-GMS for a Floor Pass user; absent for every
  paying plan including `trial_trader`.
- Banner is **absent** on all seven forbidden contexts, asserted by extending CR122's
  structural test — and verified by navigation, not by a suppression list.
- Banner height matches the table above at 390dp and at 984dp, verified by resizing (Android
  foldable emulator or a resizable window) rather than by two separate launches.
- Ad is disposed and reloaded on width change; no stale 390dp-sized banner after unfold.
- Chrome renders without overflow at text scale 1.0×, 2.0× and 3.1× on a 375dp-wide screen
  (the worst case: smallest width, largest scale), asserted in a widget test.
- Header title ellipsises rather than overflowing at 3.1×.
- Existing 33 ads tests and the structural guard still pass.
- Manual, on-device (Saiful): banner visible on Floor/Portfolio/Lessons/Journal, gone inside
  Concierge and the trade ticket, gone after upgrading to a paid plan.

## Implementation notes (AT:R85)

**Seam additions (AdMob-agnostic, no `google_mobile_ads` import outside
`admob_real_sdk.dart`):**

- `services/ads/ads_models.dart` — `AdFormat.banner`, `AdPlacement.globalBanner`
  (the 7th entry in `AdPlacement.approved`).
- `services/ads/admob_sdk.dart` — `AdMobBannerRequestSpec` (carries `widthDp`,
  unlike the fixed-size interstitial/native specs), `AdMobBannerHandle`,
  `AdMobSdk.loadBanner`, `AdMobBannerFill`.
- `services/ads/admob_real_sdk.dart` — `RealAdMobSdk.loadBanner` calls
  `AdSize.getLargeAnchoredAdaptiveBannerAdSize(widthDp)` — 9.0.0's
  non-deprecated resolver (the SDK's own deprecation notice on
  `getCurrentOrientationAnchoredAdaptiveBannerAdSize` points here; same
  native adaptive-size call). Returns null (⇒ house fallback) when the SDK
  can't resolve a size for the given width.
- `services/ads/ads_service.dart` / `admob_ads_service.dart` /
  `house_ads_service.dart` — `AdsService.requestFill` gained an optional
  `widthDp` parameter (default 0, ignored by every non-banner placement).
  `AdMobAdsService` reuses the NATIVE unit id for banner requests — no
  4th build-time ad-unit-id define; flagged in the doc for Saiful's console
  setup, revisit if a dedicated banner unit id is wanted.
- `state/ads_providers.dart` — `AdGate.request` gained `widthDp`; banner is
  EXEMPT from the `ads.md:59-60` frequency caps and from `recordShown`'s
  impression counter (see the library doc's job 4: the banner is persistent
  chrome mounted once for the app's lifetime, not a discrete per-screen
  impression — running it through the 8/day native-card cap would hide it
  after 8 re-renders, not after 8 actual ad SHOWINGS). Still goes through
  the SAME plan gate as every other placement.

**Rendering:**

- `widgets/ads/anchored_ad_banner.dart` (new) — the actual widget.
  `LayoutBuilder` measures width (not `MediaQuery.of(context).size.width`,
  per §Scope 2); disposes + re-requests on width change (verified by test:
  a simulated unfold from 390dp→984dp triggers a fresh request at the new
  width). Renders `AdMobBannerFill` via the SDK's own `AdWidget`-backed
  `build()`, `HouseAdFill` via the new `HouseAdBannerStrip`, and draws the
  AdMob-policy separator (a `slate700` top border) directly around its OWN
  content so the separator collapses to zero height with the banner rather
  than being a shell-level fixed gap that could appear with nothing under
  it on a paid-tier screen.
- `widgets/ads/house_ad_banner_strip.dart` (new) — compact single-row house
  fallback (badge, one-line headline, text CTA), reusing `HouseAdCard`'s
  existing `copyFor` targeting table rather than a second copy of the
  upsell strings. No dismiss X: `ads.md`'s "remove ads lives in Wallet &
  Plan" already covers that, and a persistent chrome slot self-dismissing
  mid-session would contradict "visible on every post-onboarding page".
- `widgets/ads/shell_banner_slot.dart` — now renders `AnchoredAdBanner`
  (was `SizedBox.shrink()` under CR232).
- `screens/home_shell.dart` — comment updated; no structural change to the
  chrome `Column` itself (CR232 already placed the slot in the right order).

**CR225's structural test-vs-live gate, landed here** (Saiful's 2026-09-24
ruling on internal vs. production ad units applies to both CRs' surface —
documented once, here, since CR226 is what actually renders a banner an
internal build could accidentally leak a real unit id through):

- `services/ads/admob_config.dart` — new `AdMobReleaseChannel` enum
  (`unknown` | `internal_` | `production`) and `AMI_RELEASE_CHANNEL`
  dart-define. `AdMobConfig.resolve` takes a `channel` parameter;
  `ADMOB_MODE=live` is honoured ONLY when `channel == production` — every
  other channel (including the unset/dev default, the conservative
  reading) downgrades to Google's reserved test unit ids, loudly logged,
  rather than either serving real units or refusing to house fill.
- `scripts/build_testflight.sh` / `scripts/build_playstore.sh` — derive
  `AMI_RELEASE_CHANNEL` STRUCTURALLY from the same `--internal-only` /
  `--production` flags that already gate the RevenueCat Test-Store-key and
  CR109 games checks (never an independently-settable env var an operator
  could forget to unset), forward it as a dart-define.
- `scripts/install_iphone.sh` — deliberately does NOT forward
  `AMI_RELEASE_CHANNEL` at all, so a cable install always resolves
  `unknown` — the same conservative downgrade applies even if
  `ADMOB_MODE=live` is set locally (e.g. copy-pasted from a production
  build's env).
- Real unit ids: no placeholder needed beyond what already existed —
  `ADMOB_INTERSTITIAL_AD_UNIT_ID` / `ADMOB_NATIVE_AD_UNIT_ID` already
  default to empty string and `AdMobConfig.resolve`'s `mode=live` branch
  already refuses (house fallback, loud log) on an empty id. The banner
  reuses the native id (see above), so it inherits that same "empty id ⇒
  refuse, never silently serve nothing that looks like success" guarantee.

**Text-scale clamp:**

- `theme/ami_text_scale.dart` (new) — `kChromeMaxTextScaleFactor = 1.3`
  (the doc's recommended bound) and `clampChromeTextScale`, a thin wrapper
  over `MediaQuery.withClampedTextScaling`.
- `widgets/hex/ami_screen_header.dart` — `build` wrapped in the clamp; the
  title gained the `maxLines: 1` + ellipsis guard the subtitle already had
  (wrapped in `Flexible` to make the ellipsis effective inside the `Row`).
- `widgets/hex/hex_bottom_nav.dart` — `build` wrapped in the clamp. **Found
  and fixed a real overflow the clamp alone did not prevent**: the label's
  `FittedBox(scaleDown)` only scales down against a BOUNDED constraint: as
  the last child of a `mainAxisSize: min` Column it was sizing to its own
  natural height, so at 3.1× scale (even clamped to 1.3×) the label's
  intrinsic line height still exceeded the 15dp left in the 64dp cell after
  the fixed 33dp icon zone — a genuine `RenderFlex` overflow the CR226
  widget test caught on a real pump, not a hypothetical. Fixed by giving
  the label row an explicit `SizedBox(height: 15)` so `FittedBox` has an
  actual box to scale into.
- `widgets/ticker_tape.dart` — `TickerTape.build`'s return wrapped in the
  clamp (not the `bottomInset` read above it, which correctly uses the
  ambient unclamped `MediaQuery`).
- `app.dart` — `builder:` added on `MaterialApp`, the entry point the CR
  doc names; deliberately a pass-through (`child ?? SizedBox.shrink()`),
  not a global clamp — clamping app-wide would defeat the OS accessibility
  setting for lesson/agent body content, which is exactly why the actual
  clamps are local to the three chrome widgets instead.
- `docs/initial_specs/06_monetization/ads.md` — 7th placement row added to
  "Where ads appear", with the structural-inheritance rationale recorded so
  a later reader doesn't re-litigate why this placement is allowed to be
  global when the other six aren't (per the CR's own "Why" section).

**Out of scope, confirmed untouched:** two-pane/foldable layout (still
`main.dart:69`'s open item), Android-HMS, rewarded ads, direct-deal
inventory, any change to the six existing placements' caps/policy/targeting.

## Acceptance — verification run this session

- `flutter build ios --release --no-codesign` — succeeded (see CR225's own
  acceptance notes; this is the same binary CR226's banner code compiles
  into).
- `flutter build appbundle --release` — succeeded, exit 0, 62.1MB AAB,
  278.9s. (Beyond this task's strict requirement — the task said skip if
  signing keys are unavailable; a keystore was present at
  `~/.android-keys/keystore.properties`, so it was run and is clean.)
- `flutter test` (full suite) — 1535 tests, all green, exit 0. New/changed
  coverage: `test/services/admob_config_test.dart` (CR225 channel-gate
  group, 7 tests), `test/services/admob_ads_service_test.dart` (CR226
  banner-routing group, 2 tests), `test/widgets/ads/anchored_ad_banner_test.dart`
  (new, 11 tests: plan gating, adaptive width, dispose/reload on resize,
  never-a-blank-slot, policy separator), `test/widgets/ami_text_scale_test.dart`
  (new, 9 tests: chrome at 1.0×/2.0×/3.1×, title ellipsis, clamp does not
  fight a smaller-than-default scale), `test/screens/home_shell_test.dart`
  (2 new tests: slot position in chrome order, keyboard hides it).
- `flutter analyze` — 11 issues (baseline, 0 errors).
- Manual on-device verification (Saiful) — not run this session, per the
  task's own instruction not to run a device install.

## Status

in_progress (submitted for audit, AT:R85)
