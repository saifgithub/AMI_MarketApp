/// CR174 §6 — ComparisonBarsPainter: two-to-four labelled horizontal bars on a
/// shared scale, for the lessons whose argument is *this number versus that
/// number*.
///
/// Named in the CR as one of the three measured gaps: only **4%** of the corpus
/// carries a table, and a table is what an author reaches for when two
/// quantities need comparing. A ratio screen, a naive-vs-real risk figure, a
/// count-of-positions against a count-of-bets — all of them are currently prose
/// arithmetic the reader has to hold in their head.
///
/// The bars share one scale by construction ([maxValue] is set once for the
/// whole set), because two bars drawn to their own scales are the classic way to
/// make a chart lie: the shorter bar looks longer and the comparison the picture
/// exists to make is inverted.
library;

import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/paint_utils.dart';
import 'package:flutter/material.dart';

class ComparisonBar {
  const ComparisonBar({
    required this.label,
    required this.value,
    required this.display,
    this.muted = false,
  });

  final String label;
  final double value;

  /// The value as the learner should read it (`'4.6%'`, `'1.1 bets'`). Kept
  /// separate from [value] so the bar's *length* and the bar's *caption* cannot
  /// drift into disagreeing.
  final String display;

  /// Draw in grey rather than accent — the reference bar, not the answer.
  final bool muted;
}

class ComparisonBarsPainter extends CustomPainter {
  const ComparisonBarsPainter({
    required this.t,
    required this.theme,
    required this.bars,
    required this.maxValue,
  });

  final double t;
  final AmiAnimTheme theme;
  final List<ComparisonBar> bars;

  /// The shared full-width value. One scale for every bar in the set.
  final double maxValue;

  @override
  void paint(Canvas canvas, Size size) {
    final n = bars.length;
    if (n == 0 || maxValue <= 0) return;

    final left = mapNorm(const Offset(0, 0), size).dx;
    final right = mapNorm(const Offset(1, 0), size).dx;
    final top = mapNorm(const Offset(0, 1), size).dy;
    final bottom = mapNorm(const Offset(0, 0), size).dy;

    final slot = (bottom - top) / n;
    final barH = (slot * 0.34).clamp(8.0, 26.0);
    final track = right - left;

    for (var i = 0; i < n; i++) {
      final b = bars[i];
      final cy = top + slot * (i + 0.5);
      final w = track * (b.value / maxValue).clamp(0.0, 1.0) * t;

      drawLabel(
        canvas,
        b.label,
        Offset(left, cy - barH / 2 - 4),
        style: theme.label.copyWith(color: theme.textMed, fontSize: 10),
        align: Alignment.bottomLeft,
        maxWidth: track,
      );

      canvas.drawRect(
        Rect.fromLTWH(left, cy - barH / 2, track, barH),
        Paint()..color = theme.surface,
      );
      canvas.drawRect(
        Rect.fromLTWH(left, cy - barH / 2, w, barH),
        Paint()
          ..color = b.muted
              ? theme.textLow.withValues(alpha: 0.5)
              : theme.accent,
      );
      drawLabel(
        canvas,
        b.display,
        Offset(left + w + 6, cy),
        style: theme.label.copyWith(
          color: b.muted ? theme.textMed : theme.textHigh,
          fontSize: 11,
        ),
        align: Alignment.centerLeft,
        maxWidth: track,
      );
    }
  }

  @override
  bool shouldRepaint(covariant ComparisonBarsPainter old) =>
      old.t != t || old.bars != bars || old.maxValue != maxValue;
}
