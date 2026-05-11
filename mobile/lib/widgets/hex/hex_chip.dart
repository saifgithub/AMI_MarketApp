import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

/// Small hex-clipped label chip. Used for tier badges, status chips,
/// inline tags. UPPERCASE mono text inside.
class HexChip extends StatelessWidget {
  const HexChip({
    super.key,
    required this.label,
    this.color = AmiColors.hexBlue,
    this.filled = true,
  });

  final String label;
  final Color color;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return ClipPath(
      clipper: const FlatTopHexagonClipper(cornerCut: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.s,
          vertical: 6,
        ),
        decoration: BoxDecoration(
          color: filled ? color : Colors.transparent,
          border: Border.all(color: color, width: 1),
        ),
        child: Text(
          label,
          style: AmiTypography.labelMono.copyWith(
            fontSize: 11,
            color: filled ? Colors.white : color,
          ),
        ),
      ),
    );
  }
}
