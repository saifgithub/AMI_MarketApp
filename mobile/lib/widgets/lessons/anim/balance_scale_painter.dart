/// CR013 (E3/D1) — BalanceScalePainter: a two-pan scale settles toward its
/// weight ratio as both sides count up. Powers position_size_calc (balances)
/// and risk_reward_scale (settles at the reward-heavy ratio).
library;

import 'dart:math' as math;

import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class BalanceScalePainter extends CustomPainter {
  const BalanceScalePainter({
    required this.t,
    required this.theme,
    required this.leftLabel,
    required this.leftValue,
    required this.rightLabel,
    required this.rightValue,
  });

  final double t;
  final AmiAnimTheme theme;
  final String leftLabel;
  final double leftValue;
  final String rightLabel;
  final double rightValue;

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final pivotY = size.height * 0.32;
    final beamHalf = size.width * 0.33;

    // Final tilt from the weight ratio; +angle tips the heavier side down.
    final total = (leftValue + rightValue).abs();
    final ratio = total == 0 ? 0.0 : (rightValue - leftValue) / total;
    final angle = ratio.clamp(-1.0, 1.0) * 0.28 * t; // radians, eased in via t

    final stroke = Paint()
      ..color = theme.accent
      ..strokeWidth = theme.stroke
      ..strokeCap = StrokeCap.round;
    final metal = Paint()
      ..color = theme.grid
      ..strokeWidth = theme.thinStroke;

    // Central column + fulcrum triangle.
    canvas.drawLine(Offset(cx, pivotY), Offset(cx, size.height * 0.88), metal);
    final tri = Path()
      ..moveTo(cx, pivotY)
      ..lineTo(cx - 12, pivotY + 18)
      ..lineTo(cx + 12, pivotY + 18)
      ..close();
    canvas.drawPath(tri, Paint()..color = theme.grid);

    // Beam.
    final dx = math.cos(angle) * beamHalf;
    final dy = math.sin(angle) * beamHalf;
    final leftEnd = Offset(cx - dx, pivotY - dy);
    final rightEnd = Offset(cx + dx, pivotY + dy);
    canvas.drawLine(leftEnd, rightEnd, stroke);

    _pan(canvas, leftEnd, leftLabel, leftValue * t, theme);
    _pan(canvas, rightEnd, rightLabel, rightValue * t, theme);
  }

  void _pan(Canvas canvas, Offset at, String label, double value,
      AmiAnimTheme theme) {
    const drop = 26.0;
    final panY = at.dy + drop;
    canvas.drawLine(
      at,
      Offset(at.dx, panY),
      Paint()
        ..color = theme.grid
        ..strokeWidth = theme.thinStroke,
    );
    final pan = Rect.fromCenter(
        center: Offset(at.dx, panY + 4), width: 46, height: 10);
    canvas.drawArc(pan, 0, math.pi, false,
        Paint()..color = theme.accent..style = PaintingStyle.stroke..strokeWidth = theme.stroke);
    drawLabel(
      canvas,
      '$label\n${value.round()}',
      Offset(at.dx, panY + 20),
      style: theme.label.copyWith(color: theme.textMed, fontSize: 10),
      align: Alignment.topCenter,
      maxWidth: 90,
    );
  }

  @override
  bool shouldRepaint(covariant BalanceScalePainter old) =>
      old.t != t ||
      old.leftValue != leftValue ||
      old.rightValue != rightValue;
}
