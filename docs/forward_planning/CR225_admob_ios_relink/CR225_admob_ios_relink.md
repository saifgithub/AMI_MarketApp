# CR225 — Re-link AdMob, fix the iOS release-build break (close out DEF351)

## What

Finish wiring real AdMob ad fill on iOS and Android-GMS release builds so Floor Pass
becomes genuinely ad-supported, closing the gap DEF351 left open. `google_mobile_ads`
is re-added to `pubspec.yaml`, the deleted `admob_real_sdk.dart` adapter is restored,
and an iOS release-build compile check is added so a future native dependency change
can't silently re-break the release build the way this one did.

## Why

Floor Pass was designed to be ad-supported (D-032) and CR122 (2026-07-29) built the
complete subsystem — `AdsService` facade, 6 approved placements, frequency caps,
content policy, Halal-safe house-ad targeting, 33 tests — but **zero third-party ad
revenue is possible in the app today**. DEF351 (2026-08-21) found that
`google_mobile_ads: ^9.1.0` broke every `flutter build ios --release` compile
(`Include of non-modular header inside framework module 'google_mobile_ads.FLTAd_Internal'`
/ `…FLTAdPreloader`). One fix was tried
(`CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES = YES` in the Podfile
`post_install`) and failed identically; a `git revert` was attempted and abandoned
(conflicted with concurrent arb-file edits on a shared checkout). The fix as shipped
was to unlink the SDK entirely — `ads_providers` always serves house-ad inventory
only. Users on Floor Pass today only ever see AMI's own upsell cards, never a paid ad.

Filed from an `/sm-elicitation` interview (transcript:
[`adding-ads-to-app.md`](../../.deliveryos/elicitation/adding-ads-to-app.md)), prompted
by Saiful asking to record "adding ads to the app" as a suggestion. Research during the
interview established this isn't a spec gap or a new feature — the spec
(`docs/initial_specs/06_monetization/ads.md`) and the build (CR122) are both already
done; the only missing piece is finishing the SDK link DEF351 gave up on.

## Root cause (confirmed via research, not yet verified on this repo's toolchain)

`google_mobile_ads` **9.1.0** introduced a regression: it added `FLTAdPreloader.h` and
a non-modular `#import <GoogleMobileAds/GoogleMobileAds_Beta.h>` inside
`FLTAd_Internal.h`, which trips `-Wnon-modular-include-in-framework-module`. **9.0.0
has neither** and does not trigger the error. A real-world fix (GitHub PR
`NelsonGrey/modulo-squares#343`) resolved the identical archive-build error by pinning
to `9.0.0` exactly and reverting a Podfile `post_install` override — because that
override only touches Pods-target build settings, not the **Runner** target, where
archive/release builds re-verify the module. This matches our own already-failed
attempt at the same Podfile-level fix.

Confirmed via pub.dev changelog (2026-09-22): **9.1.0 is still the latest published
version** — no later release exists, and no changelog entry from 9.0.0 through 9.1.0
acknowledges this issue. Pinning to 9.0.0 is the only currently-available fix, not a
stopgap awaiting a newer release upstream.

Second, less-confirmed lever (only if 9.0.0 turns out to lack a feature this app
needs, e.g. the ad preloader API or `ageRestrictedTreatment`): set
`CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES = YES` directly in
`ios/Flutter/Debug.xcconfig` and `ios/Flutter/Release.xcconfig` (which the Runner
target actually reads, unlike Podfile `post_install`), possibly combined with
`ENABLE_MODULE_VERIFIER = NO`. Mechanically plausible but only one non-independent
source found — treat as untested until verified on-device here.

## Scope

Mobile-only (iOS + Android-GMS). In scope:

1. Root-cause fix — pin `google_mobile_ads` to `9.0.0` exactly (not `^9.1.0`, not
   `^9.0.0`, either of which could resolve back into the broken 9.1.x range).
2. Restore/rebuild the deleted `admob_real_sdk.dart` adapter — CR122's structural
   guard already expects a `_adSdkAdapterExpected` flag flip for this.
3. Re-add `google_mobile_ads` to `mobile/pubspec.yaml`; Android-GMS side is expected
   to be unaffected (DEF351 was iOS-only) but gets the same on-device verification.
4. Add an iOS release-build compile step to CI or an equivalent gate — DEF351's own
   text names this as the guard gap deliberately left open ("nothing in CI compiles
   an iOS release, so the next native dependency will land the same way").
5. On-device verification per CR122's original test plan: test-unit fill AND
   registered-test-device fill, 5s skip, UMP consent (debug geography incl. decline
   path), ATT, CCPA toggle, frequency caps surviving a force-quit, a live purchase
   removing ads.

Out of scope:

- Android-HMS / Huawei Ads Kit (later, v1.1-aligned per decision log; Huawei
  AppGallery ships at v1.1, not alpha)
- Rewarded ads (D-036, permanently rejected — "this is not a game")
- Direct-deal inventory (CR122 explicitly deferred)
- Any change to placements, frequency caps, content policy, or house-ad targeting
  logic — already correct, already shipped, not touched by this CR
- Revisiting whether Floor Pass should have ads at all (D-032 locked), or the
  Halal-mandate house-ad-only targeting in `house_ads_service.dart` (already
  correctly scoped — Halal-mandated users get upsell-only house ads, never
  third-party ad income, consistent with the rejected-features register's brand-risk
  finding on rewarded ads)

## Constraints

- Check for concurrent edits to arb/l10n files before touching anything nearby —
  DEF351's abandoned revert conflicted there because other tracks were mid-edit on a
  shared checkout.
- Preserve CR122's structural no-forbidden-context guard and all 33 existing ads
  tests (currently passing against fakes) — no regression.
- Per CLAUDE.md's degrade-loudly rule: if AdMob fails to init at runtime, it must not
  silently look identical to the intentional house-ad-only fallback — log/report
  distinguishably.

## Changes (planned)

- `mobile/pubspec.yaml` — `google_mobile_ads: 9.0.0` (exact pin), uncomment.
- `mobile/lib/services/ads/admob_real_sdk.dart` — restore (deleted in DEF351's fix;
  git history has the pre-deletion version at commit `cb625863`'s parent).
- `mobile/lib/state/ads_providers.dart` — flip `_adSdkAdapterExpected` (or equivalent)
  back to serving the real adapter when available.
- `mobile/test/ads_structural_test.dart` — update the structural guard's expectation
  to match the re-linked state.
- CI / build gate — add an iOS release-build compile step (exact mechanism TBD at
  implementation time; CR162/CR163 territory per DEF351's own note).
- If the 9.0.0 pin turns out insufficient: `ios/Flutter/Debug.xcconfig` /
  `Release.xcconfig` additions as the fallback lever (see Root cause above).

## Acceptance

- `flutter build ios --release` succeeds with `google_mobile_ads` linked.
- Real AdMob ad renders in at least one of the 6 approved placements on a registered
  iOS test device and a registered Android-GMS test device.
- All 33 existing ads tests still pass; structural forbidden-context guard still
  passes.
- An iOS release-build compile step exists in CI or an equivalent gate.
- Manual, on-device (Saiful): 5s skip works, UMP consent flow (including decline)
  doesn't crash or silently skip, ATT prompt appears, CCPA toggle in Settings works,
  frequency caps hold across a force-quit, upgrading to a paid plan removes ads
  immediately.

## Status

proposed
