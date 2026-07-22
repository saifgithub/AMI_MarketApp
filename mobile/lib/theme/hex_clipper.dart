/// Hex clip-path geometry for AMI's flat-topped hexagons.
///
/// Two variants:
///   - [FlatTopHexagonClipper]: cut-corner octagon (used for buttons + cards
///     that want the angled-corner look from the AMI design system).
///   - [FlatTopRegularHexagon]: a true flat-topped regular hexagon (used for
///     agent avatars in the honeycomb home).
library;

import 'package:flutter/material.dart';

/// Cut-corner octagon — what the design system spec calls a "hex clip-path".
/// Used for [HexButton], [GlassPanel] accents, hex chips.
class FlatTopHexagonClipper extends CustomClipper<Path> {
  const FlatTopHexagonClipper({this.cornerCut = 10.0});

  /// Length cut off each corner (in logical pixels).
  /// AMI spec: ~10px mobile, ~20px desktop.
  final double cornerCut;

  @override
  Path getClip(Size size) {
    final double w = size.width;
    final double h = size.height;
    final double c = cornerCut.clamp(0.0, [w, h].reduce((a, b) => a < b ? a : b) / 2);

    return Path()
      ..moveTo(c, 0) // top-left of top edge
      ..lineTo(w - c, 0) // top-right of top edge
      ..lineTo(w, c) // diagonal to right side
      ..lineTo(w, h - c)
      ..lineTo(w - c, h) // bottom-right of bottom edge
      ..lineTo(c, h)
      ..lineTo(0, h - c)
      ..lineTo(0, c)
      ..close();
  }

  @override
  bool shouldReclip(covariant FlatTopHexagonClipper old) => cornerCut != old.cornerCut;
}

/// True flat-topped regular hexagon.
/// Used for agent avatars (every hex on the honeycomb home screen).
///
/// Aspect ratio of a flat-topped regular hexagon: width : height = 2 : sqrt(3).
/// Wrap with [AspectRatio] of `2 / sqrt(3)` (~1.155) for correct proportions.
class FlatTopRegularHexagon extends CustomClipper<Path> {
  const FlatTopRegularHexagon();

  @override
  Path getClip(Size size) {
    final double w = size.width;
    final double h = size.height;
    final double qw = w * 0.25; // quarter-width: where the diagonals start

    return Path()
      ..moveTo(qw, 0)
      ..lineTo(w - qw, 0)
      ..lineTo(w, h * 0.5)
      ..lineTo(w - qw, h)
      ..lineTo(qw, h)
      ..lineTo(0, h * 0.5)
      ..close();
  }

  @override
  bool shouldReclip(covariant FlatTopRegularHexagon old) => false;
}

/// Convenience: aspect ratio of a flat-topped regular hexagon.
const double flatTopRegularHexagonAspectRatio = 2.0 / 1.7320508075688772; // 2 / sqrt(3)

/// Width of a [FlatTopRegularHexagon], as a fraction of its bounding box, at a
/// height [yFraction] down from the top.
///
/// The diagonals start a quarter of the way in, so the shape is 0.5x its box at
/// the flat top and only reaches full width at the vertical middle. Anything
/// laid out off-centre must be sized against *this*, not against the box.
double flatTopHexWidthFractionAt(double yFraction) {
  final d = (yFraction.clamp(0.0, 1.0) - 0.5).abs() * 2; // 0 at middle, 1 at top
  return 1.0 - 0.5 * d;
}

/// Where [TrackHexButton] puts its label: centred on ~0.224 of the hex height,
/// above the progress ring. Sizing the label against the bounding box instead
/// left ISLAMIC FINANCE 4.7 pt of headroom at 1.0 text scale and none at 1.15,
/// so the diagonal sliced its ends off.
const double flatTopHexLabelYFraction = 0.224;
final double flatTopHexWidthFractionAtLabel =
    flatTopHexWidthFractionAt(flatTopHexLabelYFraction);
