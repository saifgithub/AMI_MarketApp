/// CR109 slice 3 — the Close's replayed NAV curve.
///
/// Design §10.2 beat 1: "rank, career-point delta, the curve replayed."
/// CR134's motion rule: "ceremony motion is a bounded ≤600ms one-time
/// draw-on, ... removed entirely under [reduced motion] ... never
/// continuous, never on a counter tick, never on a stat that only
/// updates." This widget plays a single left-to-right reveal wipe once per
/// mount and never repeats — a ceremony, not a loading spinner.
///
/// Same painter idiom as `widgets/portfolio_equity_chart.dart`'s
/// `_EquityCurvePainter`: a dashed segment AND a filled tick mark every
/// point whose `price_source` is not `live` (CR040/CR134 — "a dimmed mark
/// reads as absent, not small," so provenance is pattern, never opacity).
/// These are the Close's "markers." No touch-drag crosshair here — this is
/// a replay, not an explorable chart, so that interaction is deliberately
/// left out.
library;

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Bounded per CR134's ceremony-motion rule — never continuous.
const Duration kGamesCloseCurveRevealDuration = Duration(milliseconds: 600);

class GamesCloseCurve extends StatefulWidget {
  const GamesCloseCurve({
    super.key,
    required this.points,
    this.height = 132,
    this.color = AmiColors.hexCyan,
  });

  final List<GameNavPoint> points;
  final double height;
  final Color color;

  @override
  State<GamesCloseCurve> createState() => _GamesCloseCurveState();
}

class _GamesCloseCurveState extends State<GamesCloseCurve>
    with SingleTickerProviderStateMixin {
  late final AnimationController _reveal = AnimationController(
    vsync: this,
    duration: kGamesCloseCurveRevealDuration,
  );

  @override
  void initState() {
    super.initState();
    // One-time draw-on: fires once when this State is first created. A
    // later rebuild (e.g. a provider refresh with the same points) does
    // NOT replay it — only a fresh mount would, which the Close screen
    // never triggers mid-session. Never `.repeat()` — that would be exactly
    // the continuous motion CR134 rules out.
    _reveal.forward();
  }

  @override
  void dispose() {
    _reveal.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final points = List<GameNavPoint>.of(widget.points)
      ..sort((a, b) => a.asOfDate.compareTo(b.asOfDate));
    if (points.length < 2) {
      // Degrades to empty space rather than a flat/zero line — same
      // "never fabricate a curve" posture as portfolio_equity_chart.dart.
      return SizedBox(height: widget.height);
    }
    return AnimatedBuilder(
      animation: _reveal,
      builder: (_, __) => SizedBox(
        height: widget.height,
        width: double.infinity,
        child: CustomPaint(
          painter: _CloseCurvePainter(
            points: points,
            color: widget.color,
            revealFraction: Curves.easeOut.transform(_reveal.value),
          ),
        ),
      ),
    );
  }
}

double _yForNav(double nav, double minNav, double maxNav, double height) {
  if (maxNav <= minNav) return height / 2;
  return height - ((nav - minNav) / (maxNav - minNav)) * height;
}

double _xForIndex(int i, int count, double width) {
  if (count <= 1) return width / 2;
  return (i / (count - 1)) * width;
}

/// Manual dash stepper — same primitive as portfolio_equity_chart.dart's
/// (no `path_drawing` dependency in this project).
void _drawDashedLine(
  Canvas canvas,
  Offset from,
  Offset to,
  Paint paint, {
  double dashLength = 4,
  double gapLength = 3,
}) {
  final total = (to - from).distance;
  if (total == 0) return;
  final direction = (to - from) / total;
  var covered = 0.0;
  var start = from;
  while (covered < total) {
    final reachedEnd = covered + dashLength >= total;
    final dashEnd = reachedEnd ? to : start + direction * dashLength;
    canvas.drawLine(start, dashEnd, paint);
    covered += dashLength + gapLength;
    start = dashEnd + direction * gapLength;
  }
}

class _CloseCurvePainter extends CustomPainter {
  _CloseCurvePainter({
    required this.points,
    required this.color,
    required this.revealFraction,
  });

  final List<GameNavPoint> points;
  final Color color;
  final double revealFraction;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2 || revealFraction <= 0) return;

    canvas.save();
    // The one-time draw-on wipe: clip to the revealed fraction of width.
    canvas.clipRect(Rect.fromLTWH(0, 0, size.width * revealFraction, size.height));

    final minNav = points.map((p) => p.nav).reduce((a, b) => a < b ? a : b);
    final maxNav = points.map((p) => p.nav).reduce((a, b) => a > b ? a : b);
    final offsets = [
      for (var i = 0; i < points.length; i++)
        Offset(
          _xForIndex(i, points.length, size.width),
          _yForNav(points[i].nav, minNav, maxNav, size.height),
        ),
    ];

    final fillPath = Path()..moveTo(offsets.first.dx, size.height);
    for (final o in offsets) {
      fillPath.lineTo(o.dx, o.dy);
    }
    fillPath.lineTo(offsets.last.dx, size.height);
    fillPath.close();
    canvas.drawPath(
      fillPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withValues(alpha: 0.25),
            color.withValues(alpha: 0.02),
          ],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );

    final linePaint = Paint()
      ..color = color
      ..strokeWidth = 2.2
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < offsets.length - 1; i++) {
      final segmentLive = points[i].isLive && points[i + 1].isLive;
      if (segmentLive) {
        canvas.drawLine(offsets[i], offsets[i + 1], linePaint);
      } else {
        _drawDashedLine(canvas, offsets[i], offsets[i + 1], linePaint);
      }
    }

    // Provenance markers — full colour, full opacity, pattern only.
    final tickPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    for (var i = 0; i < points.length; i++) {
      if (!points[i].isLive) {
        canvas.drawCircle(offsets[i], 3.0, tickPaint);
      }
    }

    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _CloseCurvePainter old) =>
      old.points != points ||
      old.revealFraction != revealFraction ||
      old.color != color;
}
