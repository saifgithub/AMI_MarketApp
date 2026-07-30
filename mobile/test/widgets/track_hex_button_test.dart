/// CR108 — lessons track hexes wrap their label instead of shrinking it.
///
/// `track_hex_button.dart:43` used to size a single-line label against the
/// hex's bounding box and let `FittedBox(scaleDown)` compress it when it
/// overran — the only label in the app that got SMALLER at a bigger text
/// scale (`ISLAMIC FINANCE` at 1.15x: 8.4px, below its own 8px base). The fix
/// wraps to two lines instead; these tests measure the rendered widget for
/// all 13 shipped labels, not the geometry on paper.
///
/// Round 2 (DEF142 audit, round 1 rejected pre-audit): round 1's `FittedBox`
/// wrapped the `Text`, so `softWrap`/`maxLines: 2` had unbounded width to
/// lay out against and never broke a line — all 13 labels stayed one line
/// and were still shrunk. And round 1's scale metric,
/// `paragraph.getTransformTo(null).getMaxScaleOnAxis()`, does not observe
/// `RenderFittedBox`'s paint-time scale (it returns 1.000 always), so all 26
/// size assertions reduced to `expect(10.0, greaterThanOrEqualTo(10.0))` —
/// deleting the entire two-line feature left every test green. This file
/// replaces the metric with `tester.getRect(finder).width /
/// RenderParagraph.size.width`, which goes through `localToGlobal` and does
/// observe the paint transform — validated below against a case forced to a
/// known scale, not trusted on say-so — and adds a `paraH` assertion so an
/// unwrapped label is a visible failure, not a passing one.
library;

import 'package:ami_trade/screens/lessons/honeycomb_layout.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/track_hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

/// The honeycomb's largest hex — see `lessons_screen.dart`'s
/// `honeycombHexWidthFraction` (0.40) on a typical device column (~358pt),
/// which is what `test/honeycomb_layout_test.dart` pins as `hexW = 143.2`.
const _hexWidth = 143.2;
const _hexHeight = _hexWidth / 1.1547005; // flatTopRegularHexagonAspectRatio

class _Measurement {
  _Measurement(this.fontSize, this.paragraphHeight, this.geometricScale);
  final double fontSize;
  final double paragraphHeight;
  final double geometricScale;
}

Future<_Measurement> _measure(
  WidgetTester t,
  String label, {
  double textScale = 1.0,
}) async {
  await t.pumpWidget(MaterialApp(
    home: Builder(builder: (context) {
      return MediaQuery(
        data: MediaQuery.of(context).copyWith(
          textScaler: TextScaler.linear(textScale),
        ),
        child: Scaffold(
          body: Center(
            child: SizedBox(
              width: _hexWidth,
              height: _hexHeight,
              child: TrackHexButton(
                label: label,
                color: AmiColors.hexCyan,
                completed: 1,
                total: 3,
                onTap: () {},
              ),
            ),
          ),
        ),
      );
    }),
  ));

  // Round 1 read `paragraph.getTransformTo(null).getMaxScaleOnAxis()`, which
  // does not observe `RenderFittedBox`'s paint-time scale and returns 1.000
  // unconditionally (proven below, and the reason round 1's 26 assertions
  // could not fail). `tester.getRect` walks `localToGlobal`, which does
  // apply the paint transform, so comparing the painted rect to the
  // pre-scale `RenderParagraph.size` observes the real scale whether it
  // comes from a `FittedBox` (single-line fallback) or is 1.0 because the
  // label wrapped at its base size and was never scaled at all.
  final finder = find.descendant(
    of: find.byType(TrackHexButton),
    matching: find.text(label),
  );
  final paragraph = t.renderObject<RenderParagraph>(finder);
  final rect = t.getRect(finder);
  final geometricScale = rect.width / paragraph.size.width;
  const baseFontSize = 10.0;
  final fontSize = baseFontSize * textScale * geometricScale;
  return _Measurement(fontSize, paragraph.size.height, geometricScale);
}

void main() {
  group('metric sanity — validated against a forced scale, not trusted', () {
    testWidgets(
        'getRect/RenderParagraph.size observes a real FittedBox scale',
        (t) async {
      // Round 1's bug was a metric that could not fail. Prove this one can:
      // force a known 0.5x FittedBox scale-down with a plain harness (no
      // TrackHexButton involved) and check the metric reports it.
      const label = 'A REASONABLY WIDE LABEL FOR THIS TEST';
      const style = TextStyle(fontSize: 10);
      final natural = (TextPainter(
        text: const TextSpan(text: label, style: style),
        maxLines: 1,
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: double.infinity))
          .width;
      const targetScale = 0.5;
      final boxWidth = natural * targetScale;

      await t.pumpWidget(MaterialApp(
        home: Center(
          child: SizedBox(
            width: boxWidth,
            child: const FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(label, maxLines: 1, softWrap: false, style: style),
            ),
          ),
        ),
      ));

      final finder = find.text(label);
      final paragraph = t.renderObject<RenderParagraph>(finder);
      final rect = t.getRect(finder);
      final measuredScale = rect.width / paragraph.size.width;

      expect(measuredScale, closeTo(targetScale, 0.02),
          reason: 'the metric must read back the real paint-time scale '
              '(0.5 here, by construction) — getTransformTo(null) reads '
              '1.000 for this exact harness, which is what let round 1\'s '
              'assertions pass with the feature deleted');

      // And prove the OLD metric really is the vacuous one, in the same
      // harness, so this is not just asserted in prose.
      final oldMetric = paragraph.getTransformTo(null).getMaxScaleOnAxis();
      expect(oldMetric, 1.0,
          reason: 'getTransformTo(null) does not observe RenderFittedBox\'s '
              'paint-time scale — this is round 1\'s actual defect, '
              'reproduced directly rather than taken on faith');
    });
  });

  group('CR108 — every track label wraps or is deliberately scaled', () {
    for (final entry in honeycombTrackLabel.entries) {
      final label = entry.value;

      testWidgets('"$label" renders at >=10.0px at 1.0x scale', (t) async {
        final m = await _measure(t, label);
        expect(m.fontSize, greaterThanOrEqualTo(10.0),
            reason: '"$label" must not need to shrink at 1.0x');
      });

      testWidgets('"$label" renders at >=10.5px at 1.15x scale', (t) async {
        final m = await _measure(t, label, textScale: 1.15);
        expect(m.fontSize, greaterThanOrEqualTo(10.5),
            reason:
                '"$label" must not need to shrink below its base at 1.15x');
      });
    }

    testWidgets('ISLAMIC FINANCE — the one that regressed — never drops '
        'below its base size at 1.15x', (t) async {
      const label = 'ISLAMIC FINANCE';
      final at1x = await _measure(t, label);
      final at1_15x = await _measure(t, label, textScale: 1.15);
      expect(at1x.fontSize, greaterThanOrEqualTo(10.0));
      expect(at1_15x.fontSize, greaterThanOrEqualTo(10.0),
          reason: 'must never render below its own 10px base — this label '
              'used to shrink to 8.4px, below its OLD 8px base, at 1.15x');
    });

    testWidgets(
        'a label that must wrap actually produces a two-line paragraph '
        '(paraH), not a silently-unwrapped one-line label', (t) async {
      // ISLAMIC FINANCE is the widest label in the set at this fixture and
      // the one CR108 was filed to fix — if any label proves the wrap
      // mechanism engages, it is this one. Round 1's bug was exactly this:
      // RenderParagraph.size.height read 14.0 (one line) for every label,
      // including this one, while the size assertions still passed.
      const label = 'ISLAMIC FINANCE';
      final m = await _measure(t, label);
      // Reference a genuinely single-line label rendered through the same
      // widget and ambient style (a bare TextPainter reads a different line
      // height — no `DefaultTextStyle` merge from the surrounding
      // `MaterialApp`/`Scaffold` to inherit `height` from).
      final oneLine = await _measure(t, 'RISK');
      expect(m.paragraphHeight, greaterThan(oneLine.paragraphHeight * 1.5),
          reason: 'the paragraph must actually be laid out across two '
              'lines — a paraH stuck at one line height is round 1\'s bug, '
              'invisible to a size-only assertion');
      expect(m.geometricScale, closeTo(1.0, 0.01),
          reason: 'a label that fits by wrapping must not ALSO be scaled '
              'down — the wrap should make scaling unnecessary');
    });

    testWidgets(
        'FUNDAMENTALS (12 chars, no space) — measured, not assumed '
        'unbreakable: Flutter\'s line breaker splits it mid-word to fit '
        'two lines, so it renders through the wrap path like any other '
        'long label, at full size', (t) async {
      // The round-2 assign states FUNDAMENTALS "cannot wrap at any box
      // width" and must fall back to scaling. Measured against the real
      // render tree, that premise does not hold: Flutter's default text
      // layout breaks an unbreakable "word" at the character level as a
      // last resort when maxLines allows a further line and no whitespace
      // break exists (UAX#14 fallback), so FUNDAMENTALS wraps into e.g.
      // "FUNDAMENT" / "ALS" and meets the floor at full size — it never
      // needs the single-line scale-down fallback. That fallback path is
      // still real and load-bearing; the synthetic-word test below proves
      // it, since none of the 13 shipped labels are long enough (even as a
      // single word) to require it.
      const label = 'FUNDAMENTALS';
      final m = await _measure(t, label);
      expect(m.fontSize, greaterThanOrEqualTo(10.0));
      expect(m.geometricScale, closeTo(1.0, 0.01),
          reason: 'FUNDAMENTALS wraps at full size — it is not scaled down, '
              'contrary to the "cannot wrap" premise');
      final oneLine = await _measure(t, 'RISK');
      expect(m.paragraphHeight, greaterThan(oneLine.paragraphHeight * 1.5),
          reason: 'FUNDAMENTALS actually wraps to two lines at this '
              'fixture — measured, not assumed');
    });

    testWidgets(
        'a genuinely unbreakable label (too long to fit even split across '
        'two lines) falls back to single-line scaling, rather than '
        'silently overflowing the hex', (t) async {
      // No shipped label is this long, even as one "word" — this proves
      // the explicit fallback branch in track_hex_button.dart exists and
      // is reachable, for the case FUNDAMENTALS turned out not to be.
      const label = 'SUPERCALIFRAGILISTICEXPIALIDOCIOUSXX';
      final m = await _measure(t, label);
      expect(m.geometricScale, lessThan(0.9),
          reason: 'a label this long cannot fit two lines within the '
              'two-line box even with a mid-word break, so it must take '
              'the single-line scale-down fallback, not wrap');
      final oneLine = await _measure(t, 'RISK');
      expect(m.paragraphHeight, closeTo(oneLine.paragraphHeight, 0.5),
          reason: 'the fallback renders one (scaled) line, not a silently '
              'truncated or overflowing two-line attempt');
    });
  });
}
