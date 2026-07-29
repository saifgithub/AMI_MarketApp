/// CR117 / DEF146 — the app's "hexagons" were octagons, and the class name
/// said otherwise.
///
/// `FlatTopHexagonClipper` emitted an **8**-point path while its own docstring
/// read *"Cut-corner octagon — what the design system spec calls a 'hex
/// clip-path'"*. It misled every reader since it was written, including
/// CR106's spec work, which reasoned about "hex geometry" on controls that
/// have none. Saiful found it from the outside: *"the buttons are octagonal,
/// not hexagonal."*
///
/// These tests count sides. A shape test that only checked "it clips
/// something" is what let an octagon ship under a hexagon's name for months,
/// so the assertions here are about the **number of edges and where they are**
/// — the one property the name makes a claim about.
library;

import 'dart:io';
import 'dart:math' as math;

import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Distinct vertices of a straight-line path, in order.
///
/// `computeMetrics`/`Path.getBounds` would tell us the box, not the shape, and
/// the box is identical for all three clippers — which is exactly why the bug
/// was invisible. Sampling the path densely and keeping only the points where
/// direction changes recovers the corner count from the path itself.
List<Offset> _vertices(Path path) {
  final metric = path.computeMetrics().first;
  const samples = 2000;
  // Drop the duplicated end point: on a closed path the last sample IS the
  // first, and the walk below is cyclic. Without this the corner sitting on
  // the seam (the `moveTo` point) is never examined, and every shape comes
  // back one side short — which is how this file first reported an octagon as
  // seven-sided and a hexagon as five.
  final pts = <Offset>[
    for (var i = 0; i < samples; i++)
      metric.getTangentForOffset(metric.length * i / samples)!.position,
  ];

  final corners = <Offset>[];
  for (var i = 0; i < pts.length; i++) {
    final prev = pts[(i - 1 + pts.length) % pts.length];
    final next = pts[(i + 1) % pts.length];
    final a = pts[i] - prev;
    final b = next - pts[i];
    if (a.distance == 0 || b.distance == 0) continue;
    final cross = a.dx * b.dy - a.dy * b.dx;
    final dot = a.dx * b.dx + a.dy * b.dy;
    final turn = math.atan2(cross, dot).abs();
    if (turn > 0.05) {
      // Collapse duplicates from adjacent samples on the same corner,
      // including a pair straddling the seam.
      final dupe = corners.any((c) => (c - pts[i]).distance <= 1.0);
      if (!dupe) corners.add(pts[i]);
    }
  }
  return corners;
}

const _box = Size(200, 40); // a segmented bar: wide, short

void main() {
  group('CR117 — the shapes are what their names say', () {
    test('CutCornerOctagonClipper really has eight corners', () {
      final v = _vertices(const CutCornerOctagonClipper(cornerCut: 8)
          .getClip(_box));
      expect(v.length, 8,
          reason: 'this is the shape that shipped as "FlatTopHexagon" — the '
              'rename is only honest if it is genuinely an octagon');
    });

    test('FlatTopHexagonBarClipper really has six', () {
      final v =
          _vertices(const FlatTopHexagonBarClipper(endInset: 8).getClip(_box));
      expect(v.length, 6);
    });

    test('the hexagon bar has a FLAT top and bottom — the whole difference',
        () {
      // The octagon cuts the top and bottom too. That is the property no
      // `cornerCut` can turn off, and it is why DEF146's design needed a new
      // class rather than a new parameter.
      final hex =
          const FlatTopHexagonBarClipper(endInset: 8).getClip(_box);
      final oct = const CutCornerOctagonClipper(cornerCut: 8).getClip(_box);

      // Walk the top edge; the hexagon stays at y=0 between the insets.
      for (final x in [20.0, 60.0, 100.0, 140.0, 180.0]) {
        expect(hex.contains(Offset(x, 0.5)), isTrue,
            reason: 'hexagon top must be flat at x=$x');
      }
      // The octagon is cut at BOTH ends of the top edge AND down the sides,
      // so a point just inside the top-left corner is outside it.
      expect(oct.contains(const Offset(2, 1)), isFalse);
      expect(hex.contains(const Offset(2, 20)), isTrue,
          reason: 'the hexagon reaches full height at the vertical middle');
    });

    test('the ends are angled, or it is just a rectangle', () {
      final hex = const FlatTopHexagonBarClipper(endInset: 8).getClip(_box);
      expect(hex.contains(const Offset(1, 1)), isFalse,
          reason: 'top-left must be cut away');
      expect(hex.contains(const Offset(199, 39)), isFalse,
          reason: 'bottom-right must be cut away');
    });

    test('an absurd inset degrades to a lozenge, not an inverted path', () {
      final v = _vertices(
          const FlatTopHexagonBarClipper(endInset: 9999).getClip(_box));
      // Clamped to w/2, so the two flat edges collapse to a point at each end.
      expect(v.length, lessThanOrEqualTo(6));
      expect(
          const FlatTopHexagonBarClipper(endInset: 9999)
              .getClip(_box)
              .getBounds()
              .width,
          _box.width);
    });

    test('FlatTopRegularHexagon cannot stand in for the bar', () {
      // Its diagonals start at a fixed w*0.25, so on a 200x40 bar the angle
      // flattens into a near-triangle. This is the measured reason CR117 adds
      // a third class instead of reusing this one.
      final regular = const FlatTopRegularHexagon().getClip(_box);
      final bar = const FlatTopHexagonBarClipper(endInset: 8).getClip(_box);
      // 40pt in from the end is inside the bar's flat top and outside the
      // regular hexagon's, which is still climbing its diagonal there.
      expect(bar.contains(const Offset(40, 0.5)), isTrue);
      expect(regular.contains(const Offset(40, 0.5)), isFalse);
    });
  });

  group('CR117 — the old name is gone, not re-pointed', () {
    test('nothing in lib/ still uses FlatTopHexagonClipper as an identifier',
        () {
      // The true hexagon deliberately did NOT inherit the vacated name. Had
      // it, an unmigrated call site would keep compiling and silently change
      // shape; because the identifier names nothing, a stale reference is a
      // compile error. This guard fails if someone reintroduces the old name
      // as an alias "for compatibility" and re-opens that door.
      //
      // Prose mentions are fine and in fact required — `hex_clipper.dart`
      // explains the rename by name, and a guard that forbade *saying* the
      // old name would delete its own explanation. So this looks for the
      // name in code position: constructed, declared, or type-annotated.
      final asCode = RegExp(
          r'(class|extends|implements)\s+FlatTopHexagonClipper\b'
          r'|FlatTopHexagonClipper\s*\('
          r'|:\s*FlatTopHexagonClipper\b');
      final offenders = Directory('lib')
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))
          .where((f) => asCode.hasMatch(f.readAsStringSync()))
          .map((f) => f.path)
          .toList();
      expect(offenders, isEmpty,
          reason: 'CR117 removed this name on purpose — see hex_clipper.dart');
    });

    test('…and that guard can actually see a violation', () {
      // Vacuity check on the regex above: a guard that matches nothing would
      // pass forever and read as proof.
      final asCode = RegExp(
          r'(class|extends|implements)\s+FlatTopHexagonClipper\b'
          r'|FlatTopHexagonClipper\s*\('
          r'|:\s*FlatTopHexagonClipper\b');
      expect(asCode.hasMatch('clipper: const FlatTopHexagonClipper(cut: 8)'),
          isTrue);
      expect(asCode.hasMatch('class FlatTopHexagonClipper extends X {'), isTrue);
      // …and must not fire on the docstring that explains the rename.
      expect(
          asCode.hasMatch(
              '/// `FlatTopHexagonClipper` used to be the octagon, and its own'),
          isFalse);
    });
  });
}
