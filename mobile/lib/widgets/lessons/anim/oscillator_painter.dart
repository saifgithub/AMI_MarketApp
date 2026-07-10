/// CR013 (E3/D1) — OscillatorPainter: a main series with a lagging companion
/// (trailing moving average) and an optional 30/70 band. Powers rsi_oscillator
/// (band on) and moving_average_lag (companion lags the price).
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class OscillatorPainter extends CustomPainter {
  const OscillatorPainter({
    required this.t,
    required this.theme,
    required this.series,
    this.companionWindow = 0,
    this.band = false,
  });

  final double t;
  final AmiAnimTheme theme;

  /// Evenly-spaced normalized samples (y ∈ [0,1]).
  final List<double> series;

  /// Trailing moving-average window (0 = no companion line).
  final int companionWindow;
  final bool band;

  @override
  void paint(Canvas canvas, Size size) {
    final n = series.length;
    if (n < 2) return;

    if (band) {
      final top = mapNorm(const Offset(0, 0.7), size).dy;
      final bot = mapNorm(const Offset(0, 0.3), size).dy;
      final l = mapNorm(const Offset(0, 0), size).dx;
      final r = mapNorm(const Offset(1, 0), size).dx;
      canvas.drawRect(
        Rect.fromLTRB(l, top, r, bot),
        Paint()..color = theme.accent.withValues(alpha: 0.07),
      );
      for (final level in const [0.3, 0.7]) {
        final y = mapNorm(Offset(0, level), size).dy;
        canvas.drawLine(Offset(l, y), Offset(r, y),
            Paint()..color = theme.grid..strokeWidth = theme.thinStroke);
      }
    }

    Offset at(int i, double v) => mapNorm(Offset(i / (n - 1), v), size);

    // Companion (trailing MA) — draw under the main line, faded.
    if (companionWindow > 1) {
      final comp = <Offset>[];
      for (var i = 0; i < n; i++) {
        final lo = (i - companionWindow + 1).clamp(0, i);
        var sum = 0.0;
        for (var j = lo; j <= i; j++) {
          sum += series[j];
        }
        comp.add(at(i, sum / (i - lo + 1)));
      }
      final rev = revealPolyline(comp, t);
      canvas.drawPath(
        rev.path,
        Paint()
          ..color = AmiColors.hexPurple.withValues(alpha: 0.7)
          ..style = PaintingStyle.stroke
          ..strokeWidth = theme.thinStroke + 1
          ..strokeCap = StrokeCap.round,
      );
    }

    // Main series.
    final main = [for (var i = 0; i < n; i++) at(i, series[i])];
    final rev = revealPolyline(main, t);
    canvas.drawPath(
      rev.path,
      Paint()
        ..color = theme.accent
        ..style = PaintingStyle.stroke
        ..strokeWidth = theme.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawCircle(rev.head, theme.stroke + 1, Paint()..color = theme.accent);
  }

  @override
  bool shouldRepaint(covariant OscillatorPainter old) =>
      old.t != t || old.series != series || old.band != band;
}
