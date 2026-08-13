/// CR174 §6 — StreakBarsPainter: a run of equity bars stepping down through a
/// losing streak, with the learner's own mandated drawdown ceiling drawn across
/// them as a dashed line.
///
/// The gap this fills is measured, not assumed: RISK 1 ("why risk matters more
/// than profit") is one of the two pilot lessons with **no** registered
/// animation, and its whole argument — *losses compound against you faster than
/// gains compound for you* — is a shape. Prose can state the asymmetry; only a
/// picture makes twelve bars visibly stop being a dip and start being a hole.
///
/// Deliberately **not** a curve. `CurveDrawPainter` already draws smooth equity
/// paths, and reusing it here would say "this is a market moving". A streak is
/// discrete: N decisions, each one a bar, each one survivable on its own. The
/// bar count *is* the point.
library;

import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class StreakBarsPainter extends CustomPainter {
  const StreakBarsPainter({
    required this.t,
    required this.theme,
    required this.equity,
    this.ceilingFraction,
    this.ceilingLabel,
  });

  final double t;
  final AmiAnimTheme theme;

  /// Remaining equity after each loss, as a fraction of the starting account
  /// (1.0 = untouched). One entry per bar, in streak order.
  final List<double> equity;

  /// Where the learner's own `max_drawdown_pct` sits, as the same fraction
  /// (0.7 = "halt at 30% down"). Null when the mandate has not been read yet —
  /// **null draws nothing**, rather than a line at a number we invented.
  final double? ceilingFraction;
  final String? ceilingLabel;

  @override
  void paint(Canvas canvas, Size size) {
    final n = equity.length;
    if (n == 0) return;

    final left = mapNorm(const Offset(0, 0), size).dx;
    final right = mapNorm(const Offset(1, 0), size).dx;
    final base = mapNorm(const Offset(0, 0), size).dy;
    final top = mapNorm(const Offset(0, 1), size).dy;
    final span = base - top;

    canvas.drawLine(
      Offset(left, base),
      Offset(right, base),
      Paint()
        ..color = theme.grid
        ..strokeWidth = theme.thinStroke,
    );

    final slot = (right - left) / n;
    final barW = slot * 0.62;

    for (var i = 0; i < n; i++) {
      // Bars land one after another as `t` runs, so the streak reads as a
      // sequence of decisions rather than a static chart.
      final appear = ((t * n) - i).clamp(0.0, 1.0);
      if (appear <= 0) continue;
      final h = span * equity[i].clamp(0.0, 1.0) * appear;
      final cx = left + slot * (i + 0.5);
      final rect = Rect.fromLTWH(cx - barW / 2, base - h, barW, h);
      final breached =
          ceilingFraction != null && equity[i] < ceilingFraction!;
      canvas.drawRect(
        rect,
        Paint()
          ..color = (breached ? theme.textLow : theme.accent)
              .withValues(alpha: breached ? 0.35 : 0.85),
      );
    }

    final c = ceilingFraction;
    if (c != null) {
      final y = base - span * c.clamp(0.0, 1.0);
      const dash = 7.0, gap = 5.0;
      final dashPaint = Paint()
        ..color = theme.textLow
        ..strokeWidth = theme.thinStroke;
      for (var x = left; x < right; x += dash + gap) {
        canvas.drawLine(
            Offset(x, y), Offset((x + dash).clamp(left, right), y), dashPaint);
      }
      if (ceilingLabel != null) {
        drawLabel(
          canvas,
          ceilingLabel!,
          Offset(right, y - 4),
          style: theme.label.copyWith(color: theme.textMed, fontSize: 10),
          align: Alignment.topRight,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant StreakBarsPainter old) =>
      old.t != t ||
      old.equity != equity ||
      old.ceilingFraction != ceilingFraction;
}
