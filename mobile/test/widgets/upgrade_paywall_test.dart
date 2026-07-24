/// CR084 — the live RevenueCat paywall + purchase flow.
///
/// The load-bearing behaviours proven here:
///   * The offering renders with **RC prices** (never hard-coded) and a BUY per
///     product.
///   * A completed purchase **re-reads entitlement from the backend** (the
///     mandate notifier's refresh), NOT the SDK cache, then unlocks (onPurchased).
///   * user-cancel / store-error do NOT unlock and do NOT refresh.
///   * Restore refreshes from the backend (App Store requirement path).
///   * An unconfigured store (DEF100) degrades to info — NO dead buy button.
///
/// The RC SDK is stubbed via [purchaseServiceProvider], so no platform channel
/// is ever touched; the backend read is stubbed via a spy [MandateNotifier].
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

// ── Fakes ────────────────────────────────────────────────────────────────

class FakePurchaseService implements PurchaseService {
  FakePurchaseService({
    this.offering,
    this.buyOutcome = PurchaseOutcome.success,
    this.restoreOutcome = PurchaseOutcome.success,
    this.configured = true,
  });

  PaywallOffering? offering;
  PurchaseOutcome buyOutcome;
  PurchaseOutcome restoreOutcome;
  bool configured;

  int buyCount = 0;
  int restoreCount = 0;
  PaywallPackage? lastBought;

  @override
  bool get isConfigured => configured;

  @override
  Future<PaywallOffering?> fetchOffering() async => offering;

  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async {
    buyCount++;
    lastBought = pkg;
    return buyOutcome;
  }

  @override
  Future<PurchaseOutcome> restore() async {
    restoreCount++;
    return restoreOutcome;
  }
}

/// Spy on the backend entitlement re-read. `refresh()` is a no-op counter, so
/// no network / SharedPreferences plugin is touched in the widget tree.
class SpyMandateNotifier extends MandateNotifier {
  SpyMandateNotifier(super.ref);
  int refreshCount = 0;

  @override
  Future<void> refresh() async {
    refreshCount++;
  }
}

// ── Builders ─────────────────────────────────────────────────────────────

PaywallPackage _pkg(String id, String price) {
  final c = PaywallPackage.classify(id);
  return PaywallPackage(
    productId: id,
    priceString: price,
    storeTitle: id,
    kind: c.kind,
    tier: c.tier,
    interval: c.interval,
    packCredits: c.credits,
    raw: Object(),
  );
}

PaywallOffering _fullOffering() => PaywallOffering(
      identifier: 'default',
      packages: [
        _pkg(PaywallProductIds.traderMonthly, '\$14.99'),
        _pkg(PaywallProductIds.traderAnnual, '\$129.00'),
        _pkg(PaywallProductIds.floorManagerMonthly, '\$34.99'),
        _pkg(PaywallProductIds.floorManagerAnnual, '\$299.00'),
        _pkg(PaywallProductIds.creditsStarter, '\$4.99'),
        _pkg(PaywallProductIds.creditsStandard, '\$19.99'),
        _pkg(PaywallProductIds.creditsPower, '\$49.99'),
      ],
    );

class _Harness extends StatelessWidget {
  const _Harness({
    required this.service,
    required this.onSpy,
    this.onPurchased,
  });

  final PurchaseService service;
  final void Function(SpyMandateNotifier) onSpy;
  final VoidCallback? onPurchased;

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      overrides: [
        purchaseServiceProvider.overrideWithValue(service),
        mandateNotifierProvider.overrideWith((ref) {
          final spy = SpyMandateNotifier(ref);
          onSpy(spy);
          return spy;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: SingleChildScrollView(
            child: UpgradePaywall(
              resetDateLabel: '2026-08-01',
              onPurchased: onPurchased,
            ),
          ),
        ),
      ),
    );
  }
}

void main() {
  testWidgets('offering renders every product with its RC price + a BUY each',
      (t) async {
    await t.pumpWidget(_Harness(
      service: FakePurchaseService(offering: _fullOffering()),
      onSpy: (_) {},
    ));
    await t.pumpAndSettle();

    // Plan names + credit-pack labels.
    expect(find.text('Trader'), findsOneWidget);
    expect(find.text('Floor Manager'), findsOneWidget);
    expect(find.text('+60 credits'), findsOneWidget);
    expect(find.text('+300 credits'), findsOneWidget);
    expect(find.text('+850 credits'), findsOneWidget);

    // Prices come straight from the offering (never hard-coded).
    expect(find.text('\$14.99'), findsOneWidget);
    expect(find.text('\$129.00'), findsOneWidget);
    expect(find.text('\$34.99'), findsOneWidget);
    expect(find.text('\$299.00'), findsOneWidget);
    expect(find.text('\$4.99'), findsOneWidget);

    // One BUY per purchasable (4 subs + 3 packs).
    expect(find.widgetWithText(ElevatedButton, 'BUY'), findsNWidgets(7));
    // Restore is always offered.
    expect(find.text('Restore purchases'), findsOneWidget);
  });

  testWidgets('unconfigured store degrades to info — NO buy button (DEF100)',
      (t) async {
    await t.pumpWidget(_Harness(
      service: FakePurchaseService(offering: null, configured: false),
      onSpy: (_) {},
    ));
    await t.pumpAndSettle();

    expect(find.text("Upgrades aren't available yet"), findsOneWidget);
    expect(find.widgetWithText(ElevatedButton, 'BUY'), findsNothing);
    // Restore still present (degrades to a message if truly unavailable).
    expect(find.text('Restore purchases'), findsOneWidget);
  });

  testWidgets('successful purchase refreshes from backend and unlocks',
      (t) async {
    SpyMandateNotifier? spy;
    var unlocked = false;
    await t.pumpWidget(_Harness(
      service: FakePurchaseService(
        offering: PaywallOffering(
          identifier: 'd',
          packages: [_pkg(PaywallProductIds.traderMonthly, '\$14.99')],
        ),
        buyOutcome: PurchaseOutcome.success,
      ),
      onSpy: (s) => spy = s,
      onPurchased: () => unlocked = true,
    ));
    await t.pumpAndSettle();

    await t.tap(find.widgetWithText(ElevatedButton, 'BUY'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 800));

    expect(unlocked, isTrue, reason: 'onPurchased must fire to unlock');
    expect(spy, isNotNull);
    expect(spy!.refreshCount, 1,
        reason: 'entitlement re-read from backend, not SDK cache');
    expect(find.textContaining("You're upgraded"), findsOneWidget);

    await t.pump(const Duration(seconds: 5)); // drain snackbar timer
  });

  testWidgets('user cancel does not unlock and does not refresh', (t) async {
    SpyMandateNotifier? spy;
    var unlocked = false;
    await t.pumpWidget(_Harness(
      service: FakePurchaseService(
        offering: PaywallOffering(
          identifier: 'd',
          packages: [_pkg(PaywallProductIds.traderMonthly, '\$14.99')],
        ),
        buyOutcome: PurchaseOutcome.cancelled,
      ),
      onSpy: (s) => spy = s,
      onPurchased: () => unlocked = true,
    ));
    await t.pumpAndSettle();

    await t.tap(find.widgetWithText(ElevatedButton, 'BUY'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 800));

    expect(unlocked, isFalse);
    // Notifier may never even be built on a cancel; refresh must not run.
    expect(spy?.refreshCount ?? 0, 0);
    expect(find.textContaining("You're upgraded"), findsNothing);
  });

  testWidgets('store error shows a failure message and does not unlock',
      (t) async {
    SpyMandateNotifier? spy;
    var unlocked = false;
    await t.pumpWidget(_Harness(
      service: FakePurchaseService(
        offering: PaywallOffering(
          identifier: 'd',
          packages: [_pkg(PaywallProductIds.traderMonthly, '\$14.99')],
        ),
        buyOutcome: const PurchaseOutcome(PurchaseStatus.error,
            message: 'store down'),
      ),
      onSpy: (s) => spy = s,
      onPurchased: () => unlocked = true,
    ));
    await t.pumpAndSettle();

    await t.tap(find.widgetWithText(ElevatedButton, 'BUY'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 800));

    expect(unlocked, isFalse);
    expect(spy?.refreshCount ?? 0, 0);
    expect(find.textContaining('No charge was made'), findsOneWidget);

    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('restore success refreshes entitlement from the backend',
      (t) async {
    SpyMandateNotifier? spy;
    var unlocked = false;
    final service = FakePurchaseService(
      offering: _fullOffering(),
      restoreOutcome: PurchaseOutcome.success,
    );
    await t.pumpWidget(_Harness(
      service: service,
      onSpy: (s) => spy = s,
      onPurchased: () => unlocked = true,
    ));
    await t.pumpAndSettle();

    await t.tap(find.text('Restore purchases'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 800));

    expect(service.restoreCount, 1);
    expect(spy?.refreshCount, 1);
    expect(unlocked, isTrue);

    await t.pump(const Duration(seconds: 5));
  });
}
