/// Native house-ad card (CR122-MOBILE-A).
///
/// Renders one [HouseAdCreative] per `ads.md` UX rules: SPONSORED label in
/// mono uppercase, one-tap dismiss (X in the corner), and a look deliberately
/// unlike agent cards — flat amber-edged rectangle, no hex clipping, no role
/// accent — so no confusion is possible. The CTA opens the CR084 paywall
/// sheet; the "remove ads" path itself lives in Wallet & Plan, never inside
/// an ad (`ads.md:117`).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_badge.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class HouseAdCard extends ConsumerWidget {
  const HouseAdCard({
    super.key,
    required this.creative,
    required this.onDismiss,
  });

  final HouseAdCreative creative;
  final VoidCallback onDismiss;

  static ({String headline, String body}) copyFor(
      AppLocalizations l, HouseAdSlot slot) {
    switch (slot) {
      case HouseAdSlot.oneOnOnesToTrader:
        return (
          headline: l.houseAdOneOnOneHeadline,
          body: l.houseAdOneOnOneBody
        );
      case HouseAdSlot.freeRoomToTrader:
        return (headline: l.houseAdRoomHeadline, body: l.houseAdRoomBody);
      case HouseAdSlot.creditCapToFloorManager:
        return (
          headline: l.houseAdCreditCapHeadline,
          body: l.houseAdCreditCapBody
        );
      case HouseAdSlot.halalToFloorManager:
        return (headline: l.houseAdHalalHeadline, body: l.houseAdHalalBody);
      case HouseAdSlot.genericTrader:
        return (
          headline: l.houseAdGenericHeadline,
          body: l.houseAdGenericBody
        );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final copy = copyFor(l, creative.slot);
    final cta = creative.targetTier == HouseAdTargetTier.floorManager
        ? l.houseAdCtaFloorManager
        : l.houseAdCtaTrader;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.cardBgAlt,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const AdBadge(sponsored: true),
              const Spacer(),
              IconButton(
                onPressed: onDismiss,
                icon: const Icon(Icons.close,
                    size: 18, color: AmiColors.textMed),
                tooltip: l.adDismiss,
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints:
                    const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(copy.headline, style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          Text(copy.body, style: AmiTypography.bodySm),
          const SizedBox(height: AmiSpacing.s),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: AmiColors.hexAmber,
                side: const BorderSide(color: AmiColors.hexAmber),
              ),
              onPressed: () => openHouseAdPaywall(context, ref),
              child: Text(cta),
            ),
          ),
        ],
      ),
    );
  }
}

/// Opens the CR084 paywall sheet — the landing surface for every house-ad
/// CTA (card and interstitial alike).
void openHouseAdPaywall(BuildContext context, WidgetRef ref) {
  // Same reset-date derivation as the Settings membership section; the
  // paywall only shows it on the degrade card.
  final resetAt = ref.read(mandateNotifierProvider).mandate?.creditsResetAt;
  final resetLabel = resetAt == null
      ? 'the 1st'
      : '${resetAt.year}-${resetAt.month.toString().padLeft(2, '0')}-'
          '${resetAt.day.toString().padLeft(2, '0')}';
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AmiColors.slate800,
    shape: const RoundedRectangleBorder(
      borderRadius:
          BorderRadius.vertical(top: Radius.circular(AmiRadii.sheet)),
    ),
    builder: (sheetCtx) => SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.only(
          left: AmiSpacing.m,
          right: AmiSpacing.m,
          top: AmiSpacing.m,
          bottom: MediaQuery.of(sheetCtx).viewInsets.bottom + AmiSpacing.m,
        ),
        child: UpgradePaywall(
          resetDateLabel: resetLabel,
          onPurchased: () => Navigator.of(sheetCtx).maybePop(),
        ),
      ),
    ),
  );
}
