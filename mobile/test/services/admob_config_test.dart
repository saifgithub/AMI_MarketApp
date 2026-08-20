/// CR122-MOBILE-C — the AdMob build-time switch.
///
/// Two guards live here:
///   * the define-off pin: this suite runs with NO dart-defines, so
///     `AdMobConfig.setup` must be null and the facade provider must yield
///     the house service — the store pipelines' behaviour cannot change
///     unless ADMOB_MODE is passed;
///   * the reserved-test-unit-id literals: Google's published constants,
///     pinned verbatim so nobody can quietly swap in a fabricated or
///     account-real id under the 'test' mode.
library;

import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

AdMobSetup? resolve({
  String mode = '',
  String liveInterstitialId = '',
  String liveNativeId = '',
  String testDeviceIdsRaw = '',
  String debugGeographyRaw = '',
  AdMobOs os = AdMobOs.ios,
}) =>
    AdMobConfig.resolve(
      mode: mode,
      liveInterstitialId: liveInterstitialId,
      liveNativeId: liveNativeId,
      testDeviceIdsRaw: testDeviceIdsRaw,
      debugGeographyRaw: debugGeographyRaw,
      os: os,
    );

void main() {
  setUp(AdMobConfig.resetForTest);
  tearDown(AdMobConfig.resetForTest);

  group('define-off pin — no ADMOB_MODE, no AdMob', () {
    test('setup resolves null in the no-define environment', () {
      expect(AdMobConfig.setup, isNull);
      expect(AdMobConfig.isConfigured, isFalse);
    });

    test('the facade provider yields the house service, no AdMob object',
        () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final AdsService svc = container.read(adsServiceProvider);
      expect(svc, isA<HouseAdsService>());
      expect(svc.network, 'house');
    });
  });

  group('mode resolution table', () {
    test('empty mode → off', () {
      expect(resolve(mode: ''), isNull);
    });

    test('unknown mode → off, never a guess', () {
      expect(resolve(mode: 'prod'), isNull);
      expect(resolve(mode: 'TEST'), isNull);
    });

    test("mode=test on iOS → Google's reserved iOS unit ids, verbatim", () {
      final s = resolve(mode: 'test', os: AdMobOs.ios)!;
      expect(s.isTestMode, isTrue);
      // Literal pin: these are Google's PUBLISHED reserved test ids — the
      // sample publisher 3940256099942544. Any other value under 'test'
      // mode is either fabricated or someone's real account material.
      expect(
          s.interstitialAdUnitId, 'ca-app-pub-3940256099942544/4411468910');
      expect(s.nativeAdUnitId, 'ca-app-pub-3940256099942544/3986624511');
    });

    test("mode=test on Android → Google's reserved Android unit ids", () {
      final s = resolve(mode: 'test', os: AdMobOs.android)!;
      expect(s.isTestMode, isTrue);
      expect(
          s.interstitialAdUnitId, 'ca-app-pub-3940256099942544/1033173712');
      expect(s.nativeAdUnitId, 'ca-app-pub-3940256099942544/2247696110');
    });

    test('mode=test on a non-mobile OS → off (no reserved ids exist)', () {
      expect(resolve(mode: 'test', os: AdMobOs.other), isNull);
    });

    test('mode=live with both unit ids → live setup', () {
      final s = resolve(
        mode: 'live',
        liveInterstitialId: 'ca-app-pub-X/int',
        liveNativeId: 'ca-app-pub-X/nat',
      )!;
      expect(s.isTestMode, isFalse);
      expect(s.interstitialAdUnitId, 'ca-app-pub-X/int');
      expect(s.nativeAdUnitId, 'ca-app-pub-X/nat');
    });

    test('mode=live missing either unit id → off (house fill, loudly)', () {
      expect(resolve(mode: 'live', liveNativeId: 'ca-app-pub-X/nat'), isNull);
      expect(resolve(mode: 'live', liveInterstitialId: 'ca-app-pub-X/int'),
          isNull);
    });
  });

  group('auxiliary defines', () {
    test('test device ids parse as a trimmed comma list', () {
      expect(AdMobConfig.parseTestDeviceIds(''), isEmpty);
      expect(AdMobConfig.parseTestDeviceIds('a, b,,c '), ['a', 'b', 'c']);
    });

    test('consent debug geography parses; junk degrades to none', () {
      AdMobSetup geo(String raw) =>
          resolve(mode: 'test', debugGeographyRaw: raw)!;
      expect(geo('').consentDebugGeography, AdMobDebugGeography.none);
      expect(geo('eea').consentDebugGeography, AdMobDebugGeography.eea);
      expect(
          geo('us_state').consentDebugGeography, AdMobDebugGeography.usState);
      expect(geo('other').consentDebugGeography, AdMobDebugGeography.other);
      expect(geo('mars').consentDebugGeography, AdMobDebugGeography.none);
    });

    test('test device ids ride into the setup', () {
      final s = resolve(mode: 'test', testDeviceIdsRaw: 'dev1,dev2')!;
      expect(s.testDeviceIds, ['dev1', 'dev2']);
    });
  });
}
