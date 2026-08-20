/// AdMob build-time configuration (CR122-MOBILE-C).
///
/// The switch that keeps `google_mobile_ads` dark: everything comes in via
/// `--dart-define`, mirroring `billing_config.dart` (CR084/DEF100), and the
/// store pipelines pass every key with an empty default — so a build with no
/// AdMob environment is byte-for-byte the house-only behaviour of MOBILE-A/B.
/// Defines (forwarded by `scripts/build_testflight.sh`,
/// `scripts/build_playstore.sh`, `scripts/install_iphone.sh` — a consumer
/// exists from day one, the DEF100 lesson):
///
///   ADMOB_MODE                     '' = off (house fill only, the default)
///                                  'test' = Google's RESERVED test ad unit
///                                  ids (published constants, safe anywhere)
///                                  'live' = unit ids from the two defines
///                                  below (Saiful's, never committed)
///   ADMOB_INTERSTITIAL_AD_UNIT_ID  live interstitial unit id
///   ADMOB_NATIVE_AD_UNIT_ID        live native unit id
///   ADMOB_TEST_DEVICE_IDS          comma-separated device ids registered as
///                                  test devices (forces test fill on live
///                                  unit ids — the CR122 testability path)
///   ADMOB_CONSENT_DEBUG_GEOGRAPHY  '' | 'eea' | 'us_state' | 'other' — UMP
///                                  debug geography, forces the EEA consent
///                                  form (or a regulated US state) from any
///                                  real geography on the test devices above
///
/// The AdMob APP ids (`GADApplicationIdentifier` in `ios/Runner/Info.plist`,
/// `com.google.android.gms.ads.APPLICATION_ID` in `AndroidManifest.xml`)
/// cannot ride a dart-define — the native SDK reads them from the manifest
/// before Dart runs. They are committed as GOOGLE'S PUBLISHED SAMPLE app ids
/// (not fabricated, not ours); swapping in Saiful's real ids is a liaison
/// step documented in `CR122_admob_compliance_and_liaison.md`.
///
/// Misconfiguration degrades LOUDLY to house fill (CR040): a recognised-but-
/// incomplete config logs an error naming the missing key — never a blank
/// slot, never a silent no-op that reads as "ads are broken".
library;

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';

/// UMP consent-debug geography, decoupled from the SDK enum so config and
/// tests never import `google_mobile_ads`.
enum AdMobDebugGeography { none, eea, usState, other }

/// The OS the unit-id table keys on, injectable so the pure resolver is
/// testable from the macOS test host.
enum AdMobOs { ios, android, other }

/// A fully resolved AdMob configuration. Existence == AdMob is on; the
/// provider swaps the facade impl on `AdMobConfig.setup != null` and nothing
/// else.
@immutable
class AdMobSetup {
  const AdMobSetup({
    required this.interstitialAdUnitId,
    required this.nativeAdUnitId,
    required this.testDeviceIds,
    required this.consentDebugGeography,
    required this.isTestMode,
  });

  final String interstitialAdUnitId;
  final String nativeAdUnitId;
  final List<String> testDeviceIds;
  final AdMobDebugGeography consentDebugGeography;

  /// True when running on Google's reserved test unit ids.
  final bool isTestMode;
}

class AdMobConfig {
  const AdMobConfig._();

  static const String _mode =
      String.fromEnvironment('ADMOB_MODE', defaultValue: '');
  static const String _liveInterstitialId = String.fromEnvironment(
      'ADMOB_INTERSTITIAL_AD_UNIT_ID',
      defaultValue: '');
  static const String _liveNativeId =
      String.fromEnvironment('ADMOB_NATIVE_AD_UNIT_ID', defaultValue: '');
  static const String _testDeviceIdsRaw =
      String.fromEnvironment('ADMOB_TEST_DEVICE_IDS', defaultValue: '');
  static const String _debugGeographyRaw = String.fromEnvironment(
      'ADMOB_CONSENT_DEBUG_GEOGRAPHY',
      defaultValue: '');

  /// Google's RESERVED test ad unit ids — published in the AdMob "test ads"
  /// guide, identical for every developer, guaranteed to always fill with
  /// test creatives. Committed on purpose: they are Google's constants, not
  /// account material.
  @visibleForTesting
  static const googleTestInterstitialIos =
      'ca-app-pub-3940256099942544/4411468910';
  @visibleForTesting
  static const googleTestInterstitialAndroid =
      'ca-app-pub-3940256099942544/1033173712';
  @visibleForTesting
  static const googleTestNativeIos = 'ca-app-pub-3940256099942544/3986624511';
  @visibleForTesting
  static const googleTestNativeAndroid =
      'ca-app-pub-3940256099942544/2247696110';

  static bool _resolved = false;
  static AdMobSetup? _setup;

  /// The resolved configuration, or null when AdMob is off. Memoised so the
  /// loud misconfiguration log fires once, not per ad request.
  static AdMobSetup? get setup {
    if (!_resolved) {
      _setup = resolve(
        mode: _mode,
        liveInterstitialId: _liveInterstitialId,
        liveNativeId: _liveNativeId,
        testDeviceIdsRaw: _testDeviceIdsRaw,
        debugGeographyRaw: _debugGeographyRaw,
        os: _currentOs,
      );
      _resolved = true;
    }
    return _setup;
  }

  static bool get isConfigured => setup != null;

  static AdMobOs get _currentOs {
    if (Platform.isIOS) return AdMobOs.ios;
    if (Platform.isAndroid) return AdMobOs.android;
    return AdMobOs.other;
  }

  /// Pure resolver — the compile-time constants above cannot be varied from
  /// a test, so the rule table takes its inputs as parameters (the
  /// `BillingConfig.usableKey` pattern).
  @visibleForTesting
  static AdMobSetup? resolve({
    required String mode,
    required String liveInterstitialId,
    required String liveNativeId,
    required String testDeviceIdsRaw,
    required String debugGeographyRaw,
    required AdMobOs os,
  }) {
    if (mode.isEmpty) return null;
    final geography = _parseGeography(debugGeographyRaw);
    final devices = parseTestDeviceIds(testDeviceIdsRaw);
    switch (mode) {
      case 'test':
        if (os == AdMobOs.other) {
          debugPrint('CR122 AdMob: ADMOB_MODE=test on a non-mobile OS — '
              'no Google test unit ids exist here; falling back to house '
              'fill.');
          return null;
        }
        return AdMobSetup(
          interstitialAdUnitId: os == AdMobOs.ios
              ? googleTestInterstitialIos
              : googleTestInterstitialAndroid,
          nativeAdUnitId:
              os == AdMobOs.ios ? googleTestNativeIos : googleTestNativeAndroid,
          testDeviceIds: devices,
          consentDebugGeography: geography,
          isTestMode: true,
        );
      case 'live':
        if (liveInterstitialId.isEmpty || liveNativeId.isEmpty) {
          debugPrint('CR122 AdMob MISCONFIGURED: ADMOB_MODE=live but '
              '${liveInterstitialId.isEmpty ? 'ADMOB_INTERSTITIAL_AD_UNIT_ID' : 'ADMOB_NATIVE_AD_UNIT_ID'} '
              'is empty — falling back to 100% house fill (CR040: loudly, '
              'not blank).');
          return null;
        }
        return AdMobSetup(
          interstitialAdUnitId: liveInterstitialId,
          nativeAdUnitId: liveNativeId,
          testDeviceIds: devices,
          consentDebugGeography: geography,
          isTestMode: false,
        );
      default:
        debugPrint('CR122 AdMob MISCONFIGURED: unknown ADMOB_MODE="$mode" '
            '(expected "", "test" or "live") — falling back to 100% house '
            'fill.');
        return null;
    }
  }

  @visibleForTesting
  static List<String> parseTestDeviceIds(String raw) => raw
      .split(',')
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();

  static AdMobDebugGeography _parseGeography(String raw) {
    switch (raw) {
      case '':
        return AdMobDebugGeography.none;
      case 'eea':
        return AdMobDebugGeography.eea;
      case 'us_state':
        return AdMobDebugGeography.usState;
      case 'other':
        return AdMobDebugGeography.other;
      default:
        debugPrint('CR122 AdMob MISCONFIGURED: unknown '
            'ADMOB_CONSENT_DEBUG_GEOGRAPHY="$raw" (expected "", "eea", '
            '"us_state" or "other") — treating as unset, so consent runs '
            'against the REAL geography.');
        return AdMobDebugGeography.none;
    }
  }

  /// Test-only: clears the memoised resolution.
  @visibleForTesting
  static void resetForTest() {
    _resolved = false;
    _setup = null;
  }
}
