/// CR260 / CR267 WP-21b — the Settings switch for the Street-rating card on the
/// Verdict Board. Default ON (Beta programme §3a.3: shown to testers after the
/// verdict, behind a setting); turning it off only hides the card — the Room
/// never sees the Street rating either way.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/street_comparison_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class StreetComparisonSetting extends ConsumerWidget {
  const StreetComparisonSetting({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final enabled = ref.watch(streetComparisonEnabledProvider);
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l.settingsStreetRatingToggle, style: AmiTypography.body),
              const SizedBox(height: 2),
              Text(
                l.settingsStreetRatingToggleSubtitle,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow),
              ),
            ],
          ),
        ),
        Switch(
          key: const ValueKey('street-comparison-switch'),
          value: enabled,
          onChanged: (v) =>
              ref.read(streetComparisonEnabledProvider.notifier).setEnabled(v),
          activeThumbColor: AmiColors.hexGreen,
          inactiveThumbColor: AmiColors.slate600,
        ),
      ],
    );
  }
}
