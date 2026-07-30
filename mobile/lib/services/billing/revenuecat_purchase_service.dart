/// RevenueCat implementation of [PurchaseService] (CR084).
///
/// The ONLY file that touches `purchases_flutter` / a store platform channel.
///
/// Lifecycle: the SDK is configured lazily the first time a paywall is shown
/// (not at app boot), then `Purchases.logIn(app_user_id)` binds the RC customer
/// to our `users.id` — the id is fetched from `GET /v1/billing/identity`
/// (CR084-BE) so RC stamps it on every webhook event and the server grant maps
/// back to the right user. No key (DEF100) ⇒ never configured ⇒ [fetchOffering]
/// returns null and the paywall degrades loudly to info-not-buy.
///
/// Prices are read straight off RC's `StoreProduct.priceString`; nothing here
/// invents a price. The store transaction returned by `purchasePackage` is
/// treated only as "go re-read entitlement from the backend" — this file never
/// grants anything client-side.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/billing/billing_config.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show PlatformException;
import 'package:purchases_flutter/purchases_flutter.dart';

class RevenueCatPurchaseService implements PurchaseService {
  RevenueCatPurchaseService({required ApiClient api}) : _api = api;

  final ApiClient _api;
  bool _configured = false;

  @override
  bool get isConfigured => BillingConfig.isConfigured;

  Future<void> _ensureConfigured() async {
    if (_configured) return;
    if (!isConfigured) {
      // Should be guarded by callers, but never configure without a key.
      throw StateError('RevenueCat SDK key not set (DEF100)');
    }
    await Purchases.configure(
        PurchasesConfiguration(BillingConfig.publicSdkKey));
    // Bind the RC customer to our backend user so the webhook can map the
    // purchase back. app_user_id is authoritative from the backend, not a
    // locally-assumed device id.
    final identity = await _api.getBillingIdentity();
    await Purchases.logIn(identity.appUserId);
    _configured = true;
  }

  @override
  Future<PaywallOffering?> fetchOffering() async {
    if (!isConfigured) return null; // DEF100 degrade — info-not-buy.
    await _ensureConfigured();
    final Offerings offerings = await Purchases.getOfferings();
    final Offering? current = offerings.current;
    if (current == null || current.availablePackages.isEmpty) {
      // RC configured but no current offering set up yet — still degrade.
      return null;
    }
    return PaywallOffering(
      identifier: current.identifier,
      packages: current.availablePackages.map(_mapPackage).toList(),
    );
  }

  PaywallPackage _mapPackage(Package pkg) {
    final product = pkg.storeProduct;
    final c = PaywallPackage.classify(product.identifier);
    return PaywallPackage(
      productId: product.identifier,
      priceString: product.priceString,
      storeTitle: product.title,
      kind: c.kind,
      tier: c.tier,
      interval: c.interval,
      packCredits: c.credits,
      raw: pkg,
    );
  }

  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async {
    if (!isConfigured) return PurchaseOutcome.notConfigured;
    final raw = pkg.raw;
    if (raw is! Package) {
      return const PurchaseOutcome(PurchaseStatus.error,
          message: 'Missing store package');
    }
    try {
      await _ensureConfigured();
      await Purchases.purchase(PurchaseParams.package(raw));
      // Store transaction done. Entitlement is NOT trusted from here — the
      // caller re-reads it from the backend (the webhook is the grant path).
      return PurchaseOutcome.success;
    } on PlatformException catch (e) {
      return _mapError(e);
    } catch (e) {
      if (kDebugMode) debugPrint('RevenueCat purchase error: $e');
      return PurchaseOutcome(PurchaseStatus.error,
          message: friendlyError(e, action: 'complete this purchase'));
    }
  }

  @override
  Future<PurchaseOutcome> restore() async {
    if (!isConfigured) return PurchaseOutcome.notConfigured;
    try {
      await _ensureConfigured();
      await Purchases.restorePurchases();
      return PurchaseOutcome.success;
    } on PlatformException catch (e) {
      return _mapError(e);
    } catch (e) {
      if (kDebugMode) debugPrint('RevenueCat restore error: $e');
      return PurchaseOutcome(PurchaseStatus.error,
          message: friendlyError(e, action: 'restore your purchases'));
    }
  }

  PurchaseOutcome _mapError(PlatformException e) {
    final code = PurchasesErrorHelper.getErrorCode(e);
    switch (code) {
      case PurchasesErrorCode.purchaseCancelledError:
        return PurchaseOutcome.cancelled;
      case PurchasesErrorCode.paymentPendingError:
        return PurchaseOutcome.pending;
      default:
        debugPrint('RevenueCat purchase error: $code / ${e.message}');
        return PurchaseOutcome(PurchaseStatus.error, message: e.message);
    }
  }
}
