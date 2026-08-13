/// DEF282 — the Test Store key that killed the app, and the two things that
/// now stop it.
///
/// Saiful, on device, 2026-08-13: *"we are using the test key in RC, and the
/// app gets killed for it somehow."* The "somehow" is deliberate, and is in
/// the vendored SDK source at
/// `ios/Pods/RevenueCat/Sources/Purchasing/Configuration.swift:532`:
///
///     #if !DEBUG && !BYPASS_SIMULATED_STORE_RELEASE_CHECK
///     // In release builds, we intentionally crash to prevent submitting an
///     // app with a Test Store API key.
///         fatalError(errorMessage)
///     #endif
///
/// RevenueCat does not degrade here — it terminates the process, so that a
/// Test Store key can never reach the App Store. Both keys in
/// `infra/alpha.env` are `test_…`, and every build that reaches a device is a
/// release build (cable install, TestFlight, Play internal), so the first
/// paywall to call `Purchases.configure` killed the app every time.
///
/// These tests pin the fix from the outside — what the app can reach — rather
/// than from the inside. A test that only asserted "the disabled service
/// returns null" would still pass on a build wired straight back to the SDK.
library;

import 'package:ami_trade/services/billing/billing_config.dart';
import 'package:ami_trade/services/billing/disabled_purchase_service.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DEF282 — billing is off, and cannot reach the SDK', () {
    test('the app wires a service that does not import the store SDK', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // The structural claim. `DisabledPurchaseService` has no import of
      // `purchases_flutter`, so while this holds there is no path from the
      // running app to `Purchases.configure` — and therefore none to the
      // fatalError. Re-enabling billing means editing this line, which means
      // this test turns red and the change is deliberate rather than drifted.
      expect(
        container.read(purchaseServiceProvider),
        isA<DisabledPurchaseService>(),
      );
    });

    test('the paywall degrades to info-not-buy rather than disappearing', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final service = container.read(purchaseServiceProvider);

      // `null` is the DEF100 degrade the paywall already renders as its
      // info card. CR040: billing deliberately off and billing broken must
      // not look the same, and hiding the surface would make them identical.
      expect(await service.fetchOffering(), isNull);
      expect(service.isConfigured, isFalse);
    });

    test('a buy or restore reports notConfigured, never a fake success', () async {
      const service = DisabledPurchaseService();

      final bought = await service.purchase(
        const PaywallPackage(
          productId: 'x',
          priceString: r'$14.99',
          storeTitle: 'Trader',
          kind: PaywallKind.subscription,
        ),
      );
      final restored = await service.restore();

      expect(bought.status, PurchaseStatus.notConfigured);
      expect(restored.status, PurchaseStatus.notConfigured);
      // A silent `success` here would send the caller to re-read entitlement
      // from the backend and show nothing changed — the DEF059 shape.
      expect(bought.isSuccess, isFalse);
      expect(restored.isSuccess, isFalse);
    });
  });

  group('DEF282 — the fence, so switching billing back on cannot re-crash', () {
    test('a Test Store key in a release build counts as no key', () {
      expect(BillingConfig.usableKey('test_abc123', debug: false), '');
    });

    test('a Test Store key in a debug build is kept — that is what it is for', () {
      // Simulated purchases end to end are exactly what alpha wants, and in a
      // debug build RevenueCat permits them. The fence must not confiscate it.
      expect(
        BillingConfig.usableKey('test_abc123', debug: true),
        'test_abc123',
      );
    });

    test('a real store key is untouched in either mode', () {
      for (final key in const ['appl_realkey', 'goog_realkey']) {
        expect(BillingConfig.usableKey(key, debug: false), key);
        expect(BillingConfig.usableKey(key, debug: true), key);
      }
    });

    test('an absent key stays absent — DEF100 is unchanged', () {
      expect(BillingConfig.usableKey('', debug: false), '');
      expect(BillingConfig.usableKey('', debug: true), '');
    });
  });
}
