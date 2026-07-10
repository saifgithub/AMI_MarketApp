/// CR013 (E3/D1) — ConstellationPainter: 12 role-coloured hexes fly in from the
/// edges into a honeycomb ring around the Concierge (pink), which lands last;
/// connecting lines glow as the formation completes. Powers ami_constellation
/// (also reusable as the Room-open moment). Content-agnostic — no params.
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class ConstellationPainter extends CustomPainter {
  const ConstellationPainter({required this.t, required this.theme});

  final double t;
  final AmiAnimTheme theme;

  static const List<Color> _familyColors = [
    AmiColors.hexCyan,
    AmiColors.hexAmber,
    AmiColors.hexGreen,
    AmiColors.hexPurple,
    AmiColors.hexBlue,
    AmiColors.hexCyan,
    AmiColors.hexAmber,
    AmiColors.hexGreen,
    AmiColors.hexPurple,
    AmiColors.hexBlue,
    AmiColors.hexCyan,
    AmiColors.hexGreen,
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height * 0.46);
    final ring = size.height * 0.30;
    final hexR = size.height * 0.075;

    // Formation slots for the 12 agents.
    final slots = <Offset>[
      for (var i = 0; i < 12; i++)
        center +
            Offset(
              ring * math.cos(math.pi / 6 * i),
              ring * math.sin(math.pi / 6 * i),
            ),
    ];

    // Glow lines from the centre once the ring is nearly formed.
    final glow = stageT(t, 0.78, 1.0);
    if (glow > 0) {
      final linePaint = Paint()
        ..color = AmiColors.hexBlue.withValues(alpha: 0.10 + 0.25 * glow)
        ..strokeWidth = theme.thinStroke;
      for (final s in slots) {
        canvas.drawLine(center, s, linePaint);
      }
    }

    // Agents fly in radially, staggered.
    for (var i = 0; i < 12; i++) {
      final p = Curves.easeOutCubic
          .transform(stageT(t, i * 0.045, i * 0.045 + 0.4));
      final start = center + (slots[i] - center) * 3.2;
      final pos = Offset.lerp(start, slots[i], p)!;
      _hex(canvas, pos, hexR, _familyColors[i], p);
    }

    // Concierge lands last, from below, into the centre.
    final cp = Curves.easeOutBack.transform(stageT(t, 0.62, 0.92));
    final cStart = Offset(center.dx, size.height * 1.8);
    _hex(canvas, Offset.lerp(cStart, center, cp)!, hexR * 1.15,
        AmiColors.hexPink, cp);
  }

  void _hex(Canvas canvas, Offset c, double r, Color color, double appear) {
    if (appear <= 0) return;
    final a = appear.clamp(0.0, 1.0);
    final path = Path();
    for (var i = 0; i < 6; i++) {
      final ang = math.pi / 6 + math.pi / 3 * i;
      final pt = Offset(c.dx + r * math.cos(ang), c.dy + r * math.sin(ang));
      i == 0 ? path.moveTo(pt.dx, pt.dy) : path.lineTo(pt.dx, pt.dy);
    }
    path.close();
    canvas.drawPath(path, Paint()..color = color.withValues(alpha: 0.18 * a));
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withValues(alpha: a)
        ..style = PaintingStyle.stroke
        ..strokeWidth = theme.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant ConstellationPainter old) => old.t != t;
}
