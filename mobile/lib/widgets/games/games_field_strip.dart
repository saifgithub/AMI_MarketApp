/// CR109 — the field, drawn as a race rather than listed as a table.
///
/// Saiful, on the shipped board: *"In the standing page, it is so very
/// boring."* He was right, and the reason is diagnosable rather than a matter
/// of taste: every number on that screen had to be READ. "3rd of 6" and
/// "+1.2%" tell a player their position but nothing about the *shape* of the
/// race — whether second place is a nudge or a canyon away, whether the pack
/// is bunched or strung out, whether the leader is running away with it.
/// That information is already in the data and was simply never drawn.
///
/// This strip is one axis carrying every measured entrant as a mark. It
/// answers "where is everyone" in a glance, which no ordered list can.
///
/// **The rules it obeys are the board's, not this widget's own:**
///
///   * **Percentages only.** §6.1 — no entrant's AMI Cash is ever rendered
///     for anyone. The axis is TWR and there is no currency in this file.
///   * **An unmeasured entrant gets NO MARK.** Not a mark at zero, not a
///     faint one. A run with no completed close has not been measured, and
///     placing it on the axis anywhere would be an assertion about where it
///     stands. It is reported by count instead, in words.
///   * **Provenance and emphasis are never opacity.** `data_viz_and_meters`
///     rules that out by name — *"a dimmed mark reads as absent, not
///     small"* — which on a board is precisely the wrong reading, since
///     absent is a state this board really has. Emphasis is SIZE and
///     STROKE; the desk marks are hollow, yours is filled and larger.
///   * **Hex geometry is for marks.** The app reserves it for marks and
///     controls, not panels (CR109 Amendment E). An entrant is a mark, so
///     each one is a small flat-topped hexagon.
///
/// **Zero is drawn whenever it falls inside the range**, because "everyone
/// is up" and "everyone is down" are different races and an axis without its
/// origin hides which one this is.
library;

import 'dart:math' as math;

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class GamesFieldStrip extends StatelessWidget {
  const GamesFieldStrip({
    super.key,
    required this.rows,
    this.height = 76,
  });

  final List<GameBoardRow> rows;
  final double height;

  /// Entrants that can be placed on an axis at all.
  List<GameBoardRow> get _measured =>
      rows.where((r) => r.twrPct != null).toList();

  @override
  Widget build(BuildContext context) {
    final measured = _measured;
    // One measured entrant is not a race, and a strip of a single mark
    // implies a spread that does not exist. The list below says it better.
    if (measured.length < 2) return const SizedBox.shrink();

    return SizedBox(
      height: height,
      child: CustomPaint(
        painter: _FieldStripPainter(measured: measured),
        size: Size.infinite,
      ),
    );
  }
}

class _FieldStripPainter extends CustomPainter {
  _FieldStripPainter({required this.measured});

  final List<GameBoardRow> measured;

  /// Half-width of an entrant mark. The hexagons are drawn to this, and the
  /// axis is inset by it so a leader at the extreme is not clipped.
  static const double _markR = 7.0;
  static const double _axisY = 0.62;

  @override
  void paint(Canvas canvas, Size size) {
    final values = measured.map((r) => r.twrPct!).toList()..sort();
    var lo = values.first;
    var hi = values.last;

    // A dead-flat field would divide by zero and, worse, would place every
    // entrant at the same point while implying an axis. Give it a nominal
    // span so the marks separate visually and the labels still read true.
    if ((hi - lo).abs() < 1e-9) {
      lo -= 0.5;
      hi += 0.5;
    }

    final left = _markR + 2;
    final right = size.width - _markR - 2;
    final axisY = size.height * _axisY;
    double x(double twr) => left + ((twr - lo) / (hi - lo)) * (right - left);

    final axis = Paint()
      ..color = AmiColors.slate700
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(left, axisY), Offset(right, axisY), axis);

    // ── Zero, when it is inside the range. "Everyone is up" and "everyone
    // is down" are different races; an axis without its origin hides which.
    if (lo < 0 && hi > 0) {
      final zx = x(0);
      final zero = Paint()
        ..color = AmiColors.textLow
        ..strokeWidth = 1.0;
      // Dashed, so it never reads as an entrant.
      const dash = 3.0;
      for (double y = axisY - 12; y < axisY + 12; y += dash * 2) {
        canvas.drawLine(Offset(zx, y), Offset(zx, y + dash), zero);
      }
      _label(canvas, '0%', Offset(zx, axisY + 16),
          AmiColors.textLow, 9, TextAlign.center);
    }

    // ── Entrant marks. Drawn worst-first so the leader, and YOU, land on
    // top of the pile rather than under it.
    final ordered = [...measured]
      ..sort((a, b) => (a.twrPct!).compareTo(b.twrPct!));
    for (final row in ordered) {
      if (row.isYou) continue; // drawn last, on top
      _mark(canvas, Offset(x(row.twrPct!), axisY), row, emphasised: false);
    }
    final you = measured.where((r) => r.isYou).toList();
    for (final row in you) {
      _mark(canvas, Offset(x(row.twrPct!), axisY), row, emphasised: true);
    }

    // ── Endpoint labels. The two numbers that bound the race.
    _label(canvas, _pct(lo), Offset(left, axisY - 26),
        AmiColors.textLow, 10, TextAlign.left);
    _label(canvas, _pct(hi), Offset(right, axisY - 26),
        AmiColors.textLow, 10, TextAlign.right);
  }

  /// One entrant, as a flat-topped hexagon — the app's mark geometry.
  ///
  /// A desk is HOLLOW and a human is FILLED: a shape difference, not a
  /// tint, so it survives both themes and does not lean on colour to carry
  /// the disclosure §11.2 requires.
  void _mark(Canvas canvas, Offset c, GameBoardRow row,
      {required bool emphasised}) {
    final twr = row.twrPct!;
    final colour = row.isYou
        ? AmiColors.hexCyan
        : (twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed);
    final r = emphasised ? _markR + 2.5 : _markR;

    final path = Path();
    for (var i = 0; i < 6; i++) {
      final a = math.pi / 3 * i;
      final p = Offset(c.dx + r * math.cos(a), c.dy + r * 0.866 * math.sin(a));
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    path.close();

    if (row.isDesk) {
      canvas.drawPath(
        path,
        Paint()
          ..color = colour
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6,
      );
    } else {
      canvas.drawPath(path, Paint()..color = colour);
    }

    // Your own mark gets a ring as well as the size bump — two channels, so
    // it is findable at a glance in a crowded field.
    if (emphasised) {
      canvas.drawPath(
        path,
        Paint()
          ..color = AmiColors.textHigh
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5,
      );
    }
  }

  static String _pct(double v) =>
      '${v >= 0 ? '+' : ''}${v.toStringAsFixed(2)}%';

  void _label(Canvas canvas, String text, Offset at, Color colour,
      double size, TextAlign align) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: colour,
          fontSize: size,
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      ),
      textAlign: align,
      textDirection: TextDirection.ltr,
    )..layout();
    final dx = switch (align) {
      TextAlign.right => at.dx - tp.width,
      TextAlign.center => at.dx - tp.width / 2,
      _ => at.dx,
    };
    tp.paint(canvas, Offset(dx, at.dy));
  }

  @override
  bool shouldRepaint(covariant _FieldStripPainter old) =>
      old.measured != measured;
}
