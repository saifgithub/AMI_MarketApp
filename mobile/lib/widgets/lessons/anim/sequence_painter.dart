/// CR013 (E3/D1) — SequencePainter: N staged scenes that crossfade. The
/// `escalate` variant grows each step and reddens (revenge_position_escalation);
/// the plain variant alternates a hex label (bull_bear_states).
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class SequencePainter extends CustomPainter {
  const SequencePainter({
    required this.t,
    required this.theme,
    required this.stages,
    this.escalate = false,
  });

  final double t;
  final AmiAnimTheme theme;
  final List<String> stages;
  final bool escalate;

  @override
  void paint(Canvas canvas, Size size) {
    final n = stages.length;
    if (n == 0) return;
    final pos = (t * n).clamp(0.0, n - 1e-6);
    final idx = pos.floor();
    final frac = pos - idx;

    _scene(canvas, size, idx, (1 - frac).clamp(0.0, 1.0));
    if (idx + 1 < n) {
      _scene(canvas, size, idx + 1, frac.clamp(0.0, 1.0));
    }

    // Step pips along the bottom.
    final pipY = size.height - 12;
    final gap = 16.0;
    final startX = size.width / 2 - (n - 1) * gap / 2;
    for (var i = 0; i < n; i++) {
      canvas.drawCircle(
        Offset(startX + i * gap, pipY),
        3,
        Paint()
          ..color = i <= idx ? theme.accent : theme.grid,
      );
    }
  }

  void _scene(Canvas canvas, Size size, int i, double opacity) {
    if (opacity <= 0) return;
    final center = Offset(size.width / 2, size.height * 0.44);
    final grow = escalate ? 1.0 + i * 0.28 : 1.0;
    final radius = size.height * 0.24 * grow;
    final base = escalate
        ? Color.lerp(theme.accent, AmiColors.hexRed,
            stages.length == 1 ? 0.0 : i / (stages.length - 1))!
        : (i.isEven ? AmiColors.hexGreen : AmiColors.hexRed);
    final color = base.withValues(alpha: opacity);

    canvas.drawPath(
      _hex(center, radius),
      Paint()
        ..color = color.withValues(alpha: opacity * 0.16)
        ..style = PaintingStyle.fill,
    );
    canvas.drawPath(
      _hex(center, radius),
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = theme.stroke,
    );
    drawLabel(
      canvas,
      stages[i].toUpperCase(),
      center,
      style: theme.label.copyWith(
          color: theme.textHigh.withValues(alpha: opacity), fontSize: 12),
      maxWidth: radius * 2.4,
    );
  }

  /// Flat-top hexagon path centred at [c].
  Path _hex(Offset c, double r) {
    final p = Path();
    for (var i = 0; i < 6; i++) {
      final a = math.pi / 180 * (60 * i);
      final pt = Offset(c.dx + r * math.cos(a), c.dy + r * math.sin(a));
      i == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
    }
    return p..close();
  }

  @override
  bool shouldRepaint(covariant SequencePainter old) =>
      old.t != t || old.stages != stages || old.escalate != escalate;
}
