/// CR122-MOBILE-C — the AdMob fills render through the SAME chrome contract
/// as house inventory.
///
///   * an [AdMobNativeFill] in an approved slot renders inside
///     [AdMobNativeCard]: SPONSORED label, one-tap dismiss, and dismissal
///     DISPOSES the underlying platform ad (the handle owns SDK memory);
///   * an [AdMobInterstitialFill] from the post-lesson entry point presents
///     via the handle's own `show()` — no house page is pushed, and the
///     impression is recorded.
///
/// Everything runs on seam fakes; no platform channel, no SDK import.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/ads/ad_frequency_caps.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/widgets/ads/ad_slot.dart';
import 'package:ami_trade/widgets/ads/admob_native_card.dart';
import 'package:ami_trade/widgets/ads/house_ad_interstitial.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/ad_cap_fakes.dart';

UserMandate _floorPass() => UserMandate.fromJson({
      'user_id': 'u-test',
      'plan': 'floor_pass',
      'credit_balance': 10,
      'credit_allowance': 13,
      'room_cost': 9,
    });

class FakeNativeHandle implements AdMobNativeHandle {
  bool disposed = false;

  @override
  Widget build(BuildContext context) =>
      const ColoredBox(color: Colors.purple, key: Key('sdk-native-template'));

  @override
  double get preferredHeight => 40;

  @override
  Future<void> dispose() async => disposed = true;
}

class FakeInterstitialHandle implements AdMobInterstitialHandle {
  int shows = 0;

  @override
  Future<void> show() async => shows++;
}

/// Facade fake answering AdMob fills, as if consent passed and the network
/// filled — the render layer under test must not care how.
class AdMobFillService implements AdsService {
  AdMobFillService({this.native, this.interstitial});

  final FakeNativeHandle? native;
  final FakeInterstitialHandle? interstitial;

  @override
  String get network => 'admob-fake';

  @override
  Future<AdFill?> requestFill(
      AdPlacement placement, HouseAdSignals signals) async {
    if (placement.format == AdFormat.interstitial) {
      return interstitial == null
          ? null
          : AdMobInterstitialFill(interstitial!);
    }
    return native == null ? null : AdMobNativeFill(native!);
  }
}

class StubMandateNotifier extends MandateNotifier {
  StubMandateNotifier(super.ref, UserMandate? m) {
    state = MandateState(mandate: m);
  }

  @override
  Future<void> refresh() async {}
}

Widget _scope({
  required AdsService service,
  required AdCapStore store,
  required Widget child,
}) {
  return ProviderScope(
    overrides: [
      adsServiceProvider.overrideWithValue(service),
      adCapStoreProvider.overrideWithValue(store),
      mandateNotifierProvider
          .overrideWith((ref) => StubMandateNotifier(ref, _floorPass())),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

void main() {
  testWidgets(
      'an AdMob native fill renders in the labelled card; dismiss disposes',
      (tester) async {
    final handle = FakeNativeHandle();
    await tester.pumpWidget(_scope(
      service: AdMobFillService(native: handle),
      store: MemoryCapStore(),
      child: const Scaffold(
        body: SingleChildScrollView(
          child: AdSlot(placement: AdPlacement.walletAndPlan),
        ),
      ),
    ));
    await tester.pump();
    await tester.pump();

    expect(find.byType(AdMobNativeCard), findsOneWidget);
    expect(find.byKey(const Key('sdk-native-template')), findsOneWidget);
    expect(find.text('SPONSORED'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.close));
    await tester.pump();
    expect(find.byType(AdMobNativeCard), findsNothing);
    expect(handle.disposed, isTrue,
        reason: 'dismiss must release the platform ad, not leak it');
  });

  testWidgets(
      'an AdMob interstitial fill shows via the SDK handle, no house page',
      (tester) async {
    final handle = FakeInterstitialHandle();
    final store = MemoryCapStore({
      // One lesson short: the entry point itself records the 5th.
      'ads.caps.lessons_since_interstitial': '4',
    });
    await tester.pumpWidget(_scope(
      service: AdMobFillService(interstitial: handle),
      store: store,
      child: Scaffold(
        body: Consumer(
          builder: (context, ref, _) => TextButton(
            onPressed: () => maybeShowPostLessonInterstitial(context, ref),
            child: const Text('finish lesson'),
          ),
        ),
      ),
    ));

    await tester.tap(find.text('finish lesson'));
    await tester.pumpAndSettle();

    expect(handle.shows, 1);
    expect(find.byType(HouseAdInterstitialPage), findsNothing);
    expect(store.map['ads.caps.session_interstitials'], '1',
        reason: 'the SDK-shown interstitial must still count against caps');
  });
}
