/// B6 — shared empty-state block, modelled on the Journal `_EmptyState` shape:
/// an icon, a title, an optional one-liner, and an optional call to action.
/// All copy is passed in (localised by the caller, AMI voice). Reused across
/// the portfolio, watchlist, ticker-detail, and Alpaca surfaces so an empty
/// view reads as intentional rather than broken.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class AmiEmptyState extends StatelessWidget {
  const AmiEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.body,
    this.ctaLabel,
    this.onCta,
    this.ctaIcon,
  });

  final IconData icon;
  final String title;
  final String? body;
  final String? ctaLabel;
  final VoidCallback? onCta;
  final IconData? ctaIcon;

  @override
  Widget build(BuildContext context) {
    final showCta = ctaLabel != null && onCta != null;
    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.xl),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: AmiColors.textLow, size: 40),
            const SizedBox(height: AmiSpacing.m),
            Text(title, style: AmiTypography.h4, textAlign: TextAlign.center),
            if (body != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(
                body!,
                textAlign: TextAlign.center,
                style: AmiTypography.body.copyWith(color: AmiColors.textLow),
              ),
            ],
            if (showCta) ...[
              const SizedBox(height: AmiSpacing.m),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                ),
                icon: Icon(ctaIcon ?? Icons.add),
                label: Text(ctaLabel!),
                onPressed: onCta,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
