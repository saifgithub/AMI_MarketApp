/// Live RevenueCat paywall (CR084).
///
/// Renders the current RC **offering** — Trader / Floor Manager (monthly +
/// annual) plus the three consumable credit packs — with **prices pulled from
/// the offering, never hard-coded** (RC is the store/region source of truth).
/// A completed purchase re-reads entitlement from the backend (via
/// [purchaseControllerProvider]) before the caller unlocks; the webhook, not the
/// SDK cache, is the grant authority.
///
/// Degrade loudly (DEF100): when no SDK key / no offering is configured the
/// widget shows the plain "upgrades not available yet, your credits still reset
/// on {date}" card and a Restore button — never a dead buy button.
///
/// Public + provider-driven so it is directly widget-testable with a fake
/// [purchaseServiceProvider]; it is embedded both at the Room 402 wall and in a
/// Settings bottom sheet.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class UpgradePaywall extends ConsumerWidget {
  const UpgradePaywall({
    super.key,
    required this.resetDateLabel,
    this.onPurchased,
    this.showHeader = true,
  });

  /// Pre-formatted credit reset date, shown on the degrade card so the user
  /// still knows the free monthly reset applies.
  final String resetDateLabel;

  /// Called after a successful purchase AND its backend entitlement refresh.
  /// The Room wall uses this to clear the paywall and re-convene.
  final VoidCallback? onPurchased;

  final bool showHeader;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final offeringAsync = ref.watch(offeringProvider);
    final busy = ref.watch(purchaseControllerProvider).busy;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (showHeader) ...[
          Text(l.upgradeSheetTitle,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const SizedBox(height: AmiSpacing.xs),
          Text(l.upgradeSheetSubtitle,
              style: AmiTypography.caption.copyWith(color: AmiColors.textMed)),
          const SizedBox(height: AmiSpacing.m),
        ],
        offeringAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(AmiSpacing.l),
            child: Center(
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          ),
          // A genuine fetch failure degrades to the same info-not-buy card as an
          // unconfigured store — never a broken checkout.
          error: (_, __) => _Unavailable(resetDateLabel: resetDateLabel),
          data: (offering) {
            if (offering == null || offering.isEmpty) {
              return _Unavailable(resetDateLabel: resetDateLabel);
            }
            return _OfferingBody(
              offering: offering,
              busy: busy,
              onBuy: (pkg) => _buy(context, ref, l, pkg),
            );
          },
        ),
        const SizedBox(height: AmiSpacing.s),
        // Restore is always available (App Store requirement) — it degrades to a
        // message when nothing is configured, rather than being hidden.
        Center(
          child: TextButton(
            onPressed: busy ? null : () => _restore(context, ref, l),
            child: Text(l.upgradeRestore,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.textMed)),
          ),
        ),
      ],
    );
  }

  Future<void> _buy(BuildContext context, WidgetRef ref, AppLocalizations l,
      PaywallPackage pkg) async {
    final outcome = await ref.read(purchaseControllerProvider.notifier).buy(pkg);
    if (!context.mounted) return;
    switch (outcome.status) {
      case PurchaseStatus.success:
        _toast(context, l.upgradePurchaseSuccess);
        onPurchased?.call();
        break;
      case PurchaseStatus.cancelled:
        // User backed out — say nothing.
        break;
      case PurchaseStatus.pending:
        _toast(context, l.upgradePurchasePending);
        break;
      case PurchaseStatus.error:
      case PurchaseStatus.notConfigured:
        _toast(context, l.upgradePurchaseFailed);
        break;
    }
  }

  Future<void> _restore(
      BuildContext context, WidgetRef ref, AppLocalizations l) async {
    final outcome =
        await ref.read(purchaseControllerProvider.notifier).restore();
    if (!context.mounted) return;
    switch (outcome.status) {
      case PurchaseStatus.success:
        _toast(context, l.upgradePurchaseSuccess);
        onPurchased?.call();
        break;
      case PurchaseStatus.pending:
        _toast(context, l.upgradePurchasePending);
        break;
      case PurchaseStatus.cancelled:
        break;
      case PurchaseStatus.error:
      case PurchaseStatus.notConfigured:
        _toast(context, l.upgradeRestoreNone);
        break;
    }
  }

  void _toast(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }
}

/// DEF100 degrade card — no buy button. Shown when RC/offering is unconfigured
/// or the fetch failed.
class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.resetDateLabel});
  final String resetDateLabel;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lock_clock_outlined,
                  color: AmiColors.textMed, size: 18),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(l.upgradeUnavailableTitle,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.textHigh)),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.upgradeUnavailableBody(resetDateLabel),
              style: AmiTypography.body),
        ],
      ),
    );
  }
}

class _OfferingBody extends StatelessWidget {
  const _OfferingBody({
    required this.offering,
    required this.busy,
    required this.onBuy,
  });

  final PaywallOffering offering;
  final bool busy;
  final ValueChanged<PaywallPackage> onBuy;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final children = <Widget>[];

    for (final tier in PaywallTier.values) {
      final pkgs = offering.tier(tier);
      if (pkgs.isEmpty) continue;
      children.add(_PlanCard(
        title: tier == PaywallTier.trader
            ? l.upgradePlanTrader
            : l.upgradePlanFloorManager,
        packages: pkgs,
        busy: busy,
        onBuy: onBuy,
      ));
      children.add(const SizedBox(height: AmiSpacing.s));
    }

    final packs = offering.creditPacks;
    if (packs.isNotEmpty) {
      children.add(Padding(
        padding: const EdgeInsets.only(top: AmiSpacing.s, bottom: AmiSpacing.xs),
        child: Text(l.upgradeCreditPacksTitle,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
      ));
      for (final p in packs) {
        children.add(_ProductRow(
          label: p.packCredits != null
              ? l.upgradeCreditPackCredits(p.packCredits!)
              : p.storeTitle,
          priceString: p.priceString,
          busy: busy,
          onBuy: () => onBuy(p),
        ));
      }
    }

    // Unrecognized products still surface (degrade loudly), using RC's title.
    for (final p in offering.other) {
      children.add(_ProductRow(
        label: p.storeTitle,
        priceString: p.priceString,
        busy: busy,
        onBuy: () => onBuy(p),
      ));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.title,
    required this.packages,
    required this.busy,
    required this.onBuy,
  });

  final String title;
  final List<PaywallPackage> packages;
  final bool busy;
  final ValueChanged<PaywallPackage> onBuy;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: AmiTypography.body.copyWith(
                color: AmiColors.textHigh,
                fontWeight: FontWeight.w600,
              )),
          const SizedBox(height: AmiSpacing.xs),
          for (final p in packages)
            _ProductRow(
              label: p.interval == PaywallInterval.annual
                  ? l.upgradeIntervalAnnual
                  : l.upgradeIntervalMonthly,
              priceString: p.priceString,
              busy: busy,
              onBuy: () => onBuy(p),
            ),
        ],
      ),
    );
  }
}

class _ProductRow extends StatelessWidget {
  const _ProductRow({
    required this.label,
    required this.priceString,
    required this.busy,
    required this.onBuy,
  });

  final String label;
  final String priceString;
  final bool busy;
  final VoidCallback onBuy;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: AmiTypography.body)),
          Text(priceString,
              style: AmiTypography.statSmall.copyWith(color: AmiColors.textHigh)),
          const SizedBox(width: AmiSpacing.s),
          SizedBox(
            height: 32,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexCyan,
                foregroundColor: AmiColors.slate900,
                padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
              ),
              onPressed: busy ? null : onBuy,
              child: Text(l.upgradeBuy,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.slate900, fontSize: 11)),
            ),
          ),
        ],
      ),
    );
  }
}

/// Present the paywall as a modal bottom sheet (the Settings entry point).
Future<void> showUpgradeSheet(
  BuildContext context, {
  required String resetDateLabel,
  VoidCallback? onPurchased,
}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (sheetContext) {
      return Padding(
        padding: EdgeInsets.fromLTRB(
          AmiSpacing.l,
          AmiSpacing.l,
          AmiSpacing.l,
          AmiSpacing.xl + MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: SingleChildScrollView(
          child: UpgradePaywall(
            resetDateLabel: resetDateLabel,
            onPurchased: () {
              onPurchased?.call();
              Navigator.of(sheetContext).pop();
            },
          ),
        ),
      );
    },
  );
}
