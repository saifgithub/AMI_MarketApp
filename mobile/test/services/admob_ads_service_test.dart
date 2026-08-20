/// CR122-MOBILE-C — the AdMob facade impl behind the seam fakes.
///
/// The two invariants the service owns, proven against fakes so no platform
/// channel is ever touched:
///   * consent gates every load — until the UMP flow says `canRequestAds`,
///     ZERO SDK calls happen and every request fills house; a failed or
///     denied gather retries on the next request;
///   * never a blank slot — no-fill, a throwing adapter and a throwing
///     consent flow all answer with house inventory.
/// Plus the compliance riders: the SDK config spec carries the
/// `ad_content_policy.dart` constants, and the CCPA "Do Not Sell" pref is
/// read per request so a Settings flip applies to the very next ad.
library;

import 'package:ami_trade/services/ads/ad_content_policy.dart';
import 'package:ami_trade/services/ads/ad_privacy_prefs.dart';
import 'package:ami_trade/services/ads/admob_ads_service.dart';
import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/ad_cap_fakes.dart';

const _signals = HouseAdSignals(effectivePlan: 'floor_pass');

const _setup = AdMobSetup(
  interstitialAdUnitId: 'unit-interstitial',
  nativeAdUnitId: 'unit-native',
  testDeviceIds: ['dev-a', 'dev-b'],
  consentDebugGeography: AdMobDebugGeography.eea,
  isTestMode: true,
);

class FakeInterstitialHandle implements AdMobInterstitialHandle {
  int shows = 0;

  @override
  Future<void> show() async => shows++;
}

class FakeNativeHandle implements AdMobNativeHandle {
  bool disposed = false;

  @override
  Widget build(BuildContext context) => const SizedBox(height: 10);

  @override
  double get preferredHeight => 10;

  @override
  Future<void> dispose() async => disposed = true;
}

class FakeSdk implements AdMobSdk {
  int initCalls = 0;
  AdMobSdkConfigSpec? lastConfig;
  final interstitialSpecs = <AdMobRequestSpec>[];
  final nativeSpecs = <AdMobRequestSpec>[];
  bool fill = true;
  bool throwOnLoad = false;

  int get loadCalls => interstitialSpecs.length + nativeSpecs.length;

  @override
  Future<void> configureAndInitialize(AdMobSdkConfigSpec spec) async {
    initCalls++;
    lastConfig = spec;
  }

  @override
  Future<AdMobInterstitialHandle?> loadInterstitial(
      AdMobRequestSpec spec) async {
    interstitialSpecs.add(spec);
    if (throwOnLoad) throw StateError('adapter blew up');
    return fill ? FakeInterstitialHandle() : null;
  }

  @override
  Future<AdMobNativeHandle?> loadNative(AdMobRequestSpec spec) async {
    nativeSpecs.add(spec);
    if (throwOnLoad) throw StateError('adapter blew up');
    return fill ? FakeNativeHandle() : null;
  }
}

class FakeConsent implements AdMobUmpConsent {
  FakeConsent({this.canRequestAds = true, this.throwOnGather = false});

  bool canRequestAds;
  bool throwOnGather;
  int gathers = 0;
  AdMobDebugGeography? lastGeography;
  List<String>? lastDevices;

  @override
  Future<bool> gatherConsent({
    required AdMobDebugGeography debugGeography,
    required List<String> testDeviceIds,
  }) async {
    gathers++;
    lastGeography = debugGeography;
    lastDevices = testDeviceIds;
    if (throwOnGather) throw StateError('UMP unreachable');
    return canRequestAds;
  }

  @override
  Future<bool> isPrivacyOptionsRequired() async => false;

  @override
  Future<void> showPrivacyOptionsForm() async {}
}

AdMobAdsService service({
  required FakeSdk sdk,
  required FakeConsent consent,
  AdPrivacyPrefs? prefs,
}) =>
    AdMobAdsService(
      setup: _setup,
      sdk: sdk,
      consent: consent,
      house: HouseAdsService.asFallback(),
      privacyPrefs: prefs ?? AdPrivacyPrefs(MemoryCapStore()),
    );

void main() {
  group('consent gates every load', () {
    test('denied consent → zero SDK calls, house fill, retried next request',
        () async {
      final sdk = FakeSdk();
      final consent = FakeConsent(canRequestAds: false);
      final svc = service(sdk: sdk, consent: consent);

      final fill =
          await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(fill, isA<HouseAdFill>());
      expect(sdk.initCalls, 0);
      expect(sdk.loadCalls, 0);

      // The user granting consent later must not be locked out by a cached
      // refusal: the next request runs the gather again.
      consent.canRequestAds = true;
      final second =
          await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(consent.gathers, 2);
      expect(second, isA<AdMobNativeFill>());
    });

    test('a throwing consent flow → house fill, zero SDK calls, retried',
        () async {
      final sdk = FakeSdk();
      final consent = FakeConsent(throwOnGather: true);
      final svc = service(sdk: sdk, consent: consent);

      final fill =
          await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(fill, isA<HouseAdFill>());
      expect(sdk.initCalls, 0);
      expect(sdk.loadCalls, 0);

      consent.throwOnGather = false;
      await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(consent.gathers, 2);
      expect(sdk.initCalls, 1);
    });

    test('granted consent → init once, not per request', () async {
      final sdk = FakeSdk();
      final consent = FakeConsent();
      final svc = service(sdk: sdk, consent: consent);

      await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      await svc.requestFill(AdPlacement.journalEmptyState, _signals);
      expect(consent.gathers, 1);
      expect(sdk.initCalls, 1);
      expect(sdk.loadCalls, 2);
    });

    test('the gather receives the setup debug geography + test devices',
        () async {
      final consent = FakeConsent();
      await service(sdk: FakeSdk(), consent: consent)
          .requestFill(AdPlacement.walletAndPlan, _signals);
      expect(consent.lastGeography, AdMobDebugGeography.eea);
      expect(consent.lastDevices, ['dev-a', 'dev-b']);
    });
  });

  group('unit id + format routing', () {
    test('interstitial placements load the interstitial unit id', () async {
      final sdk = FakeSdk();
      final fill = await service(sdk: sdk, consent: FakeConsent())
          .requestFill(AdPlacement.postLessonInterstitial, _signals);
      expect(fill, isA<AdMobInterstitialFill>());
      expect(sdk.interstitialSpecs.single.adUnitId, 'unit-interstitial');
      expect(sdk.nativeSpecs, isEmpty);
    });

    test('native placements load the native unit id', () async {
      final sdk = FakeSdk();
      final fill = await service(sdk: sdk, consent: FakeConsent())
          .requestFill(AdPlacement.academyHubBottom, _signals);
      expect(fill, isA<AdMobNativeFill>());
      expect(sdk.nativeSpecs.single.adUnitId, 'unit-native');
      expect(sdk.interstitialSpecs, isEmpty);
    });
  });

  group('never a blank slot — house answers every failure', () {
    test('no fill from the network → house inventory', () async {
      final sdk = FakeSdk()..fill = false;
      final fill = await service(sdk: sdk, consent: FakeConsent())
          .requestFill(AdPlacement.walletAndPlan, _signals);
      expect(fill, isA<HouseAdFill>());
    });

    test('a throwing adapter → house inventory', () async {
      final sdk = FakeSdk()..throwOnLoad = true;
      final fill = await service(sdk: sdk, consent: FakeConsent())
          .requestFill(AdPlacement.walletAndPlan, _signals);
      expect(fill, isA<HouseAdFill>());
    });
  });

  group('compliance riders on every spec', () {
    test('the SDK config spec carries the ad content policy', () async {
      final sdk = FakeSdk();
      await service(sdk: sdk, consent: FakeConsent())
          .requestFill(AdPlacement.walletAndPlan, _signals);
      final config = sdk.lastConfig!;
      expect(config.maxAdContentRating, AdContentPolicy.maxAdContentRating);
      expect(config.ageTreatment, AdAgeTreatment.none);
      expect(config.testDeviceIds, ['dev-a', 'dev-b']);
    });

    test('CCPA Do-Not-Sell is read per request, not cached', () async {
      final sdk = FakeSdk();
      final store = MemoryCapStore();
      final svc = service(
          sdk: sdk,
          consent: FakeConsent(),
          prefs: AdPrivacyPrefs(store));

      await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(sdk.nativeSpecs.last.ccpaDoNotSell, isFalse);

      store.map[AdPrivacyPrefs.doNotSellKey] = 'true';
      await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(sdk.nativeSpecs.last.ccpaDoNotSell, isTrue);
    });

    test('an unreadable privacy store fails TOWARD privacy (rdp on)',
        () async {
      final sdk = FakeSdk();
      final svc = service(
          sdk: sdk,
          consent: FakeConsent(),
          prefs: AdPrivacyPrefs(ThrowingCapStore()));
      await svc.requestFill(AdPlacement.walletAndPlan, _signals);
      expect(sdk.nativeSpecs.single.ccpaDoNotSell, isTrue);
    });
  });
}
