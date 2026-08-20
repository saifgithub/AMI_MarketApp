/// CR122-MOBILE-A/B — the AdSlot render path through the AdGate.
///
/// The load-bearing behaviours proven here (each mutation-proven against the
/// production gate):
///   * plan gating, table-driven over EVERY plan value plus an unknown
///     future plan and the mandate-not-loaded case — only `floor_pass` sees
///     ads, so a new plan cannot silently default to ad-serving;
///   * a 7th (unapproved) placement is refused by the runtime allowlist,
///     with an approved placement as the in-test positive control;
///   * an unreadable/corrupt cap store BLOCKS the ad (never unlimited);
///   * the rendered card carries the SPONSORED label and a working one-tap
///     dismiss; a CR084 upgrade removes the ad without an app restart.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/ads/ad_frequency_caps.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/widgets/ads/ad_slot.dart';
import 'package:ami_trade/widgets/ads/house_ad_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/ad_cap_fakes.dart';

UserMandate mandateWithPlan(String plan) => UserMandate.fromJson({
      'user_id': 'u-test',
      'plan': plan,
      'credit_balance': 10,
      'credit_allowance': 13,
      'room_cost': 9,
    });

/// Always-fill network fake. The gating tests use it so a refusal can ONLY
/// come from the gate — with the real house service, paying plans have no
/// inventory anyway, which would mask a broken plan gate (the exact mutant
/// this arrangement exists to kill).
class AlwaysFillAdsService implements AdsService {
  @override
  String get network => 'always-fill-fake';

  @override
  Future<AdFill?> requestFill(
          AdPlacement placement, HouseAdSignals signals) async =>
      const HouseAdFill(HouseAdCreative(
          slot: HouseAdSlot.genericTrader,
          targetTier: HouseAdTargetTier.trader));
}

/// Mandate stub: preset state, no network, mutable so the upgrade test can
/// flip the plan mid-run the way a CR084 entitlement refresh does.
class StubMandateNotifier extends MandateNotifier {
  StubMandateNotifier(super.ref, UserMandate? m) {
    state = MandateState(mandate: m);
  }

  void setMandate(UserMandate? m) => state = MandateState(mandate: m);

  @override
  Future<void> refresh() async {}
}

class _Harness extends StatelessWidget {
  const _Harness({
    super.key,
    required this.mandate,
    required this.store,
    required this.placement,
    required this.service,
    this.onNotifier,
  });

  final UserMandate? mandate;
  final AdCapStore store;
  final AdPlacement placement;
  final AdsService service;
  final void Function(StubMandateNotifier)? onNotifier;

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      overrides: [
        adsServiceProvider.overrideWithValue(service),
        adCapStoreProvider.overrideWithValue(store),
        mandateNotifierProvider.overrideWith((ref) {
          final n = StubMandateNotifier(ref, mandate);
          onNotifier?.call(n);
          return n;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: SingleChildScrollView(
            child: AdSlot(placement: placement),
          ),
        ),
      ),
    );
  }
}

Future<void> pumpSlot(
  WidgetTester tester, {
  UserMandate? mandate,
  AdCapStore? store,
  AdPlacement placement = AdPlacement.walletAndPlan,
  AdsService? service,
  void Function(StubMandateNotifier)? onNotifier,
}) async {
  // UniqueKey remounts the whole harness on repeat pumps in one test —
  // otherwise the element tree (and the previous ProviderScope's gate/store
  // overrides) would be reused across scenarios.
  await tester.pumpWidget(_Harness(
    key: UniqueKey(),
    mandate: mandate,
    store: store ?? MemoryCapStore(),
    placement: placement,
    service: service ?? AlwaysFillAdsService(),
    onNotifier: onNotifier,
  ));
  // Microtask-scheduled gate request + the async cap reads.
  await tester.pump();
  await tester.pump();
}

void main() {
  group('plan gating — floor_pass only, table-driven', () {
    const table = {
      'floor_pass': true,
      'trader': false,
      'floor_manager': false,
      'trial_trader': false,
      // A plan value this build has never heard of must NOT see ads —
      // the failure mode the CR names: a new plan defaulting to ad-serving.
      'day_pass_2027': false,
    };
    for (final entry in table.entries) {
      testWidgets('plan=${entry.key} → ads=${entry.value}', (tester) async {
        await pumpSlot(tester, mandate: mandateWithPlan(entry.key));
        expect(find.byType(HouseAdCard),
            entry.value ? findsOneWidget : findsNothing);
      });
    }

    testWidgets('mandate not loaded → no ads (fail closed)', (tester) async {
      await pumpSlot(tester, mandate: null);
      expect(find.byType(HouseAdCard), findsNothing);
    });

    testWidgets('CR084 upgrade removes the ad without a restart',
        (tester) async {
      StubMandateNotifier? notifier;
      await pumpSlot(tester,
          mandate: mandateWithPlan('floor_pass'),
          onNotifier: (n) => notifier = n);
      expect(find.byType(HouseAdCard), findsOneWidget);
      notifier!.setMandate(mandateWithPlan('trader'));
      await tester.pump();
      await tester.pump();
      expect(find.byType(HouseAdCard), findsNothing);
    });
  });

  group('placement allowlist', () {
    testWidgets('a 7th placement is refused; the approved one still fills',
        (tester) async {
      // Positive control first: identical conditions, approved placement.
      await pumpSlot(tester,
          mandate: mandateWithPlan('floor_pass'),
          placement: AdPlacement.journalEmptyState);
      expect(find.byType(HouseAdCard), findsOneWidget);

      // Same conditions, a placement outside ads.md:39-44: refused.
      await pumpSlot(tester,
          mandate: mandateWithPlan('floor_pass'),
          placement: const AdPlacement.unapproved(
              'room_sidebar', AdFormat.nativeCard));
      expect(find.byType(HouseAdCard), findsNothing);
    });
  });

  group('cap store failures BLOCK the ad', () {
    testWidgets('throwing store → no ad (positive control fills)',
        (tester) async {
      await pumpSlot(tester, mandate: mandateWithPlan('floor_pass'));
      expect(find.byType(HouseAdCard), findsOneWidget);

      await pumpSlot(tester,
          mandate: mandateWithPlan('floor_pass'),
          store: ThrowingCapStore());
      expect(find.byType(HouseAdCard), findsNothing);
    });

    testWidgets('corrupt counter → no ad', (tester) async {
      await pumpSlot(tester,
          mandate: mandateWithPlan('floor_pass'),
          store:
              MemoryCapStore({'ads.caps.day_impressions': 'not-a-number'}));
      expect(find.byType(HouseAdCard), findsNothing);
    });
  });

  group('ads.md UX rules on the rendered card', () {
    testWidgets('carries the SPONSORED label and a one-tap dismiss',
        (tester) async {
      await pumpSlot(tester, mandate: mandateWithPlan('floor_pass'));
      expect(find.text('SPONSORED'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.close));
      await tester.pump();
      expect(find.byType(HouseAdCard), findsNothing);
    });
  });
}
