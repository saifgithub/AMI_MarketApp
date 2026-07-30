/// Clip-path geometry for AMI's angled shapes. **Two of the three are not
/// hexagons, and until CR117 all three were named as if they were.**
///
///   - [CutCornerOctagonClipper]: an **eight**-sided cut-corner rectangle —
///     angled ends *and* angled top and bottom. Used by [HexChip],
///     [GlassPanel] accents, the bottom nav, toasts.
///   - [FlatTopHexagonBarClipper]: a **true** flat-top hexagon at any aspect
///     ratio — angled ends, flat top and bottom. For rect-proportioned
///     controls: segmented bars, wide pills.
///   - [FlatTopRegularHexagon]: a true flat-top *regular* hexagon, locked to
///     the 2:√3 bounding box. Agent avatars, the honeycomb.
///
/// **CR117 — why the rename, and why the new class did not simply inherit the
/// vacated name.** `FlatTopHexagonClipper` used to be the octagon, and its own
/// docstring admitted it: *"Cut-corner octagon — what the design system spec
/// calls a 'hex clip-path'"*. It misled every reader since it was written,
/// including CR106's spec work, which reasoned about "hex geometry" on
/// controls that have none. Saiful found it from the outside, on the
/// ticker-period toggle: *"the buttons are octagonal, not hexagonal."*
///
/// The true hexagon could have taken over the freed name — it is, after all,
/// what the name always claimed. It deliberately does not. Had it, any call
/// site not migrated, or written in a lane in flight, would keep compiling and
/// **silently change shape**. Because `FlatTopHexagonClipper` now names
/// nothing at all, a stale reference is a **compile error instead of a wrong
/// shape**. That is CLAUDE.md's degrade-loudly rule applied to a rename.
library;

import 'package:flutter/material.dart';

/// Cut-corner **octagon**. Angled corners on all four sides.
///
/// This is what the AMI design-system spec loosely calls a "hex clip-path",
/// and it is the shape most AMI controls have always had. It is not a mistake
/// to be swept away — it has shipped for months and reads as intentional
/// (CR117 explicitly declines to migrate on tidiness). It is only a mistake
/// when something needs *six* sides and reaches for this.
class CutCornerOctagonClipper extends CustomClipper<Path> {
  const CutCornerOctagonClipper({this.cornerCut = 10.0});

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
  bool shouldReclip(covariant CutCornerOctagonClipper old) =>
      cornerCut != old.cornerCut;
}

/// A **true flat-top hexagon** that stretches to any aspect ratio: angled left
/// and right ends, flat top and bottom, six sides.
///
/// This is the shape the AT:Designer specified for the BOARD|TRANSCRIPT
/// toggle (DEF146) and it is **not producible** by [CutCornerOctagonClipper]
/// at any `cornerCut` — that one always cuts the top and bottom too.
/// [FlatTopRegularHexagon] cannot do it either: its diagonals start at a fixed
/// `w * 0.25`, so on a wide bar the angle flattens out into a near-triangle.
/// Hence a third class rather than a parameter on either.
///
/// [endInset] is how far in from each end the flat top begins, in logical
/// pixels. It is clamped to half the width, so an inset wider than the box
/// degrades to a pointed lozenge rather than an inverted path.
class FlatTopHexagonBarClipper extends CustomClipper<Path> {
  const FlatTopHexagonBarClipper({this.endInset = 10.0});

  final double endInset;

  @override
  Path getClip(Size size) {
    final double w = size.width;
    final double h = size.height;
    final double i = endInset.clamp(0.0, w / 2);

    return Path()
      ..moveTo(i, 0)
      ..lineTo(w - i, 0)
      ..lineTo(w, h * 0.5) // the point, at the vertical middle
      ..lineTo(w - i, h)
      ..lineTo(i, h)
      ..lineTo(0, h * 0.5)
      ..close();
  }

  @override
  bool shouldReclip(covariant FlatTopHexagonBarClipper old) =>
      endInset != old.endInset;
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
