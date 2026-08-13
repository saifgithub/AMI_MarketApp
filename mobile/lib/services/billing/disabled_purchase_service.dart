/// Billing off — the [PurchaseService] that never loads the store SDK (DEF282).
///
/// **Why this exists.** RevenueCat's SDK deliberately kills the app when it is
/// configured with a Test Store key (`test_…`) in a non-DEBUG build. Not an
/// error, not a degrade — a `fatalError`, by design, so a Test Store key can
/// never reach the App Store. From the vendored source,
/// `ios/Pods/RevenueCat/Sources/Purchasing/Configuration.swift:532`:
///
///     #if !DEBUG && !BYPASS_SIMULATED_STORE_RELEASE_CHECK
///     // In release builds, we intentionally crash to prevent submitting an
///     // app with a Test Store API key.
///         fatalError(errorMessage)
///     #endif
///
/// Both keys in `infra/alpha.env` are `test_…`, and every build that reaches a
/// device is a release build — cable installs, TestFlight, Play internal. So
/// `Purchases.configure` was a guaranteed crash the first time any paywall
/// opened. Saiful, on device: *"we are using the test key in RC, and the app
/// gets killed for it somehow."*
///
/// **What this does.** Answers every [PurchaseService] call from Dart. It does
/// not import `purchases_flutter`, so with [purchaseServiceProvider] pointing
/// here there is no code path from the app to the SDK at all — the crash is
/// removed structurally rather than by a flag someone can flip back on.
///
/// The paywall is NOT hidden. `isConfigured == false` is the same state DEF100
/// already designed for: `fetchOffering()` returns null and the paywall renders
/// its info-not-buy card. A player who runs out of credits still learns what
/// the tiers are; there is simply no dead buy button. Hiding the surface would
/// make "billing is deliberately off" and "billing is broken" look identical,
/// which is the CR040 line.
///
/// **To turn billing back on** — a real `appl_…`/`goog_…` key from the
/// RevenueCat dashboard, then restore the one line in
/// `lib/state/purchase_providers.dart`. `BillingConfig` refuses a `test_…` key
/// in a release build on its own now, so re-enabling cannot resurrect this
/// crash by itself.
library;

import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';

class DisabledPurchaseService implements PurchaseService {
  const DisabledPurchaseService();

  @override
  bool get isConfigured => false;

  @override
  Future<PaywallOffering?> fetchOffering() async => null;

  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async =>
      PurchaseOutcome.notConfigured;

  @override
  Future<PurchaseOutcome> restore() async => PurchaseOutcome.notConfigured;
}
