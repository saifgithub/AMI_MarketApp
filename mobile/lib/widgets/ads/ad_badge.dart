/// The mandatory `AD` / `SPONSORED` label (CR122, `ads.md` UX rules).
///
/// Every ad surface carries one, in the canonical mono label face
/// ([AmiTypography.labelMono] — the design system's JetBrains-class mono),
/// uppercase, amber — visually unlike any agent-card chrome so an ad can
/// never be mistaken for analyst output.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class AdBadge extends StatelessWidget {
  const AdBadge({super.key, this.sponsored = false});

  /// False ⇒ "AD" (interstitials), true ⇒ "SPONSORED" (native cards).
  final bool sponsored;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final label = (sponsored ? l.adBadgeSponsored : l.adBadge).toUpperCase();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: AmiColors.hexAmber),
        borderRadius: BorderRadius.circular(AmiRadii.sm),
      ),
      child: Text(
        label,
        style: AmiTypography.labelMono
            .copyWith(fontSize: 10, color: AmiColors.hexAmber),
      ),
    );
  }
}
