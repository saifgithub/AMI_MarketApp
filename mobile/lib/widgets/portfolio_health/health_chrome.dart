/// CR136 M09 — chrome shared by the Health card and the Finding screen: the one whole-surface fade and the dashed "this is not a result" frame.
///
/// Both surfaces obey the same two rules, so both rules live in one place. A
/// second copy of either would be a rule with two implementations, which is how
/// they drift; putting them beside the card instead would have meant the
/// Finding screen importing the card that pushes it, which is a cycle.
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Key on the fade's `Opacity`, so a test asserts the reduced-motion rule on
/// this specific widget rather than on whichever `Opacity` it happens to find.
const healthFadeKey = ValueKey<String>('portfolioHealthFade');

/// One opacity fade of the whole surface, and nothing else moves. Bars never
/// grow and numbers are never counted up (data_viz §7): a figure that animates
/// is unreadable while it moves and invites a screenshot of a value that was
/// never true. `Duration.zero` under `disableAnimations` — the flag's first use
/// in the app, and the spec is the pin.
Widget healthFadeIn(BuildContext context, Widget child) =>
    TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0.0, end: 1.0),
      duration: MediaQuery.of(context).disableAnimations
          ? Duration.zero
          : AmiMotion.fast,
      curve: AmiMotion.easeOut,
      builder: (_, value, child) =>
          Opacity(key: healthFadeKey, opacity: value, child: child),
      child: child,
    );

/// A dashed rounded rect. Every state that is NOT a finished measurement wears
/// one — the card's four non-populated states and all four Finding refusal
/// panels — so "this is not a result" is carried by the frame itself rather
/// than by copy the reader may skip (SCREEN_DESIGNS 07b). Precedent: CR098's
/// dashed hexes and the dashed lesson threshold levels.
class HealthDashedBorder extends CustomPainter {
  const HealthDashedBorder({required this.color, this.fill});

  final Color color;
  final Color? fill;

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      const Radius.circular(AmiRadii.card),
    );
    if (fill != null) {
      canvas.drawRRect(rrect, Paint()..color = fill!);
    }
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color;
    for (final metric in (Path()..addRRect(rrect)).computeMetrics()) {
      var d = 0.0;
      while (d < metric.length) {
        final next = math.min(d + 4.0, metric.length);
        canvas.drawPath(metric.extractPath(d, next), paint);
        d = next + 3.0;
      }
    }
  }

  @override
  bool shouldRepaint(HealthDashedBorder old) =>
      old.color != color || old.fill != fill;
}

class HealthDashedBox extends StatelessWidget {
  const HealthDashedBox({
    super.key,
    required this.child,
    this.borderColor = AmiColors.slate700,
    this.fill,
  });

  final Widget child;
  final Color borderColor;
  final Color? fill;

  @override
  Widget build(BuildContext context) => CustomPaint(
        painter: HealthDashedBorder(color: borderColor, fill: fill),
        child: SizedBox(
          width: double.infinity,
          child: Padding(
            padding: const EdgeInsets.all(AmiSpacing.m),
            child: child,
          ),
        ),
      );
}
