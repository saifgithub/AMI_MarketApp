/// The ONLY file that imports `google_mobile_ads` (CR122-MOBILE-C).
///
/// Restored by CR225 — DEF351 deleted this file to unlink the plugin after
/// `google_mobile_ads: ^9.1.0` broke every `flutter build ios --release`
/// archive (a non-modular header import inside the vendored framework).
/// CR225 pins `pubspec.yaml` to `9.0.0` exactly, which does not carry the
/// offending header, and restores this adapter unchanged — nothing in the
/// seam it implements moved while it was gone.
///
/// Adapters from the `admob_sdk.dart` seam to the real SDK + UMP. The
/// structural test (`test/ads_structural_test.dart`) pins the import to this
/// exact file — everything else in the app, screens and services alike, sees
/// only the seam. Nothing here is reachable until `AdMobConfig.setup`
/// resolves non-null AND the UMP flow allows requesting ads
/// (`admob_ads_service.dart`), which together keep an ADMOB_MODE-less build
/// from ever touching a platform channel.
///
/// Native counterparts (committed with GOOGLE'S PUBLISHED SAMPLE app ids —
/// swapping in Saiful's real ones is the liaison step in
/// `CR122_admob_compliance_and_liaison.md`):
///   * `ios/Runner/Info.plist` — `GADApplicationIdentifier`,
///     `GADDelayAppMeasurementInit`, `NSUserTrackingUsageDescription`,
///     `SKAdNetworkItems`;
///   * `android/.../AndroidManifest.xml` — `APPLICATION_ID`,
///     `DELAY_APP_MEASUREMENT_INIT`.
/// Both DELAY_APP_MEASUREMENT flags matter: they stop the native SDK from
/// starting itself at process launch, so measurement begins only if and when
/// this file's `configureAndInitialize` runs.
library;

import 'dart:async';

import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ad_content_policy.dart';
import 'package:flutter/widgets.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

/// How long a load may take before we answer "no fill" and let house
/// inventory serve. A late-arriving ad is disposed, not shown.
const _loadTimeout = Duration(seconds: 12);

class RealAdMobSdk implements AdMobSdk {
  @override
  Future<void> configureAndInitialize(AdMobSdkConfigSpec spec) async {
    // CR225: 9.0.0's `RequestConfiguration` predates the `AgeRestrictedTreatment`
    // enum 9.1.0 added — it exposes the older, separate
    // `tagForChildDirectedTreatment` / `tagForUnderAgeOfConsent` int-coded
    // fields instead. The mapping stays total (every `AdAgeTreatment` value
    // still maps explicitly) so the policy contract `ad_content_policy.dart`
    // documents — "age treatment: NONE, never silently dropped" — holds under
    // the older API too; only the wire representation changed.
    final tag = _tagFor(spec.ageTreatment);
    await MobileAds.instance.updateRequestConfiguration(RequestConfiguration(
      testDeviceIds: spec.testDeviceIds,
      maxAdContentRating: spec.maxAdContentRating,
      tagForChildDirectedTreatment: tag,
      tagForUnderAgeOfConsent: tag,
    ));
    await MobileAds.instance.initialize();
  }

  int _tagFor(AdAgeTreatment t) {
    switch (t) {
      case AdAgeTreatment.none:
        return TagForChildDirectedTreatment.unspecified;
      case AdAgeTreatment.child:
        return TagForChildDirectedTreatment.yes;
      case AdAgeTreatment.teen:
        // 9.0.0 has no distinct "teen" tag (that granularity arrived with
        // 9.1.0's AgeRestrictedTreatment) — "child directed" is the closer,
        // more conservative of the two available tags, never "unspecified"
        // (AdAgeTreatment.teen is unused today; ad_content_policy.dart pins
        // the app to AdAgeTreatment.none, but the mapping stays total rather
        // than assuming that never changes).
        return TagForChildDirectedTreatment.yes;
    }
  }

  // CR226 — `ccpaDoNotSell` lives on both `AdMobRequestSpec` and
  // `AdMobBannerRequestSpec` (no shared base class for the two — they diverge
  // on `adUnitId` vs the width-bearing banner shape), so this takes the bool
  // directly rather than either spec type, and both call sites pass their own
  // `.ccpaDoNotSell` straight through.
  AdRequest _request({required bool ccpaDoNotSell}) => AdRequest(
        // CCPA restricted data processing (`ads.md:108`) — the Settings
        // "Do Not Sell" toggle rides every request as AdMob's rdp extra.
        extras: ccpaDoNotSell ? const {'rdp': '1'} : null,
      );

  @override
  Future<AdMobInterstitialHandle?> loadInterstitial(
      AdMobRequestSpec spec) async {
    final completer = Completer<AdMobInterstitialHandle?>();
    await InterstitialAd.load(
      adUnitId: spec.adUnitId,
      request: _request(ccpaDoNotSell: spec.ccpaDoNotSell),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) {
          if (completer.isCompleted) {
            // Arrived after the timeout answered "no fill" — never show a
            // stale ad, release it.
            ad.dispose();
            return;
          }
          completer.complete(_RealInterstitialHandle(ad));
        },
        onAdFailedToLoad: (error) {
          debugPrint('CR122 AdMob interstitial load failed: $error');
          if (!completer.isCompleted) completer.complete(null);
        },
      ),
    );
    return completer.future.timeout(_loadTimeout, onTimeout: () => null);
  }

  @override
  Future<AdMobNativeHandle?> loadNative(AdMobRequestSpec spec) async {
    final completer = Completer<AdMobNativeHandle?>();
    final ad = NativeAd(
      adUnitId: spec.adUnitId,
      request: _request(ccpaDoNotSell: spec.ccpaDoNotSell),
      // Dart-side native template — no per-platform NativeAdFactory code.
      // Our own AD-labelled chrome and dismiss control wrap this in
      // `widgets/ads/admob_native_card.dart`.
      nativeTemplateStyle: NativeTemplateStyle(templateType: TemplateType.medium),
      listener: NativeAdListener(
        onAdLoaded: (ad) {
          if (completer.isCompleted) {
            ad.dispose();
            return;
          }
          completer.complete(_RealNativeHandle(ad as NativeAd));
        },
        onAdFailedToLoad: (ad, error) {
          debugPrint('CR122 AdMob native load failed: $error');
          ad.dispose();
          if (!completer.isCompleted) completer.complete(null);
        },
      ),
    );
    await ad.load();
    return completer.future.timeout(_loadTimeout, onTimeout: () => null);
  }

  @override
  Future<AdMobBannerHandle?> loadBanner(AdMobBannerRequestSpec spec) async {
    // CR226 — the anchored ADAPTIVE size, derived from the width the caller's
    // `LayoutBuilder` measured (never a fixed AdSize.banner constant, and
    // never MediaQuery's full-screen width — see `widgets/ads/anchored_ad_banner.dart`
    // for why). `getLargeAnchoredAdaptiveBannerAdSize` is 9.0.0's
    // non-deprecated resolver (the SDK's own doc points here off the older
    // `getCurrentOrientationAnchoredAdaptiveBannerAdSize`) — same native
    // adaptive-size call, current Google-recommended entry point. Null means
    // the SDK could not find a valid size for this width (e.g. width <= 0
    // during a transient layout pass); that is "no fill", not a crash.
    final size =
        await AdSize.getLargeAnchoredAdaptiveBannerAdSize(spec.widthDp);
    if (size == null) {
      debugPrint('CR226 AdMob: no adaptive banner size for width '
          '${spec.widthDp}dp — house fallback');
      return null;
    }
    final completer = Completer<AdMobBannerHandle?>();
    final ad = BannerAd(
      adUnitId: spec.adUnitId,
      size: size,
      request: _request(ccpaDoNotSell: spec.ccpaDoNotSell),
      listener: BannerAdListener(
        onAdLoaded: (ad) {
          if (completer.isCompleted) {
            ad.dispose();
            return;
          }
          completer.complete(
              _RealBannerHandle(ad as BannerAd, size.height.toDouble()));
        },
        onAdFailedToLoad: (ad, error) {
          debugPrint('CR226 AdMob banner load failed: $error');
          ad.dispose();
          if (!completer.isCompleted) completer.complete(null);
        },
      ),
    );
    await ad.load();
    return completer.future.timeout(_loadTimeout, onTimeout: () => null);
  }
}

class _RealInterstitialHandle implements AdMobInterstitialHandle {
  _RealInterstitialHandle(this._ad);

  final InterstitialAd _ad;

  @override
  Future<void> show() {
    final dismissed = Completer<void>();
    _ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdDismissedFullScreenContent: (ad) {
        ad.dispose();
        if (!dismissed.isCompleted) dismissed.complete();
      },
      onAdFailedToShowFullScreenContent: (ad, error) {
        debugPrint('CR122 AdMob interstitial failed to show: $error');
        ad.dispose();
        if (!dismissed.isCompleted) dismissed.complete();
      },
    );
    unawaited(_ad.show());
    return dismissed.future;
  }
}

class _RealNativeHandle implements AdMobNativeHandle {
  _RealNativeHandle(this._ad);

  final NativeAd _ad;

  @override
  Widget build(BuildContext context) => AdWidget(ad: _ad);

  /// google_mobile_ads' medium template renders within 250–350dp.
  @override
  double get preferredHeight => 320;

  @override
  Future<void> dispose() => _ad.dispose();
}

class _RealBannerHandle implements AdMobBannerHandle {
  _RealBannerHandle(this._ad, this.heightDp);

  final BannerAd _ad;

  @override
  final double heightDp;

  @override
  Widget build(BuildContext context) => AdWidget(ad: _ad);

  @override
  Future<void> dispose() => _ad.dispose();
}

class RealAdMobUmpConsent implements AdMobUmpConsent {
  @override
  Future<bool> gatherConsent({
    required AdMobDebugGeography debugGeography,
    required List<String> testDeviceIds,
  }) async {
    final params = ConsentRequestParameters(
      tagForUnderAgeOfConsent: false,
      consentDebugSettings: debugGeography == AdMobDebugGeography.none &&
              testDeviceIds.isEmpty
          ? null
          : ConsentDebugSettings(
              debugGeography: _geography(debugGeography),
              testIdentifiers: testDeviceIds.isEmpty ? null : testDeviceIds,
            ),
    );
    final updated = Completer<void>();
    ConsentInformation.instance.requestConsentInfoUpdate(
      params,
      () => updated.complete(),
      (FormError error) => updated.completeError(
          StateError('UMP consent info update failed: '
              '${error.errorCode} ${error.message}')),
    );
    await updated.future;
    final shown = Completer<void>();
    ConsentForm.loadAndShowConsentFormIfRequired((FormError? error) {
      if (error != null) {
        // A missing/failed form must not be silent: surface it so the
        // caller logs and falls back to house (CR040).
        shown.completeError(StateError(
            'UMP consent form failed: ${error.errorCode} ${error.message}'));
        return;
      }
      shown.complete();
    });
    await shown.future;
    return ConsentInformation.instance.canRequestAds();
  }

  DebugGeography _geography(AdMobDebugGeography g) {
    switch (g) {
      case AdMobDebugGeography.none:
        return DebugGeography.debugGeographyDisabled;
      case AdMobDebugGeography.eea:
        return DebugGeography.debugGeographyEea;
      case AdMobDebugGeography.usState:
        return DebugGeography.debugGeographyRegulatedUsState;
      case AdMobDebugGeography.other:
        return DebugGeography.debugGeographyOther;
    }
  }

  @override
  Future<bool> isPrivacyOptionsRequired() async =>
      await ConsentInformation.instance.getPrivacyOptionsRequirementStatus() ==
      PrivacyOptionsRequirementStatus.required;

  @override
  Future<void> showPrivacyOptionsForm() {
    final dismissed = Completer<void>();
    ConsentForm.showPrivacyOptionsForm((FormError? error) {
      if (error != null) {
        dismissed.completeError(StateError(
            'UMP privacy options form failed: '
            '${error.errorCode} ${error.message}'));
        return;
      }
      dismissed.complete();
    });
    return dismissed.future;
  }
}
