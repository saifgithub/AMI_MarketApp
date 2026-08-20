/// The ONLY file that imports `google_mobile_ads` (CR122-MOBILE-C).
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
    await MobileAds.instance.updateRequestConfiguration(RequestConfiguration(
      testDeviceIds: spec.testDeviceIds,
      maxAdContentRating: spec.maxAdContentRating,
      ageRestrictedTreatment: _ageTreatment(spec.ageTreatment),
    ));
    await MobileAds.instance.initialize();
  }

  AgeRestrictedTreatment _ageTreatment(AdAgeTreatment t) {
    switch (t) {
      case AdAgeTreatment.none:
        return AgeRestrictedTreatment.unspecified;
      case AdAgeTreatment.child:
        return AgeRestrictedTreatment.child;
      case AdAgeTreatment.teen:
        return AgeRestrictedTreatment.teen;
    }
  }

  AdRequest _request(AdMobRequestSpec spec) => AdRequest(
        // CCPA restricted data processing (`ads.md:108`) — the Settings
        // "Do Not Sell" toggle rides every request as AdMob's rdp extra.
        extras: spec.ccpaDoNotSell ? const {'rdp': '1'} : null,
      );

  @override
  Future<AdMobInterstitialHandle?> loadInterstitial(
      AdMobRequestSpec spec) async {
    final completer = Completer<AdMobInterstitialHandle?>();
    await InterstitialAd.load(
      adUnitId: spec.adUnitId,
      request: _request(spec),
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
      request: _request(spec),
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
