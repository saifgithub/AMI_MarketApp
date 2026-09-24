/// Compact house-ad fallback for the global banner slot (CR226).
///
/// [HouseAdCard] is a full card — headline, body, CTA button — sized for a
/// native-card placement, not a 50dp anchored strip. When AdMob has no fill
/// (or is unconfigured) for [AdPlacement.globalBanner], this renders the
/// SAME targeted [HouseAdCreative] the full card would, in a single row that
/// fits the fixed banner height: badge, one-line headline, a text CTA. No
/// body copy, no dismiss X — `ads.md`'s "remove ads lives in Wallet & Plan,
/// never inside an ad" already means there is nothing this strip needs a
/// close button for that the card's own dismissal semantics require, and a
/// persistent chrome slot dismissing itself mid-session would contradict
/// "visible on every post-onboarding page".
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_badge.dart';
import 'package:ami_trade/widgets/ads/house_ad_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class HouseAdBannerStrip extends ConsumerWidget {
  const HouseAdBannerStrip({super.key, required this.creative});

  final HouseAdCreative creative;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    // Reuses AdSlot's copy table (`HouseAdCard.copyFor`) — one source of
    // headline strings per HouseAdSlot, not a second one for the banner.
    final copy = HouseAdCard.copyFor(l, creative.slot);
    final cta = creative.targetTier == HouseAdTargetTier.floorManager
        ? l.houseAdCtaFloorManager
        : l.houseAdCtaTrader;
    return GestureDetector(
      onTap: () => openHouseAdPaywall(context, ref),
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: double.infinity,
        color: AmiColors.cardBgAlt,
        padding:
            const EdgeInsets.symmetric(horizontal: AmiSpacing.m, vertical: 6),
        child: Row(
          children: [
            const AdBadge(),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Text(
                copy.headline,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AmiTypography.bodySm,
              ),
            ),
            const SizedBox(width: AmiSpacing.s),
            Text(
              cta,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.hexAmber),
            ),
          ],
        ),
      ),
    );
  }
}
