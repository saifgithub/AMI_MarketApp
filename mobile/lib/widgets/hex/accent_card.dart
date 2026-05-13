/// Accent card — glass panel with a 2px colored top border.
///
/// Mobile variant of the AMI hex design language's "accent card" pattern
/// (desktop uses 3px). The top-stripe is the at-a-glance categorisation
/// signal: cyan = info, amber = attention/risk, green = positive, red =
/// error, purple = highlight/AI, pink = tertiary.
///
/// Per spec (ui_kits/mobile/README.md):
///   "Cards: glass panels (#111827 + 1px border) with a 2px colored
///    top-border accent — same vocabulary as desktop."
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class AccentCard extends StatelessWidget {
  const AccentCard({
    super.key,
    required this.accent,
    required this.child,
    this.padding = const EdgeInsets.all(AmiSpacing.m),
    this.onTap,
  });

  /// Top-stripe color. Drive from the design system's semantic accents
  /// (hexCyan / hexAmber / hexGreen / hexRed / hexPurple / hexPink).
  final Color accent;

  /// Inner content.
  final Widget child;

  final EdgeInsetsGeometry padding;

  /// Optional tap handler. Provides Material InkWell ripple when set.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 2px top-accent stripe — sits flush with the rounded corners
          // by inheriting the card's clip radius from the parent ClipRRect.
          Container(height: 2, color: accent),
          Padding(padding: padding, child: child),
        ],
      ),
    );

    final clipped = ClipRRect(
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: card,
    );

    if (onTap == null) return clipped;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: clipped,
      ),
    );
  }
}
