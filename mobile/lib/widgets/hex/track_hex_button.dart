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
          final w = constraints.maxWidth;
          final donutSize = h * 0.52;
          // The DEF082 palette is optimised for separation *between* hexes, so
          // it admits a token too dark to set type in (hexIndigo600, 2.8:1).
          // Fill keeps the true brand colour; foreground marks get the lift.
          final ink = readableOnCanvas(color);
          // CR108: a long label used to shrink instead of wrap — the only
          // label in the app that got SMALLER at a bigger text scale. Measure
          // whether it fits one line at the raised 10px cap inside the
          // one-line box (0.724 x W); if not, wrap to two lines sized against
          // the narrower top-line box (0.676 x W) instead of the single-line
          // one, or the second line would run under the diagonal exactly as
          // the shrink-only version did.
          //
          // Round 2 (DEF142 audit): a `FittedBox` always lays its child out
          // with UNBOUNDED constraints before scaling the result, so a
          // `Text` inside one can never wrap — `softWrap`/`maxLines: 2` had
          // no width to break against. The two-line branch below therefore
          // gives the `Text` its width from a plain `SizedBox`, not a
          // `FittedBox`, so real line breaks can happen; `FittedBox` is kept
          // only for the single-line branch, where it did already work
          // (that half of the mechanism was never the bug).
          final oneLineBox = w * flatTopHexWidthFractionAtLabel;
          final twoLineBox = w * flatTopHexWidthFractionAtTwoLineLabel;
          final labelStyle =
              AmiTypography.labelMono.copyWith(fontSize: 10, color: ink);
          final singleLineMeasure = TextPainter(
            text: TextSpan(text: label, style: labelStyle),
            maxLines: 1,
            textDirection: TextDirection.ltr,
          )..layout(maxWidth: double.infinity);
          var needsTwoLines = singleLineMeasure.width > oneLineBox;
          if (needsTwoLines) {
            // Confirm the wrap actually produces two lines that each fit the
            // two-line box, rather than assuming a candidate wraps. A single
            // unbreakable word (`FUNDAMENTALS`, 12 characters, no space) has
            // no break opportunity: constrained layout still reports it as
            // one line whose natural width is the whole word, wider than the
            // box. That case is decided explicitly here — it is not a wrap,
            // so it falls back to the single-line branch and scales down
            // instead, the same way any long single-line label always did.
            final wrapMeasure = TextPainter(
              text: TextSpan(text: label, style: labelStyle),
              maxLines: 2,
              textDirection: TextDirection.ltr,
            )..layout(maxWidth: twoLineBox);
            final lines = wrapMeasure.computeLineMetrics();
            needsTwoLines = !wrapMeasure.didExceedMaxLines &&
                lines.length > 1 &&
                lines.every((line) => line.width <= twoLineBox + 0.5);
          }
          final labelBox = needsTwoLines ? twoLineBox : oneLineBox;
          return ClipPath(
            clipper: const FlatTopRegularHexagon(),
            child: Container(
              color: color.withValues(alpha: 0.15),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: labelBox,
                    child: needsTwoLines
                        // A confirmed wrap already fits within labelBox at
                        // the base font — it never needs to shrink, unlike
                        // the old single-line-only version.
                        ? Text(
                            label,
                            maxLines: 2,
                            softWrap: true,
                            textAlign: TextAlign.center,
                            style: labelStyle,
                          )
                        // Single line, possibly an unbreakable word wider
                        // than its box: absorb the user's text-scale setting
                        // by scaling down, never below its own base, unlike
                        // the old single-line FittedBox, which is exactly
                        // how `ISLAMIC FINANCE` used to shrink under a
                        // larger text scale instead of growing.
                        : FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              label,
                              maxLines: 1,
                              softWrap: false,
                              textAlign: TextAlign.center,
                              style: labelStyle,
                            ),
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
