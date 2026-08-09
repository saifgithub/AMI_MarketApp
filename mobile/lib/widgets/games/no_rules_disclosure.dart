/// CR109 slice 2 — the no-rules disclosure (design §7, §13.3).
///
/// The game trade path runs with no mandate, no position/sector/drawdown
/// cap and no halal/locale screen (implementation_plan.md §7). CR040: "a
/// screen that silently stops existing" is exactly this shape, so it must
/// be disclosed plainly rather than left to be discovered. [NoRulesDisclosurePanel]
/// renders the full text on a player's first entry; [NoRulesDisclosureChip]
/// compresses it to a tappable chip on every entry after — tappable, not
/// merely smaller, or "compresses" would quietly become "buried".
///
/// Colour-neutral by design (CR134 §21): this is a disclosure, not a
/// warning, so neither variant uses amber.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';

class NoRulesDisclosurePanel extends StatelessWidget {
  const NoRulesDisclosurePanel({super.key});

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
              const Icon(Icons.rule_folder_outlined,
                  color: AmiColors.textMed, size: 16),
              const SizedBox(width: AmiSpacing.xs),
              Text(
                l.gamesDisclosureHeading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.gamesDisclosureBody, style: AmiTypography.body),
        ],
      ),
    );
  }
}

class NoRulesDisclosureChip extends StatelessWidget {
  const NoRulesDisclosureChip({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return GestureDetector(
      onTap: () => _showFull(context),
      child: HexChip(
        label: l.gamesDisclosureChip,
        color: AmiColors.slate600,
        variant: HexChipVariant.outlined,
      ),
    );
  }

  void _showFull(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: AmiColors.slate800,
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: const NoRulesDisclosurePanel(),
        ),
      ),
    );
  }
}
