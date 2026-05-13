import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

/// Visual variants for [HexChip].
///
/// - [filled]: solid accent fill, white text — tier badges, completed states.
/// - [outlined]: transparent body, colored border + text — inline tags.
/// - [tinted]: faint accent fill (12% alpha) + colored text — status pills
///   (LIVE / MOCK / OFFLINE / WARN). Matches the spec's status-pill pattern.
enum HexChipVariant { filled, outlined, tinted }

/// Small hex-clipped label chip. Used for tier badges, status pills,
/// category tags. UPPERCASE mono text inside.
///
/// Per spec `--clip-hex-chip` — 8px horizontal points, flat top/bottom.
class HexChip extends StatelessWidget {
  const HexChip({
    super.key,
    required this.label,
    this.color = AmiColors.hexBlue,
    this.variant = HexChipVariant.filled,
    this.showDot = false,
    this.fontSize = 11,
  });

  /// Backwards-compatible constructor — accepts the legacy `filled: bool`
  /// flag. New code should pass `variant` directly.
  factory HexChip.legacy({
    Key? key,
    required String label,
    Color color = AmiColors.hexBlue,
    bool filled = true,
  }) =>
      HexChip(
        key: key,
        label: label,
        color: color,
        variant: filled ? HexChipVariant.filled : HexChipVariant.outlined,
      );

  final String label;
  final Color color;
  final HexChipVariant variant;

  /// Show a small leading status dot — typical for LIVE / MOCK / OFFLINE
  /// pills. Defaults to false. Only meaningful with `tinted`.
  final bool showDot;

  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final Color fill;
    final Color textColor;
    final Border? border;
    switch (variant) {
      case HexChipVariant.filled:
        fill = color;
        textColor = Colors.white;
        border = Border.all(color: color, width: 1);
        break;
      case HexChipVariant.outlined:
        fill = Colors.transparent;
        textColor = color;
        border = Border.all(color: color, width: 1);
        break;
      case HexChipVariant.tinted:
        fill = color.withValues(alpha: 0.14);
        textColor = color;
        border = null;
        break;
    }

    return ClipPath(
      clipper: const FlatTopHexagonClipper(cornerCut: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.s,
          vertical: 4,
        ),
        decoration: BoxDecoration(color: fill, border: border),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (showDot) ...[
              Container(
                width: 6, height: 6,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 5),
            ],
            Text(
              label,
              style: AmiTypography.labelMono.copyWith(
                fontSize: fontSize,
                color: textColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
