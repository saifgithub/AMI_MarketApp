/// Intro bottom sheet shown before the Floor coach marks.
///
/// Returns true via Navigator.pop when the user wants the tour, null/false
/// when they skip. Shown only on the Floor tab (first section the user sees).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class TourIntroSheet extends StatelessWidget {
  const TourIntroSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AmiSpacing.l, AmiSpacing.l, AmiSpacing.l, AmiSpacing.m,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AmiColors.slate600,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AmiSpacing.l),
            const Icon(Icons.explore_outlined, color: AmiColors.hexCyan, size: 40),
            const SizedBox(height: AmiSpacing.m),
            Text(
              l.tourIntroTitle,
              style: AmiTypography.h4,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.s),
            Text(
              l.tourIntroSubtitle,
              style: AmiTypography.body.copyWith(color: AmiColors.textMed),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.xl),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: () => Navigator.of(context).pop(true),
                child: Text(l.tourTakeTheTour,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.slate900)),
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(
                l.tourSkipForNow,
                style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
