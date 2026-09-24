/// AdMob build-time configuration (CR122-MOBILE-C, channel gate CR225).
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
///                                  below (Saiful's, never committed) —
///                                  ONLY HONOURED on AMI_RELEASE_CHANNEL=
///                                  'production' (see below)
///   ADMOB_INTERSTITIAL_AD_UNIT_ID  live interstitial unit id
///   ADMOB_NATIVE_AD_UNIT_ID        live native unit id
///   ADMOB_TEST_DEVICE_IDS          comma-separated device ids registered as
///                                  test devices (forces test fill on live
///                                  unit ids — the CR122 testability path)
///   ADMOB_CONSENT_DEBUG_GEOGRAPHY  '' | 'eea' | 'us_state' | 'other' — UMP
///                                  debug geography, forces the EEA consent
///                                  form (or a regulated US state) from any
///                                  real geography on the test devices above
///   AMI_RELEASE_CHANNEL            '' (dev/unknown) | 'internal' |
///                                  'production' — set STRUCTURALLY by the
///                                  build scripts from --internal-only /
///                                  --production (never hand-typed), the same
///                                  flags that already gate the RevenueCat
///                                  Test-Store-key and CR109 games checks.
///
/// **CR225 — internal builds cannot serve real ad units, structurally.**
/// Saiful's ruling (2026-09-24): TestFlight Internal / Play Internal must
/// serve Google's OFFICIAL AdMob test unit IDs, and real unit IDs may only
/// reach a production build. A misconfigured `ADMOB_MODE=live` on an
/// operator's shell (copy-paste from a previous production build, forgetting
/// to unset a local env var) must not be able to leak real ad units into an
/// internal build — an instruction ("remember to unset it") is not a control
/// (CLAUDE.md). So [resolve] takes the channel as an input, not just the
/// mode: `mode=live` is honoured ONLY when `channel == production`; on any
/// other channel (including the empty/dev default, which is the more
/// conservative reading — an unknown channel must not be treated as
/// permission to ship real ad units) it is downgraded to Google's reserved
/// test ids, loudly (never a blank slot — CR040), rather than refused to
/// house fill. That keeps CR122's original guarantee — "no ADMOB_MODE define
/// ⇒ house fill, byte-identical to pre-CR122" — intact, because the
/// downgrade only fires when a caller explicitly asked for `live`.
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

/// CR225 — the build flavour, read from `AMI_RELEASE_CHANNEL`. [unknown] is
/// the dev/unset default and is treated as the MORE conservative of the two
/// named channels wherever the two disagree (i.e. same as [internal]) — an
/// absent channel is never read as permission to ship real ad units.
enum AdMobReleaseChannel { unknown, internal_, production }

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
  static const String _releaseChannelRaw =
      String.fromEnvironment('AMI_RELEASE_CHANNEL', defaultValue: '');

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
        channel: _parseChannel(_releaseChannelRaw),
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
    AdMobReleaseChannel channel = AdMobReleaseChannel.unknown,
  }) {
    if (mode.isEmpty) return null;
    final geography = _parseGeography(debugGeographyRaw);
    final devices = parseTestDeviceIds(testDeviceIdsRaw);
    switch (mode) {
      case 'test':
        return _testSetup(os, devices, geography, reason: 'ADMOB_MODE=test');
      case 'live':
        // CR225 — Saiful's ruling (2026-09-24): only a PRODUCTION build may
        // serve real ad units. `internal` and `unknown` (the conservative
        // default — see AdMobReleaseChannel doc) both downgrade a `live`
        // request to Google's reserved test ids rather than refusing to
        // house fill: the operator asked for AdMob to be ON, and an
        // internal tester seeing a real ad served against a real account
        // is the actual policy risk this exists to prevent (accidental
        // real-money click fraud from the team's own devices), not a
        // missing placement. This is structural, not a comment: the
        // decision lives here, not in a build-script instruction an
        // operator has to remember to check.
        if (channel != AdMobReleaseChannel.production) {
          debugPrint('CR225 AdMob: ADMOB_MODE=live but AMI_RELEASE_CHANNEL='
              '"${_channelLabel(channel)}" (not production) — serving '
              "Google's reserved TEST unit ids instead. Real ad units may "
              'only reach a production build.');
          return _testSetup(os, devices, geography,
              reason: 'ADMOB_MODE=live downgraded on a non-production '
                  'channel');
        }
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

  /// Google's reserved test unit ids for [os], or null (house fill) on a
  /// non-mobile OS — shared by the explicit `mode=test` path and the CR225
  /// live→test channel downgrade so the two can never drift apart.
  static AdMobSetup? _testSetup(
    AdMobOs os,
    List<String> devices,
    AdMobDebugGeography geography, {
    required String reason,
  }) {
    if (os == AdMobOs.other) {
      debugPrint('CR122 AdMob: $reason on a non-mobile OS — no Google test '
          'unit ids exist here; falling back to house fill.');
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
  }

  static String _channelLabel(AdMobReleaseChannel c) => switch (c) {
        AdMobReleaseChannel.unknown => '' '(unset)',
        AdMobReleaseChannel.internal_ => 'internal',
        AdMobReleaseChannel.production => 'production',
      };

  @visibleForTesting
  static AdMobReleaseChannel parseChannel(String raw) => _parseChannel(raw);

  static AdMobReleaseChannel _parseChannel(String raw) {
    switch (raw) {
      case '':
        return AdMobReleaseChannel.unknown;
      case 'internal':
        return AdMobReleaseChannel.internal_;
      case 'production':
        return AdMobReleaseChannel.production;
      default:
        debugPrint('CR225 AdMob MISCONFIGURED: unknown '
            'AMI_RELEASE_CHANNEL="$raw" (expected "", "internal" or '
            '"production") — treating as unset, the conservative default '
            '(no live ad units).');
        return AdMobReleaseChannel.unknown;
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
