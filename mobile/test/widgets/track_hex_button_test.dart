/// CR108 — lessons track hexes wrap their label instead of shrinking it.
///
/// `track_hex_button.dart:43` used to size a single-line label against the
/// hex's bounding box and let `FittedBox(scaleDown)` compress it when it
/// overran — the only label in the app that got SMALLER at a bigger text
/// scale (`ISLAMIC FINANCE` at 1.15x: 8.4px, below its own 8px base). The fix
/// wraps to two lines instead; these tests measure the rendered widget for
/// all 13 shipped labels, not the geometry on paper.
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

Future<double> _renderedLabelFontSize(
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

  // `FittedBox` scales visually at paint time — it does not rewrite the
  // `TextStyle`, so the Text widget's own `fontSize` always reads back as the
  // unscaled base (10). The rendered size is the base font size times the
  // ambient text scale (baked into the RenderParagraph's own layout) times
  // whatever the FittedBox's paint transform applies on top — read off the
  // actual render tree, not computed on paper.
  final finder = find.descendant(
    of: find.byType(TrackHexButton),
    matching: find.text(label),
  );
  final paragraph = t.renderObject<RenderParagraph>(finder);
  final fittedBoxScale = paragraph.getTransformTo(null).getMaxScaleOnAxis();
  const baseFontSize = 10.0;
  return baseFontSize * textScale * fittedBoxScale;
}

void main() {
  group('CR108 — every track label wraps instead of shrinking', () {
    for (final entry in honeycombTrackLabel.entries) {
      final label = entry.value;

      testWidgets('"$label" renders at >=10.0px at 1.0x scale', (t) async {
        final fontSize = await _renderedLabelFontSize(t, label);
        expect(fontSize, greaterThanOrEqualTo(10.0),
            reason: '"$label" must not need to shrink at 1.0x');
      });

      testWidgets('"$label" renders at >=10.5px at 1.15x scale', (t) async {
        final fontSize =
            await _renderedLabelFontSize(t, label, textScale: 1.15);
        expect(fontSize, greaterThanOrEqualTo(10.5),
            reason: '"$label" must not need to shrink below its base at 1.15x');
      });
    }

    testWidgets('ISLAMIC FINANCE — the one that regressed — never drops '
        'below its base size at 1.15x', (t) async {
      const label = 'ISLAMIC FINANCE';
      final at1x = await _renderedLabelFontSize(t, label);
      final at1_15x = await _renderedLabelFontSize(t, label, textScale: 1.15);
      expect(at1x, greaterThanOrEqualTo(10.0));
      expect(at1_15x, greaterThanOrEqualTo(10.0),
          reason: 'must never render below its own 10px base — this label '
              'used to shrink to 8.4px, below its OLD 8px base, at 1.15x');
    });
  });
}
