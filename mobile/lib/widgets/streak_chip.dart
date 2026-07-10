/// CR010 (B2) — the streak chip: a hex glyph + the current streak count,
/// amber while today's challenge is still open and green once it's done.
/// Shown on the Floor header and the daily-challenge card. "Filled" is scoped
/// to today's daily challenge (the action this chip nudges), not every
/// streak-eligible activity.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class StreakChip extends StatelessWidget {
  const StreakChip({
    super.key,
    required this.count,
    required this.todayFilled,
    this.onTap,
  });

  final int count;
  final bool todayFilled;

  /// Optional tap handler — the Floor wires this to share the streak (CR012 C4).
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = todayFilled ? AmiColors.hexGreen : AmiColors.hexAmber;
    final chip = Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.hexagon_outlined, color: color, size: 14),
          const SizedBox(width: 4),
          Text(
            '$count',
            style: AmiTypography.labelMono.copyWith(color: color, fontSize: 12),
          ),
        ],
      ),
    );
    if (onTap == null) return chip;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: chip,
    );
  }
}
