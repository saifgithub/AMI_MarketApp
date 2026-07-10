/// CR013 (E3/D1) — CurveDrawPainter: an animated path reveal with an optional
/// area fill and annotation flags at x-stops. Powers the "shape of a curve"
/// lessons: compounding_curve, fomo_curve, pump_dump_curve, drawdown_recovery.
library;

import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

/// A flag drawn on the curve once the reveal passes normalized x [atX].
class CurveFlag {
  const CurveFlag(this.atX, this.label);
  final double atX;
  final String label;
}

class CurveDrawPainter extends CustomPainter {
  const CurveDrawPainter({
    required this.t,
    required this.theme,
    required this.points,
    this.fill = true,
    this.flags = const [],
  });

  final double t;
  final AmiAnimTheme theme;

  /// Normalized control points (x,y ∈ [0,1], y up), sorted by x.
  final List<Offset> points;
  final bool fill;
  final List<CurveFlag> flags;

  @override
  void paint(Canvas canvas, Size size) {
    // Baseline axis.
    final axis = Paint()
      ..color = theme.grid
      ..strokeWidth = theme.thinStroke;
    final a0 = mapNorm(const Offset(0, 0), size);
    final a1 = mapNorm(const Offset(1, 0), size);
    canvas.drawLine(a0, a1, axis);

    final pts = points.map((n) => mapNorm(n, size)).toList();
    final rev = revealPolyline(pts, t);

    if (fill) {
      final fillPath = Path.from(rev.path)
        ..lineTo(rev.head.dx, a0.dy)
        ..lineTo(pts.first.dx, a0.dy)
        ..close();
      canvas.drawPath(
        fillPath,
        Paint()..color = theme.accent.withValues(alpha: 0.12),
      );
    }

    canvas.drawPath(
      rev.path,
      Paint()
        ..color = theme.accent
        ..style = PaintingStyle.stroke
        ..strokeWidth = theme.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    // Moving head dot.
    canvas.drawCircle(rev.head, theme.stroke + 1.5, Paint()..color = theme.accent);

    // Annotation flags, revealed as the head passes their x.
    final headXNorm = (rev.head.dx - kAnimPad.left) /
        (size.width - kAnimPad.horizontal);
    for (final f in flags) {
      if (headXNorm + 0.001 < f.atX) continue;
      final y = _yAtX(points, f.atX);
      final at = mapNorm(Offset(f.atX, y), size);
      canvas.drawLine(
        at,
        Offset(at.dx, at.dy - 18),
        Paint()
          ..color = theme.textLow
          ..strokeWidth = theme.thinStroke,
      );
      drawLabel(
        canvas,
        f.label,
        Offset(at.dx, at.dy - 24),
        style: theme.label.copyWith(color: theme.textMed, fontSize: 10),
        align: Alignment.bottomCenter,
      );
    }
  }

  double _yAtX(List<Offset> pts, double x) {
    for (var i = 1; i < pts.length; i++) {
      if (x <= pts[i].dx) {
        final span = pts[i].dx - pts[i - 1].dx;
        final f = span == 0 ? 0.0 : (x - pts[i - 1].dx) / span;
        return pts[i - 1].dy + (pts[i].dy - pts[i - 1].dy) * f;
      }
    }
    return pts.last.dy;
  }

  @override
  bool shouldRepaint(covariant CurveDrawPainter old) =>
      old.t != t || old.points != points;
}
