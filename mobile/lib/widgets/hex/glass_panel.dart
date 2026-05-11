import 'dart:ui';

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// AMI signature glass surface — dark translucent panel with backdrop blur.
///
/// Optionally takes an [accentColor] for the 3px top border that
/// the AMI design system uses to categorize cards by role.
class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AmiSpacing.m),
    this.margin,
    this.accentColor,
    this.radius = AmiRadii.card,
    this.borderColor,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final Color? accentColor;
  final double radius;
  final Color? borderColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(
          color: borderColor ?? AmiColors.slate700,
          width: 1,
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
          child: Container(
            decoration: BoxDecoration(
              color: AmiColors.glass,
              border: accentColor != null
                  ? Border(top: BorderSide(color: accentColor!, width: 3))
                  : null,
            ),
            padding: padding,
            child: child,
          ),
        ),
      ),
    );
  }
}
