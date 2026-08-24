/// CR172 §12 — the expiry payoff diagram.
///
/// A `CustomPainter` over coded primitives, per **D-061**: this project draws
/// its own charts and does not ship Lottie.
///
/// **The curve is the server's, not this file's.** `payoffCurve` arrives as
/// (price, pnl) vertices from `trading_math.option_strategy.payoff_curve` —
/// the same module that produces `max_loss`, `max_gain` and `break_evens`. This
/// widget interpolates between vertices and draws; it computes no payoff of its
/// own. A diagram that disagreed with the figure printed under it would be
/// DEF098's two-renderers shape on the surface where the picture is what the
/// user actually reads.
///
/// **Draws nothing when the server sent no curve.** An axis with no line is a
/// chart that failed, rendered as a chart that is empty (CR040).
library;

import 'dart:math' as math;
import 'dart:ui' show PathMetric;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart' hide TextDirection;

final _axisMoney = NumberFormat('#,##0');

/// The payoff of a structure at [price], interpolated from [curve].
///
/// Exported so a test can assert the interpolation without a widget tree, and
/// so the "is this exact?" question has one answer: between two vertices the
/// true payoff IS linear, so linear interpolation is not an approximation
/// here — it is the function.
double? payoffAt(List<({double price, double pnl})> curve, double price) {
  if (curve.isEmpty) return null;
  if (price <= curve.first.price) return curve.first.pnl;
  if (price >= curve.last.price) return curve.last.pnl;
  for (var i = 0; i < curve.length - 1; i++) {
    final a = curve[i], b = curve[i + 1];
    if (price >= a.price && price <= b.price) {
      final span = b.price - a.price;
      if (span <= 0) return a.pnl;
      return a.pnl + (b.pnl - a.pnl) * ((price - a.price) / span);
    }
  }
  return curve.last.pnl;
}

class OptionPayoffChart extends StatelessWidget {
  const OptionPayoffChart({
    super.key,
    required this.curve,
    this.spot,
    this.breakEvens = const [],
    this.height = 160,
  });

  final List<({double price, double pnl})> curve;
  final double? spot;
  final List<double> breakEvens;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (curve.length < 2) return const SizedBox.shrink();
    return SizedBox(
      height: height,
      width: double.infinity,
      child: CustomPaint(
        painter: _PayoffPainter(
          curve: curve,
          spot: spot,
          breakEvens: breakEvens,
          reduceMotion: MediaQuery.maybeOf(context)?.disableAnimations ?? false,
        ),
      ),
    );
  }
}

class _PayoffPainter extends CustomPainter {
  _PayoffPainter({
    required this.curve,
    required this.spot,
    required this.breakEvens,
    required this.reduceMotion,
  });

  final List<({double price, double pnl})> curve;
  final double? spot;
  final List<double> breakEvens;
  final bool reduceMotion;

  @override
  void paint(Canvas canvas, Size size) {
    const padL = 8.0, padR = 8.0, padT = 10.0, padB = 18.0;
    final plot = Rect.fromLTRB(padL, padT, size.width - padR, size.height - padB);
    if (plot.width <= 0 || plot.height <= 0) return;

    final xs = curve.map((p) => p.price);
    final ys = curve.map((p) => p.pnl);
    final minX = xs.reduce(math.min), maxX = xs.reduce(math.max);
    var minY = ys.reduce(math.min), maxY = ys.reduce(math.max);
    // Always include zero: a payoff chart whose axis excludes break-even is
    // drawing a shape without the line that gives it meaning.
    minY = math.min(minY, 0);
    maxY = math.max(maxY, 0);
    if (maxX <= minX || maxY <= minY) return;
    // A little headroom so the terminal slope does not run along the frame.
    final padY = (maxY - minY) * 0.08;
    minY -= padY;
    maxY += padY;

    double dx(double price) =>
        plot.left + (price - minX) / (maxX - minX) * plot.width;
    double dy(double pnl) =>
        plot.bottom - (pnl - minY) / (maxY - minY) * plot.height;

    final zeroY = dy(0);

    // Zero line — the break-even axis.
    canvas.drawLine(
      Offset(plot.left, zeroY),
      Offset(plot.right, zeroY),
      Paint()
        ..color = AmiColors.slate600
        ..strokeWidth = 1,
    );

    // The curve, split at zero so profit and loss are separately coloured.
    final path = Path()..moveTo(dx(curve.first.price), dy(curve.first.pnl));
    for (var i = 1; i < curve.length; i++) {
      path.lineTo(dx(curve[i].price), dy(curve[i].pnl));
    }

    // Fill above and below zero in the two semantic colours, clipped to each
    // half-plane so a structure that crosses zero reads at a glance.
    for (final (rect, color) in <(Rect, Color)>[
      (Rect.fromLTRB(plot.left, plot.top, plot.right, zeroY),
          AmiColors.hexGreen.withValues(alpha: 0.16)),
      (Rect.fromLTRB(plot.left, zeroY, plot.right, plot.bottom),
          AmiColors.hexRed.withValues(alpha: 0.16)),
    ]) {
      final filled = Path.from(path)
        ..lineTo(dx(curve.last.price), zeroY)
        ..lineTo(dx(curve.first.price), zeroY)
        ..close();
      canvas.save();
      canvas.clipRect(rect);
      canvas.drawPath(filled, Paint()..color = color);
      canvas.restore();
    }

    for (final (rect, color) in <(Rect, Color)>[
      (Rect.fromLTRB(plot.left, plot.top, plot.right, zeroY), AmiColors.hexGreen),
      (Rect.fromLTRB(plot.left, zeroY, plot.right, plot.bottom), AmiColors.hexRed),
    ]) {
      canvas.save();
      canvas.clipRect(rect);
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeJoin = StrokeJoin.round,
      );
      canvas.restore();
    }

    // Spot marker — where the underlying is now, so the diagram is anchored to
    // something the user can see on the rest of the screen.
    final s = spot;
    if (s != null && s >= minX && s <= maxX) {
      _dashedVertical(canvas, dx(s), plot, AmiColors.textLow);
      _label(canvas, _axisMoney.format(s), Offset(dx(s), plot.bottom + 3),
          AmiColors.textLow);
    }

    // Break-evens — the numbers printed beside the chart, drawn on it.
    for (final be in breakEvens) {
      if (be < minX || be > maxX) continue;
      canvas.drawCircle(
        Offset(dx(be), zeroY), 3,
        Paint()..color = AmiColors.hexAmber,
      );
    }
  }

  void _dashedVertical(Canvas canvas, double x, Rect plot, Color color) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    final line = Path()
      ..moveTo(x, plot.top)
      ..lineTo(x, plot.bottom);
    for (final PathMetric m in line.computeMetrics()) {
      var d = 0.0;
      while (d < m.length) {
        canvas.drawPath(m.extractPath(d, math.min(d + 3, m.length)), paint);
        d += 6;
      }
    }
  }

  void _label(Canvas canvas, String text, Offset at, Color color) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: AmiTypography.caption.copyWith(color: color, fontSize: 9),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(at.dx - tp.width / 2, at.dy));
  }

  @override
  bool shouldRepaint(covariant _PayoffPainter old) =>
      old.curve != curve ||
      old.spot != spot ||
      old.breakEvens != breakEvens;
}
