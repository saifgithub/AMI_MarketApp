/// CR013 (E3/D1) — CandleAnatomyPainter: one large candle assembles in stages
/// (body → wicks → O/H/L/C callouts). Powers candlestick_anatomy.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class CandleAnatomyPainter extends CustomPainter {
  const CandleAnatomyPainter({
    required this.t,
    required this.theme,
    this.bullish = true,
  });

  final double t;
  final AmiAnimTheme theme;
  final bool bullish;

  @override
  void paint(Canvas canvas, Size size) {
    final color = bullish ? AmiColors.hexGreen : AmiColors.hexRed;
    final cx = size.width * 0.42;
    final bodyW = 46.0;

    // Vertical anatomy (canvas y down): high, open/close body, low.
    final highY = size.height * 0.14;
    final topBody = size.height * 0.32;
    final botBody = size.height * 0.66;
    final lowY = size.height * 0.86;

    final bodyT = stageT(t, 0.0, 0.35);
    final wickT = stageT(t, 0.35, 0.65);
    final labelT = stageT(t, 0.65, 1.0);

    // Body grows from its centre.
    final midBody = (topBody + botBody) / 2;
    final half = (botBody - topBody) / 2 * bodyT;
    final bodyRect = Rect.fromLTRB(
        cx - bodyW / 2, midBody - half, cx + bodyW / 2, midBody + half);
    canvas.drawRRect(
      RRect.fromRectAndRadius(bodyRect, const Radius.circular(3)),
      Paint()..color = color,
    );

    // Wicks extend outward.
    final wickPaint = Paint()
      ..color = color
      ..strokeWidth = theme.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(cx, topBody),
        Offset(cx, topBody - (topBody - highY) * wickT), wickPaint);
    canvas.drawLine(Offset(cx, botBody),
        Offset(cx, botBody + (lowY - botBody) * wickT), wickPaint);

    if (labelT <= 0) return;
    final ls = theme.label.copyWith(
      color: theme.textMed.withValues(alpha: labelT),
      fontSize: 11,
    );
    final tickPaint = Paint()
      ..color = theme.textLow.withValues(alpha: labelT)
      ..strokeWidth = theme.thinStroke;
    void callout(double y, String text) {
      canvas.drawLine(Offset(cx + bodyW / 2 + 4, y),
          Offset(cx + bodyW / 2 + 26, y), tickPaint);
      drawLabel(canvas, text, Offset(cx + bodyW / 2 + 30, y),
          style: ls, align: Alignment.centerLeft, maxWidth: 120);
    }

    callout(highY, 'HIGH');
    callout(topBody, bullish ? 'CLOSE' : 'OPEN');
    callout(botBody, bullish ? 'OPEN' : 'CLOSE');
    callout(lowY, 'LOW');
  }

  @override
  bool shouldRepaint(covariant CandleAnatomyPainter old) =>
      old.t != t || old.bullish != bullish;
}
