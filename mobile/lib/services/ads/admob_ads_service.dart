/// AdMob-backed [AdsService] (CR122-MOBILE-C) — the second facade impl.
///
/// Sits behind the same seam as [HouseAdsService]; the [AdGate] has already
/// run the allowlist, plan gate and persisted caps before this is asked for
/// fill. Two invariants this class owns:
///
///   1. **Consent gates every load** (`ads.md:106-107`). The UMP flow runs
///      before the SDK is initialised or any ad requested; until
///      `canRequestAds` is true, ZERO SDK calls are made and every request
///      is answered from house inventory. A declined GDPR form or ATT
///      prompt still serves ads — the SDK serves them non-personalised off
///      the consent state it stores natively; nothing here re-implements
///      that.
///   2. **Never a blank slot.** No consent, no fill, a load error, a thrown
///      adapter — every failure path answers with house inventory, loudly
///      (CR040). AdMob being dark can cost revenue, never a placement.
///
/// The CCPA "Do Not Sell" preference is read per request (not cached) so a
/// Settings flip applies to the next ad immediately.
library;

import 'package:ami_trade/services/ads/ad_privacy_prefs.dart';
import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:flutter/foundation.dart';

class AdMobAdsService implements AdsService {
  AdMobAdsService({
    required AdMobSetup setup,
    required AdMobSdk sdk,
    required AdMobUmpConsent consent,
    required HouseAdsService house,
    required AdPrivacyPrefs privacyPrefs,
  })  : _setup = setup,
        _sdk = sdk,
        _consent = consent,
        _house = house,
        _privacyPrefs = privacyPrefs {
    debugPrint('CR122 AdsService=admob '
        '(${setup.isTestMode ? 'GOOGLE TEST unit ids' : 'live unit ids'}, '
        '${setup.testDeviceIds.length} test device(s), '
        'consent debug geography: ${setup.consentDebugGeography.name}) — '
        'house inventory remains the fallback for every unfilled request');
  }

  final AdMobSetup _setup;
  final AdMobSdk _sdk;
  final AdMobUmpConsent _consent;
  final HouseAdsService _house;
  final AdPrivacyPrefs _privacyPrefs;

  /// Single-flight consent+init. Non-null only while a gather is running or
  /// after one SUCCEEDED — a failed gather clears it so the next ad request
  /// retries (UMP only re-shows a form when consent is actually required).
  Future<bool>? _ready;

  @override
  String get network => 'admob';

  @override
  Future<AdFill?> requestFill(
      AdPlacement placement, HouseAdSignals signals) async {
    if (!await _ensureReady()) {
      return _house.requestFill(placement, signals);
    }
    try {
      final spec = AdMobRequestSpec(
        adUnitId: placement.format == AdFormat.interstitial
            ? _setup.interstitialAdUnitId
            : _setup.nativeAdUnitId,
        ccpaDoNotSell: await _privacyPrefs.doNotSell(),
      );
      final AdFill? fill = placement.format == AdFormat.interstitial
          ? await _loadInterstitial(spec)
          : await _loadNative(spec);
      if (fill != null) return fill;
      debugPrint(
          'CR122 AdMob: no fill for ${placement.id} — house fallback');
    } catch (e) {
      debugPrint('CR122 AdMob: load failed for ${placement.id} — house '
          'fallback ($e)');
    }
    return _house.requestFill(placement, signals);
  }

  Future<AdFill?> _loadInterstitial(AdMobRequestSpec spec) async {
    final handle = await _sdk.loadInterstitial(spec);
    return handle == null ? null : AdMobInterstitialFill(handle);
  }

  Future<AdFill?> _loadNative(AdMobRequestSpec spec) async {
    final handle = await _sdk.loadNative(spec);
    return handle == null ? null : AdMobNativeFill(handle);
  }

  Future<bool> _ensureReady() {
    return _ready ??= _gatherAndInitialize();
  }

  Future<bool> _gatherAndInitialize() async {
    try {
      final canRequestAds = await _consent.gatherConsent(
        debugGeography: _setup.consentDebugGeography,
        testDeviceIds: _setup.testDeviceIds,
      );
      if (!canRequestAds) {
        debugPrint('CR122 AdMob: consent flow ended without permission to '
            'request ads — serving house inventory only, will retry on the '
            'next ad request');
        _ready = null;
        return false;
      }
      await _sdk.configureAndInitialize(
          AdMobSdkConfigSpec(testDeviceIds: _setup.testDeviceIds));
      return true;
    } catch (e) {
      debugPrint('CR122 AdMob: consent/init failed — serving house '
          'inventory only, will retry on the next ad request ($e)');
      _ready = null;
      return false;
    }
  }
}
