/// Large tinted hex button for the lessons landing hex cluster.
///
/// Renders the track label, a doughnut progress ring, and a 15%-alpha
/// accent fill using [FlatTopRegularHexagon] — the same geometry as
/// agent avatars on the Floor home screen.
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

class TrackHexButton extends StatelessWidget {
  const TrackHexButton({
    super.key,
    required this.label,
    required this.color,
    required this.completed,
    required this.total,
    required this.onTap,
  });

  final String label;
  final Color color;
  final int completed;
  final int total;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final h = constraints.maxHeight;
          final donutSize = h * 0.52;
          // The DEF082 palette is optimised for separation *between* hexes, so
          // it admits a token too dark to set type in (hexIndigo600, 2.8:1).
          // Fill keeps the true brand colour; foreground marks get the lift.
          final ink = readableOnCanvas(color);
          return ClipPath(
            clipper: const FlatTopRegularHexagon(),
            child: Container(
              color: color.withValues(alpha: 0.15),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                    style: AmiTypography.labelMono.copyWith(
                      fontSize: 8,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 4),
                  SizedBox(
                    width: donutSize,
                    height: donutSize,
                    child: CustomPaint(
                      painter: _DoughnutPainter(
                        color: ink,
                        fraction: total == 0
                            ? 0
                            : (completed / total).clamp(0.0, 1.0),
                      ),
                      child: Center(
                        child: Text(
                          '$completed/$total',
                          style: AmiTypography.labelMono.copyWith(
                            fontSize: 9,
                            color: AmiColors.textHigh,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _DoughnutPainter extends CustomPainter {
  const _DoughnutPainter({required this.color, required this.fraction});

  final Color color;
  final double fraction;

  static const double _strokeWidth = 8.0;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - _strokeWidth / 2;

    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..color = AmiColors.slate700
        ..style = PaintingStyle.stroke
        ..strokeWidth = _strokeWidth,
    );

    if (fraction > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        -math.pi / 2,
        fraction * 2 * math.pi,
        false,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = _strokeWidth
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _DoughnutPainter old) =>
      color != old.color || fraction != old.fraction;
}
