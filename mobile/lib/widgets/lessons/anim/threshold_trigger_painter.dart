/// CR013 (E3/D1) — ThresholdTriggerPainter: a price path is revealed toward a
/// dashed horizontal level; when the head reaches the level it flashes a ring +
/// label. Powers stop_loss_trigger, support_resistance_test, breakout_pattern.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class ThresholdTriggerPainter extends CustomPainter {
  const ThresholdTriggerPainter({
    required this.t,
    required this.theme,
    required this.level,
    required this.path,
    required this.triggerLabel,
    this.breach = true,
  });

  final double t;
  final AmiAnimTheme theme;

  /// Normalized y of the dashed level (0 bottom, 1 top).
  final double level;

  /// Normalized price path (x,y ∈ [0,1], y up).
  final List<Offset> path;
  final String triggerLabel;

  /// true = breakout (up, accent/green); false = stop (down, red).
  final bool breach;

  @override
  void paint(Canvas canvas, Size size) {
    final triggerColor = breach ? AmiColors.hexGreen : AmiColors.hexRed;

    // Dashed level line.
    final y = mapNorm(Offset(0, level), size).dy;
    final left = mapNorm(const Offset(0, 0), size).dx;
    final right = mapNorm(const Offset(1, 0), size).dx;
    final dashPaint = Paint()
      ..color = theme.textLow
      ..strokeWidth = theme.thinStroke;
    const dash = 8.0, gap = 6.0;
    for (var x = left; x < right; x += dash + gap) {
      canvas.drawLine(Offset(x, y), Offset((x + dash).clamp(left, right), y),
          dashPaint);
    }
    drawLabel(
      canvas,
      triggerLabel,
      Offset(right, y - 6),
      style: theme.label.copyWith(color: theme.textMed, fontSize: 10),
      align: Alignment.topRight,
    );

    // Revealed price path.
    final pts = path.map((n) => mapNorm(n, size)).toList();
    final rev = revealPolyline(pts, t);
    canvas.drawPath(
      rev.path,
      Paint()
        ..color = theme.accent
        ..style = PaintingStyle.stroke
        ..strokeWidth = theme.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawCircle(rev.head, theme.stroke + 1.5, Paint()..color = theme.accent);

    // Flash ring once the head arrives at the level (near the end of the path).
    final headYNorm = 1 -
        (rev.head.dy - kAnimPad.top) / (size.height - kAnimPad.vertical);
    final atLevel = (headYNorm - level).abs() < 0.06 && t > 0.55;
    if (atLevel) {
      final pulse = (t - 0.55) / 0.45; // 0→1 over the tail
      canvas.drawCircle(
        rev.head,
        (theme.stroke + 2) + pulse * 22,
        Paint()
          ..color = triggerColor.withValues(alpha: (1 - pulse).clamp(0.0, 1.0))
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5,
      );
      canvas.drawCircle(rev.head, theme.stroke + 2,
          Paint()..color = triggerColor);
    }
  }

  @override
  bool shouldRepaint(covariant ThresholdTriggerPainter old) =>
      old.t != t || old.level != level || old.breach != breach;
}
