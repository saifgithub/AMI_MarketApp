import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

enum HexButtonVariant { filled, outlined, glow }

class HexButton extends StatelessWidget {
  const HexButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.color = AmiColors.hexBlue,
    this.variant = HexButtonVariant.filled,
    this.padding,
    this.minHeight = 44, // iOS HIG min touch target
  });

  final String label;
  final VoidCallback? onPressed;
  final Color color;
  final HexButtonVariant variant;
  final EdgeInsetsGeometry? padding;
  final double minHeight;

  bool get _isEnabled => onPressed != null;

  @override
  Widget build(BuildContext context) {
    // C6: `glow` is a filled button with a coloured halo — previously it fell
    // through to `outlined` (dead variant). The halo must sit on a container
    // *behind* the ClipPath, else the clip crops the shadow.
    final isGlow = variant == HexButtonVariant.glow;
    final isFilled = variant == HexButtonVariant.filled || isGlow;
    final textColor = isFilled
        ? Colors.white
        : (_isEnabled ? color : AmiColors.textLow);
    final fillColor = isFilled
        ? (_isEnabled ? color : AmiColors.slate700)
        : Colors.transparent;
    final borderColor = isFilled ? color : (_isEnabled ? color : AmiColors.slate600);

    Widget button = ClipPath(
      clipper: const FlatTopHexagonClipper(cornerCut: AmiRadii.hexCornerMobile),
      child: AnimatedContainer(
        duration: AmiMotion.normal,
        curve: AmiMotion.easeOut,
        padding: padding ??
            const EdgeInsets.symmetric(
              horizontal: AmiSpacing.l,
              vertical: AmiSpacing.m,
            ),
        decoration: BoxDecoration(
          color: fillColor,
          border: Border.all(color: borderColor, width: 1),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: AmiTypography.labelMono.copyWith(color: textColor),
          textAlign: TextAlign.center,
        ),
      ),
    );

    if (isGlow && _isEnabled) {
      button = DecoratedBox(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.5),
              blurRadius: 22,
              spreadRadius: -2,
            ),
          ],
        ),
        child: button,
      );
    }

    return Semantics(
      button: true,
      enabled: _isEnabled,
      label: label,
      child: GestureDetector(
        onTap: onPressed,
        behavior: HitTestBehavior.opaque,
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: minHeight),
          child: button,
        ),
      ),
    );
  }
}
