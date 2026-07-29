/// The app's large call-to-action. **It is not hex-clipped, and the name is
/// now historical** (CR113).
///
/// Every large CTA in the app goes through this one widget, and it applied
/// `ClipPath(CutCornerOctagonClipper(...))` unconditionally — there was no size
/// variant, so width never entered the decision. At full width the cut corners
/// stop reading as a hexagonal mark and read as a chevron banner. Saiful, on
/// the account-claim CTA: *"the larger buttons should all be normal rounded
/// edge buttons."*
///
/// **The rule this obeys — marks and controls get hex; surfaces and large CTAs
/// get rounded rects.** A full-width CTA is a *surface* wearing a control's
/// clothes. See `docs/initial_specs/05_design/ami_hex_in_flutter.md`. This
/// widget simply predates the rule and was never reconciled to it; `HexChip`,
/// `HexAvatar`, `HexToast`, `HexBottomNav`, `TrackHexButton` and the segmented
/// toggles all keep their geometry deliberately.
///
/// The name stays `HexButton` because renaming it would touch six call sites to
/// no behavioural end — unlike CR117's rename, where the old name made a false
/// claim about a *shape a caller could still select*. Here there is no
/// parameter to get wrong.
library;

import 'package:ami_trade/theme/ami_theme.dart';
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
    // through to `outlined` (dead variant). The halo sits on a container
    // *behind* the button; CR113 removed the ClipPath that used to crop it,
    // but the outer box still has to carry the SAME radius or the halo is a
    // square shadow behind a rounded button.
    final isGlow = variant == HexButtonVariant.glow;
    final isFilled = variant == HexButtonVariant.filled || isGlow;
    final textColor = isFilled
        ? Colors.white
        : (_isEnabled ? color : AmiColors.textLow);
    final fillColor = isFilled
        ? (_isEnabled ? color : AmiColors.slate700)
        : Colors.transparent;
    final borderColor = isFilled ? color : (_isEnabled ? color : AmiColors.slate600);

    Widget button = AnimatedContainer(
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
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      alignment: Alignment.center,
      child: Text(
        label,
        style: AmiTypography.labelMono.copyWith(color: textColor),
        textAlign: TextAlign.center,
      ),
    );

    if (isGlow && _isEnabled) {
      button = DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AmiRadii.card),
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
