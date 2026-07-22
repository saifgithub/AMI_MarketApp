/// DEF082 guard — the Lessons comb must render every track the API served.
///
/// The defect: the screen iterated a hardcoded 7-entry position map and used
/// the API response only as a filter, so five backend tracks (64 lessons) were
/// silently dark for months. These tests fail the build the next time the
/// backend taxonomy grows past what this app knows about, instead of letting
/// the extra tracks vanish — CLAUDE.md "degrade loudly", third occurrence of
/// the class after DEF038 and DEF063.
library;

import 'dart:math' as math;

import 'package:ami_trade/screens/lessons/honeycomb_layout.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// The 13 tracks the backend registers today (`LessonTrack` in
/// `backend/app/schemas/lessons.py`). `decision_evaluation` is registered with
/// zero lessons until CR062 lands, so the API serves 12 of these.
const _backendTracks = [
  'foundations',
  'fundamentals_analysis',
  'technical_analysis',
  'news_macro',
  'sentiment_behaviour',
  'risk_portfolio',
  'edge_process',
  'asset_classes',
  'economics_macro',
  'quant_methods',
  'ethics_integrity',
  'islamic_finance',
  'decision_evaluation',
];

// ─── OKLab, for the adjacency assertion ──────────────────────────────────────

double _lin(int v) {
  final c = v / 255.0;
  return c <= 0.04045 ? c / 12.92 : math.pow((c + 0.055) / 1.055, 2.4) as double;
}

List<double> _oklab(Color c) {
  final r = _lin((c.r * 255).round());
  final g = _lin((c.g * 255).round());
  final b = _lin((c.b * 255).round());
  final l = math.pow(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b, 1 / 3)
      as double;
  final m = math.pow(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b, 1 / 3)
      as double;
  final s = math.pow(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b, 1 / 3)
      as double;
  return [
    0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
  ];
}

/// Chroma axes weighted up: hue separation is what reads as a boundary.
double _deltaE(Color x, Color y) {
  final a = _oklab(x), b = _oklab(y);
  final dl = a[0] - b[0];
  final da = (a[1] - b[1]) * 1.6;
  final db = (a[2] - b[2]) * 1.6;
  return math.sqrt(dl * dl + da * da + db * db);
}

double _contrast(Color c) {
  final a = c.computeLuminance();
  final b = AmiColors.slate900.computeLuminance();
  return (math.max(a, b) + 0.05) / (math.min(a, b) + 0.05);
}

/// Edge list of the comb: vertical neighbours within a column, plus each side
/// cell touching the two centre cells it sits between.
List<List<int>> _edges(int n) {
  final centre = honeycombCentreCount(n);
  final sides = centre - 1;
  int l(int i) => i;
  int c(int i) => sides + i;
  int r(int i) => sides + centre + i;
  final out = <List<int>>[];
  void add(int a, int b) {
    if (a < n && b < n) out.add([a, b]);
  }

  for (var i = 0; i < sides - 1; i++) {
    add(l(i), l(i + 1));
    add(r(i), r(i + 1));
  }
  for (var i = 0; i < centre - 1; i++) {
    add(c(i), c(i + 1));
  }
  for (var i = 0; i < sides; i++) {
    add(l(i), c(i));
    add(l(i), c(i + 1));
    add(r(i), c(i));
    add(r(i), c(i + 1));
  }
  return out;
}

void main() {
  group('DEF082 — no track can go dark', () {
    test('every served track gets a slot, exactly once', () {
      for (var n = 1; n <= _backendTracks.length + 3; n++) {
        final served = [
          ..._backendTracks.take(math.min(n, _backendTracks.length)),
          for (var k = 0; k < n - _backendTracks.length; k++) 'future_track_$k',
        ];
        final ordered = orderTracksForHoneycomb(served);
        expect(ordered.length, served.length,
            reason: 'dropped a track at n=$n');
        expect(ordered.toSet(), served.toSet(),
            reason: 'lost or duplicated a track at n=$n');
        expect(honeycombSlots(ordered.length, 100, 87).length, ordered.length,
            reason: 'fewer positions than tracks at n=$n');
      }
    });

    test('unknown tracks survive — they render, they do not vanish', () {
      final ordered = orderTracksForHoneycomb(
        [..._backendTracks, 'behavioural_finance', 'crypto_basics'],
      );
      expect(ordered, contains('behavioural_finance'));
      expect(ordered, contains('crypto_basics'));
      // Appended after the known taxonomy, so known placements never shift.
      expect(ordered.take(_backendTracks.length).toSet(),
          _backendTracks.toSet());
      expect(honeycombFallbackColors, isNotEmpty);
    });

    test('every backend track has a colour and a label', () {
      for (final t in _backendTracks) {
        expect(honeycombTrackOrder, contains(t), reason: '$t has no slot order');
        expect(honeycombTrackColor[t], isNotNull, reason: '$t has no colour');
        expect(honeycombTrackLabel[t], isNotNull, reason: '$t has no label');
      }
      expect(honeycombTrackOrder.toSet(), _backendTracks.toSet());
    });
  });

  group('DEF082 — the palette is the boundary', () {
    test('no two adjacent hexes are perceptually close', () {
      // Floor is the shipped 7-colour palette's own closest pair
      // (hexPink/hexRed = 0.1807); the solved comb clears 0.32. Asserting well
      // above the floor is what catches a reorder that undoes the solve.
      const floor = 0.30;
      for (final n in [12, 13]) {
        final ordered = orderTracksForHoneycomb(honeycombTrackOrder.take(n));
        for (final e in _edges(n)) {
          final a = honeycombTrackColor[ordered[e[0]]]!;
          final b = honeycombTrackColor[ordered[e[1]]]!;
          expect(_deltaE(a, b), greaterThanOrEqualTo(floor),
              reason: 'n=$n: ${ordered[e[0]]} touches ${ordered[e[1]]}');
        }
      }
    });

    test('every track label is legible on the dark canvas', () {
      for (final t in honeycombTrackOrder) {
        expect(_contrast(readableOnCanvas(honeycombTrackColor[t]!)),
            greaterThanOrEqualTo(amiCanvasContrastFloor),
            reason: '$t label ink fails the contrast floor');
      }
    });
  });

  group('hex label fits inside the hexagon, not just its box', () {
    test('width at the label height is the narrow measurement', () {
      // Sizing against the bounding box is what sliced ISLAMIC FINANCE: at the
      // label's height a flat-top hexagon is 0.72x its box, not 1.0x.
      expect(flatTopHexWidthFractionAt(0.5), closeTo(1.0, 1e-9));
      expect(flatTopHexWidthFractionAt(0.0), closeTo(0.5, 1e-9));
      expect(flatTopHexWidthFractionAt(1.0), closeTo(0.5, 1e-9));
      expect(flatTopHexWidthFractionAtLabel, lessThan(0.75));
      expect(flatTopHexWidthFractionAtLabel, greaterThan(0.6));
    });

    test('the longest label fits at 143 pt, with the system text scale up', () {
      const hexW = 143.2; // what honeycombHexWidthFraction gives on a 358 pt column
      final box = hexW * flatTopHexWidthFractionAtLabel;
      // IBM Plex Mono at 8 pt: 0.6 em advance + 1.8 letterSpacing per glyph.
      double labelWidth(String s, double scale) =>
          s.length * (8 * scale * 0.6 + 1.8);
      final longest = honeycombTrackLabel.values
          .reduce((a, b) => a.length >= b.length ? a : b);
      expect(longest, 'ISLAMIC FINANCE');
      // At 1.0 the raw label fits the hexagon with only ~4 pt to spare, and at
      // 1.15 it does not — which is why the widget wraps it in a scaleDown
      // FittedBox instead of trusting the margin.
      expect(labelWidth(longest, 1.0), lessThan(box));
      expect(labelWidth(longest, 1.15), greaterThan(box),
          reason: 'if this ever passes, the FittedBox is no longer load-bearing '
              'and this test should be revisited rather than deleted');
    });
  });

  group('honeycomb geometry', () {
    test('the comb fits the width it is given', () {
      // 0.1.0+47 shipped `maxWidth * 2 / honeycombWidthInHexes` — a misread of
      // the original `2 / 5` — which is 0.80, so the comb rendered at 2x and
      // overflowed its column. This is the assertion that would have caught it.
      expect(honeycombHexWidthFraction * honeycombWidthInHexes,
          lessThanOrEqualTo(1.0),
          reason: 'three columns span 2.5 hexes; they cannot exceed the box');

      const maxWidth = 358.0;
      final hexW = maxWidth * honeycombHexWidthFraction;
      final slots = honeycombSlots(13, hexW, hexW / 1.1547005);
      for (final s in slots) {
        expect(s.dx + hexW, lessThanOrEqualTo(maxWidth + 0.5),
            reason: 'a hex hangs off the right edge');
      }
    });


    test('centre column runs one taller than the sides', () {
      expect(honeycombCentreCount(7), 3); // the old 2/3/2 flower
      expect(honeycombCentreCount(12), 5);
      expect(honeycombCentreCount(13), 5); // 4/5/4
      expect(honeycombCentreCount(14), 6);
    });

    test('columns sit at 0, ¾W, 1½W and side columns drop half a hex', () {
      final slots = honeycombSlots(13, 100, 80);
      expect(slots[0], const Offset(0, 40)); // L0
      expect(slots[4], const Offset(75, 0)); // C0
      expect(slots[6], const Offset(75, 160)); // C2 — the visual centre
      expect(slots[9], const Offset(150, 40)); // R0
      expect(slots[12], const Offset(150, 280)); // R3 — last slot
    });

    test('an unauthored track empties the last slot, not a middle one', () {
      final full = honeycombSlots(13, 100, 80);
      final without = honeycombSlots(12, 100, 80);
      expect(without, full.take(12));
      // EVALUATION is last precisely so its absence cannot hole the comb.
      expect(honeycombTrackOrder.last, 'decision_evaluation');
    });
  });
}
