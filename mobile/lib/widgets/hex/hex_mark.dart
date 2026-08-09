/// A small true-hexagon badge — CR109 slice 3's rank/result/PR marks.
///
/// CR134's design conformance review found **zero hexagons across 20 mocked
/// game screens** ("hex geometry for marks and controls — reuse
/// `mobile/lib/widgets/hex/`... do not repeat that"). [FlatTopRegularHexagon]
/// (`theme/hex_clipper.dart`) is the actual six-sided shape; this widget is
/// just the small chrome (fill/border/child) wrapped around it, extracted
/// because the Close's result mark and the Record's PR-board badges both
/// need the same small hex — see `screens/games/games_close_screen.dart`
/// and `screens/games/games_record_screen.dart`.
library;

import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

class HexMark extends StatelessWidget {
  const HexMark({
    super.key,
    required this.color,
    required this.child,
    this.size = 56,
    this.fillAlpha = 0.16,
  });

  /// Border colour and (at [fillAlpha]) fill colour.
  final Color color;

  /// Centred content — a short text run or a small icon.
  final Widget child;

  /// Width in logical pixels; height follows the regular hex's fixed
  /// aspect ratio ([flatTopRegularHexagonAspectRatio]).
  final double size;

  final double fillAlpha;

  @override
  Widget build(BuildContext context) {
    final height = size / flatTopRegularHexagonAspectRatio;
    return SizedBox(
      width: size,
      height: height,
      child: ClipPath(
        clipper: const FlatTopRegularHexagon(),
        child: Container(
          decoration: BoxDecoration(
            color: color.withValues(alpha: fillAlpha),
            border: Border.all(color: color, width: 1.5),
          ),
          alignment: Alignment.center,
          child: child,
        ),
      ),
    );
  }
}
