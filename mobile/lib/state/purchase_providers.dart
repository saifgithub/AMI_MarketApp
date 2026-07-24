/// Riverpod wiring for the CR084 paywall / purchase flow.
///
/// Three providers:
///   * [purchaseServiceProvider] — the RC-backed [PurchaseService]. Tests
///     override this with a fake so the paywall never hits a platform channel.
///   * [offeringProvider] — the live offering (or null when RC/DEF100 is not
///     configured, driving the info-not-buy degrade).
///   * [purchaseControllerProvider] — runs a purchase/restore and, on success,
///     **re-reads entitlement from the backend** (the mandate endpoint), never
///     trusting the SDK's local cache: the webhook (CR084-BE) is the grant
///     authority, the store result only says "go re-read".
library;

import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/services/billing/revenuecat_purchase_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final purchaseServiceProvider = Provider<PurchaseService>((ref) {
  final api = ref.watch(apiClientProvider);
  return RevenueCatPurchaseService(api: api);
});

/// The current live offering. `null` ⇒ not configured yet (no SDK key / no
/// dashboard offering) ⇒ the paywall shows the info state, not a buy button.
final offeringProvider = FutureProvider.autoDispose<PaywallOffering?>((ref) {
  return ref.watch(purchaseServiceProvider).fetchOffering();
});

@immutable
class PurchaseControllerState {
  const PurchaseControllerState({this.busy = false, this.last});

  /// A purchase/restore is in flight — disable buy buttons.
  final bool busy;

  /// The most recent outcome (for one-shot UI feedback).
  final PurchaseOutcome? last;

  PurchaseControllerState copyWith({bool? busy, PurchaseOutcome? last}) {
    return PurchaseControllerState(
      busy: busy ?? this.busy,
      last: last ?? this.last,
    );
  }
}

class PurchaseController extends StateNotifier<PurchaseControllerState> {
  PurchaseController(this._ref) : super(const PurchaseControllerState());

  final Ref _ref;

  Future<PurchaseOutcome> buy(PaywallPackage pkg) async {
    if (state.busy) return const PurchaseOutcome(PurchaseStatus.error);
    state = state.copyWith(busy: true);
    final outcome = await _ref.read(purchaseServiceProvider).purchase(pkg);
    if (outcome.isSuccess) {
      await _refreshEntitlementFromBackend();
    }
    state = PurchaseControllerState(busy: false, last: outcome);
    return outcome;
  }

  Future<PurchaseOutcome> restore() async {
    if (state.busy) return const PurchaseOutcome(PurchaseStatus.error);
    state = state.copyWith(busy: true);
    final outcome = await _ref.read(purchaseServiceProvider).restore();
    if (outcome.isSuccess) {
      await _refreshEntitlementFromBackend();
    }
    state = PurchaseControllerState(busy: false, last: outcome);
    return outcome;
  }

  /// Re-read plan + credit state from the backend (`GET /v1/mandate/{id}`), the
  /// server-authoritative source the webhook writes — NOT the SDK's cached
  /// CustomerInfo. This is the "unlock" step.
  Future<void> _refreshEntitlementFromBackend() async {
    await _ref.read(mandateNotifierProvider.notifier).refresh();
  }
}

final purchaseControllerProvider =
    StateNotifierProvider<PurchaseController, PurchaseControllerState>((ref) {
  return PurchaseController(ref);
});
