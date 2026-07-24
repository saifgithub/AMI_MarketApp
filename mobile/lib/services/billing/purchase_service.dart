/// Purchase service abstraction (CR084).
///
/// The seam between the paywall and the RevenueCat SDK. Everything the UI needs
/// is expressed in store-agnostic [purchase_models] terms so the widgets and
/// their tests never import `purchases_flutter` or hit a platform channel — the
/// concrete [RevenueCatPurchaseService] is the only place the SDK lives, and a
/// fake stands in for it under test.
library;

import 'package:ami_trade/services/billing/purchase_models.dart';

abstract class PurchaseService {
  /// True when a public SDK key is present for this platform (DEF100). When
  /// false, [fetchOffering] returns null and the paywall degrades to info-only.
  bool get isConfigured;

  /// Fetch the current live offering, mapping RC prices/products into our
  /// domain. Returns null when RC is not configured OR no current offering is
  /// set up yet in the dashboard — both drive the degrade (info-not-buy) path.
  /// Never throws for the "unconfigured" case; a genuine fetch failure throws.
  Future<PaywallOffering?> fetchOffering();

  /// Buy [pkg]. On [PurchaseStatus.success] the store transaction is done but
  /// entitlement is NOT yet trusted — the caller re-reads it from the backend.
  Future<PurchaseOutcome> purchase(PaywallPackage pkg);

  /// Restore prior purchases (App Store requirement). Success does not imply a
  /// specific entitlement — the caller re-reads from the backend afterward.
  Future<PurchaseOutcome> restore();
}
