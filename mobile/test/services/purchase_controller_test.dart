/// CR084 — [PurchaseController] backend-refresh contract (no widgets).
///
/// The webhook (CR084-BE) is the grant authority; the SDK result only says "go
/// re-read". This proves the controller re-reads entitlement from the backend
/// (the mandate notifier) exactly when — and only when — a purchase/restore
/// actually succeeds.
library;

import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeService implements PurchaseService {
  _FakeService(this._buy, this._restore);
  final PurchaseOutcome _buy;
  final PurchaseOutcome _restore;
  @override
  bool get isConfigured => true;
  @override
  Future<PaywallOffering?> fetchOffering() async => null;
  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async => _buy;
  @override
  Future<PurchaseOutcome> restore() async => _restore;
}

class _SpyMandate extends MandateNotifier {
  _SpyMandate(super.ref);
  int refreshCount = 0;
  @override
  Future<void> refresh() async => refreshCount++;
}

PaywallPackage _pkg() => const PaywallPackage(
      productId: PaywallProductIds.traderMonthly,
      priceString: '\$14.99',
      storeTitle: 'Trader',
      kind: PaywallKind.subscription,
      tier: PaywallTier.trader,
      interval: PaywallInterval.monthly,
    );

({ProviderContainer container, _SpyMandate? Function() spy}) _harness(
    _FakeService svc) {
  _SpyMandate? captured;
  final container = ProviderContainer(overrides: [
    purchaseServiceProvider.overrideWithValue(svc),
    mandateNotifierProvider.overrideWith((ref) {
      captured = _SpyMandate(ref);
      return captured!;
    }),
  ]);
  addTearDown(container.dispose);
  return (container: container, spy: () => captured);
}

void main() {
  test('successful buy re-reads entitlement from backend', () async {
    final h = _harness(_FakeService(
      PurchaseOutcome.success,
      PurchaseOutcome.success,
    ));
    final outcome =
        await h.container.read(purchaseControllerProvider.notifier).buy(_pkg());
    expect(outcome.isSuccess, isTrue);
    expect(h.spy()!.refreshCount, 1);
  });

  test('cancelled buy does NOT re-read entitlement', () async {
    final h = _harness(_FakeService(
      PurchaseOutcome.cancelled,
      PurchaseOutcome.success,
    ));
    final outcome =
        await h.container.read(purchaseControllerProvider.notifier).buy(_pkg());
    expect(outcome.status, PurchaseStatus.cancelled);
    // The mandate notifier may never even be built; refresh must not run.
    expect(h.spy()?.refreshCount ?? 0, 0);
  });

  test('errored buy does NOT re-read entitlement', () async {
    final h = _harness(_FakeService(
      const PurchaseOutcome(PurchaseStatus.error, message: 'x'),
      PurchaseOutcome.success,
    ));
    await h.container.read(purchaseControllerProvider.notifier).buy(_pkg());
    expect(h.spy()?.refreshCount ?? 0, 0);
  });

  test('successful restore re-reads entitlement from backend', () async {
    final h = _harness(_FakeService(
      PurchaseOutcome.success,
      PurchaseOutcome.success,
    ));
    final outcome =
        await h.container.read(purchaseControllerProvider.notifier).restore();
    expect(outcome.isSuccess, isTrue);
    expect(h.spy()!.refreshCount, 1);
  });
}
