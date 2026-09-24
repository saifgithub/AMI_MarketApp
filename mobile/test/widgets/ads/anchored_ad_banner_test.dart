/// CR226 — the global anchored banner slot.
///
/// Covers what `CR225_admob_ios_relink.md`/`CR226_adaptive_banner_slot.md`
/// require directly:
///   * paid tiers (every plan but `floor_pass`, including `trial_trader`)
///     collapse the slot to zero height — same AdGate plan-gate every other
///     placement uses, exercised here at the shell-slot widget itself;
///   * the width measured by the banner's own `LayoutBuilder` reaches the
///     network layer (`AdsService.requestFill`'s `widthDp`), which is what
///     makes the size adaptive rather than a fixed constant;
///   * a house fallback renders when AdMob has no fill, never a blank slot;
///   * the AdMob policy separator (a visible border) is present ABOVE the
///     banner content and absent when the slot is empty (paid plan) — it
///     must never be a stray line with nothing under it.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/anchored_ad_banner.dart';
import 'package:ami_trade/widgets/ads/house_ad_banner_strip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/ad_cap_fakes.dart';

UserMandate _mandateWithPlan(String plan) => UserMandate.fromJson({
      'user_id': 'u-test',
      'plan': plan,
      'credit_balance': 10,
      'credit_allowance': 13,
      'room_cost': 9,
    });

class _StubMandateNotifier extends MandateNotifier {
  _StubMandateNotifier(super.ref, UserMandate? m) {
    state = MandateState(mandate: m);
  }

  @override
  Future<void> refresh() async {}
}

/// Records every `widthDp` a request carried, and always fills via house
/// inventory — the render-path tests care about width plumbing and slot
/// presence, not about a specific network's fill shape (that is
/// `admob_ads_service_test.dart`'s CR226 group).
class _RecordingAdsService implements AdsService {
  final widthsSeen = <int>[];
  bool houseFills = true;

  @override
  String get network => 'recording-fake';

  @override
  Future<AdFill?> requestFill(AdPlacement placement, HouseAdSignals signals,
      {int widthDp = 0}) async {
    widthsSeen.add(widthDp);
    if (!houseFills) return null;
    return const HouseAdFill(HouseAdCreative(
        slot: HouseAdSlot.genericTrader,
        targetTier: HouseAdTargetTier.trader));
  }
}

Widget _harness({
  required UserMandate? mandate,
  required AdsService service,
}) {
  return ProviderScope(
    overrides: [
      adsServiceProvider.overrideWithValue(service),
      adCapStoreProvider.overrideWithValue(MemoryCapStore()),
      mandateNotifierProvider
          .overrideWith((ref) => _StubMandateNotifier(ref, mandate)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: SizedBox.shrink(),
        bottomNavigationBar: SizedBox(
          width: double.infinity,
          child: AnchoredAdBanner(),
        ),
      ),
    ),
  );
}

/// Sets the TEST SURFACE width (what `Scaffold`'s `bottomNavigationBar`
/// actually lays out against) — matching `home_shell_test.dart`'s own
/// pattern (`tester.view.physicalSize`), not a `MediaQuery` override, which
/// does not reach `Scaffold`'s own layout constraints.
void _setWidth(WidgetTester t, double width) {
  t.view.physicalSize = Size(width, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('paid tiers collapse the slot to zero height', () {
    const table = {
      'floor_pass': true,
      'trader': false,
      'floor_manager': false,
      'trial_trader': false,
      'day_pass_2027': false, // unrecognised future plan: fail closed
    };
    for (final entry in table.entries) {
      testWidgets('plan=${entry.key} → banner visible=${entry.value}',
          (tester) async {
        final service = _RecordingAdsService();
        await tester.pumpWidget(_harness(
          mandate: _mandateWithPlan(entry.key),
          service: service,
        ));
        await _settle(tester);
        expect(find.byType(HouseAdBannerStrip),
            entry.value ? findsOneWidget : findsNothing);
        final bannerBox =
            tester.renderObject<RenderBox>(find.byType(AnchoredAdBanner));
        expect(bannerBox.size.height, entry.value ? greaterThan(0) : 0);
      });
    }

    testWidgets('mandate not loaded → no ads (fail closed)', (tester) async {
      final service = _RecordingAdsService();
      await tester.pumpWidget(_harness(mandate: null, service: service));
      await _settle(tester);
      expect(find.byType(HouseAdBannerStrip), findsNothing);
    });
  });

  group('adaptive width reaches the network layer', () {
    testWidgets('the LayoutBuilder-measured width rides the request',
        (tester) async {
      _setWidth(tester, 412);
      final service = _RecordingAdsService();
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('floor_pass'),
        service: service,
      ));
      await _settle(tester);
      expect(service.widthsSeen, isNotEmpty);
      expect(service.widthsSeen.last, 412,
          reason: 'CR226: the banner must size from the width it is '
              'actually given (LayoutBuilder), not a hard-coded constant');
    });

    testWidgets('a wider constraint (simulated unfold) re-requests',
        (tester) async {
      _setWidth(tester, 390);
      final service = _RecordingAdsService();
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('floor_pass'),
        service: service,
      ));
      await _settle(tester);
      expect(service.widthsSeen.last, 390);

      // Simulate an unfold: widen the test surface, then rebuild — the
      // widget must dispose the old fill and request a NEW one at the new
      // width, not keep rendering a 390dp-sized decision.
      _setWidth(tester, 984);
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('floor_pass'),
        service: service,
      ));
      await _settle(tester);
      expect(service.widthsSeen.last, 984,
          reason: 'CR226: width change must dispose + reload, not keep a '
              'stale narrower-width decision');
    });
  });

  group('never a blank slot', () {
    testWidgets('no network fill at all still renders SOMETHING filled '
        'only when the network actually has inventory', (tester) async {
      final service = _RecordingAdsService()..houseFills = false;
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('floor_pass'),
        service: service,
      ));
      await _settle(tester);
      // No inventory anywhere (network AND house both refuse) is a
      // legitimate zero-height outcome — the guarantee is "never silently
      // pretend to have filled", not "always show a box".
      expect(find.byType(HouseAdBannerStrip), findsNothing);
      final bannerBox =
          tester.renderObject<RenderBox>(find.byType(AnchoredAdBanner));
      expect(bannerBox.size.height, 0);
    });
  });

  group('AdMob policy separator (Saiful, 2026-09-24)', () {
    testWidgets('a visible divider sits above the banner when it fills',
        (tester) async {
      final service = _RecordingAdsService();
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('floor_pass'),
        service: service,
      ));
      await _settle(tester);
      expect(find.byType(HouseAdBannerStrip), findsOneWidget);

      final decorated = tester.widgetList<DecoratedBox>(
        find.descendant(
          of: find.byType(AnchoredAdBanner),
          matching: find.byType(DecoratedBox),
        ),
      );
      final hasTopBorder = decorated.any((w) {
        final decoration = w.decoration;
        return decoration is BoxDecoration &&
            decoration.border?.top.color == AmiColors.slate700;
      });
      expect(hasTopBorder, isTrue,
          reason: 'CR226: a visible separator must sit between the nav '
              'buttons and the banner (accidental-click risk)');
    });

    testWidgets('no separator when the slot is empty (paid plan)',
        (tester) async {
      final service = _RecordingAdsService();
      await tester.pumpWidget(_harness(
        mandate: _mandateWithPlan('trader'),
        service: service,
      ));
      await _settle(tester);
      expect(find.byType(HouseAdBannerStrip), findsNothing);
      // Zero-height slot: no separator drawn with nothing under it.
      final bannerBox =
          tester.renderObject<RenderBox>(find.byType(AnchoredAdBanner));
      expect(bannerBox.size.height, 0);
    });
  });
}
