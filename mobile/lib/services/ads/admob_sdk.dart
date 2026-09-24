/// The AdMob SDK seam (CR122-MOBILE-C) — interfaces only, no SDK import.
///
/// [AdMobAdsService] talks to these abstractions; the ONLY file that imports
/// `google_mobile_ads` is `admob_real_sdk.dart` (structurally enforced in
/// `test/ads_structural_test.dart`). Tests fake this seam, which is what
/// keeps the whole suite from ever touching a platform channel — the same
/// reason `AdCapStore` exists for MOBILE-B.
///
/// The spec types carry the `ad_content_policy.dart` knobs by construction,
/// so an adapter cannot "forget" the age treatment or the content rating —
/// the unit test asserts every captured spec carries them.
library;

import 'package:ami_trade/services/ads/ad_content_policy.dart';
import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:flutter/widgets.dart';

/// One-time SDK configuration, applied before `MobileAds.initialize`.
@immutable
class AdMobSdkConfigSpec {
  const AdMobSdkConfigSpec({required this.testDeviceIds});

  final List<String> testDeviceIds;

  /// Policy constants ride along read-only so the adapter maps them from the
  /// single source in [AdContentPolicy].
  String get maxAdContentRating => AdContentPolicy.maxAdContentRating;
  AdAgeTreatment get ageTreatment => AdContentPolicy.ageTreatment;
}

/// Per-load request parameters.
@immutable
class AdMobRequestSpec {
  const AdMobRequestSpec({
    required this.adUnitId,
    required this.ccpaDoNotSell,
  });

  final String adUnitId;

  /// True → the request carries AdMob's CCPA restricted-data-processing
  /// extra (`rdp=1`), from the Settings "Do Not Sell" toggle (`ads.md:108`).
  final bool ccpaDoNotSell;
}

/// CR226 — banner request parameters. Unlike [AdMobRequestSpec], a banner's
/// size is DERIVED from the width it will render in (the whole point of an
/// anchored adaptive banner — see `admob_real_sdk.dart`'s
/// `getCurrentOrientationAnchoredAdaptiveBannerAdSize`), so the width the
/// caller's `LayoutBuilder` measured rides along with the request rather
/// than being read back out of a loaded handle.
@immutable
class AdMobBannerRequestSpec {
  const AdMobBannerRequestSpec({
    required this.adUnitId,
    required this.ccpaDoNotSell,
    required this.widthDp,
  });

  final String adUnitId;
  final bool ccpaDoNotSell;

  /// The available width in density-independent pixels — `AdSize`'s own
  /// unit, so this rides straight into the adaptive-size lookup with no
  /// device-pixel-ratio conversion at the call site.
  final int widthDp;
}

/// A loaded, showable interstitial. Disposal after dismiss is the adapter's
/// job (it owns the underlying SDK object).
abstract class AdMobInterstitialHandle {
  /// Presents the SDK's own full-screen ad and completes when it has been
  /// dismissed. The close affordance is the SDK's; the `ads.md` 5s-skippable
  /// rule is verified on-device (CR122 test plan, on-device #2).
  Future<void> show();
}

/// A loaded native ad, renderable inside our own labelled card chrome.
abstract class AdMobNativeHandle {
  /// The SDK's rendered native template. Must be given a bounded height by
  /// the caller ([preferredHeight]).
  Widget build(BuildContext context);

  /// Height for the medium native template.
  double get preferredHeight;

  Future<void> dispose();
}

/// CR226 — a loaded anchored adaptive banner. The SDK renders its own
/// platform view (a `PlatformView`/`AdWidget`, not composed Flutter chrome
/// like [AdMobNativeHandle]'s template), so `textScaler` never reaches it —
/// see `ad_adaptive_research.md` "the banner is the least risky element
/// here". [heightDp] is what the caller sizes its `SizedBox` to; it comes
/// from the SDK's own adaptive-size resolution, not a guess.
abstract class AdMobBannerHandle {
  Widget build(BuildContext context);

  double get heightDp;

  Future<void> dispose();
}

/// Loading seam over `google_mobile_ads`.
abstract class AdMobSdk {
  /// Apply [spec] (test devices + content policy) and initialise the SDK.
  /// Called at most once, and only AFTER consent allows requesting ads.
  Future<void> configureAndInitialize(AdMobSdkConfigSpec spec);

  /// Load an interstitial; null when the network has no fill (never throw
  /// for a no-fill).
  Future<AdMobInterstitialHandle?> loadInterstitial(AdMobRequestSpec spec);

  /// Load a native ad; null when the network has no fill.
  Future<AdMobNativeHandle?> loadNative(AdMobRequestSpec spec);

  /// CR226 — load an anchored adaptive banner sized from [spec.widthDp];
  /// null when the network has no fill.
  Future<AdMobBannerHandle?> loadBanner(AdMobBannerRequestSpec spec);
}

/// Seam over the UMP (User Messaging Platform) consent SDK.
abstract class AdMobUmpConsent {
  /// Runs the full consent gather: `requestConsentInfoUpdate` then
  /// `loadAndShowConsentFormIfRequired` — which shows the GDPR form in the
  /// EEA (or when [debugGeography] forces it) and, on iOS, the console-
  /// configured ATT explainer followed by the OS tracking prompt
  /// (`ads.md:106-107`). Returns the post-flow `canRequestAds`.
  Future<bool> gatherConsent({
    required AdMobDebugGeography debugGeography,
    required List<String> testDeviceIds,
  });

  /// Whether a privacy-options (re-consent) entry point must be offered.
  Future<bool> isPrivacyOptionsRequired();

  /// Shows the UMP privacy-options form (the consent re-open path).
  Future<void> showPrivacyOptionsForm();
}

/// AdMob fill types behind the [AdsService] facade — the subtypes the
/// MOBILE-A models reserved for this lane.
class AdMobInterstitialFill extends AdFill {
  const AdMobInterstitialFill(this.handle);
  final AdMobInterstitialHandle handle;
}

class AdMobNativeFill extends AdFill {
  const AdMobNativeFill(this.handle);
  final AdMobNativeHandle handle;
}

class AdMobBannerFill extends AdFill {
  const AdMobBannerFill(this.handle);
  final AdMobBannerHandle handle;
}
