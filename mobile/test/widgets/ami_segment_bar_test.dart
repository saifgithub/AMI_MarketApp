/// CR133 §4 — the shared segmented control.
///
/// The properties asserted here are DEF146's fix, which is the reason this
/// widget exists as a component at all: the first build clipped each segment
/// separately, producing independently-cut objects with a gap and an outline
/// each, reported as *"the buttons are not hex design"*. One clip around the
/// whole bar, a 1pt divider rather than a gap.
///
/// It also renders at **three** segments, because CR133 ships `YOU` with two
/// and CR178 inserts INSIGHTS as the third. Proving that now is the difference
/// between an insertion and a re-layout.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_segment_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester t, List<String> labels, int selected,
    void Function(int) onSelect) {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: AmiSegmentBar(
        segments: [for (final l in labels) AmiSegment(label: l)],
        selected: selected,
        onSelect: onSelect,
      ),
    ),
  ));
}

/// The fill of each segment. `AnimatedContainer` exposes no `color` getter —
/// it folds a bare `color:` into its `decoration` — so read it back from there.
List<Color?> _fills(WidgetTester t) => t
    .widgetList<AnimatedContainer>(find.byType(AnimatedContainer))
    .map((c) => (c.decoration as BoxDecoration?)?.color)
    .toList();

void main() {
  testWidgets('DEF146 — one clip around the whole bar, not one per segment',
      (t) async {
    await _pump(t, ['SETTINGS', 'JOURNAL'], 0, (_) {});
    expect(find.byType(ClipPath), findsOneWidget,
        reason: 'a clip per segment is two independently-cut objects, which '
            'is two chips whatever their geometry — DEF146');
  });

  testWidgets('segments are divided by a line, not a gap', (t) async {
    await _pump(t, ['A', 'B', 'C'], 0, (_) {});
    // n-1 dividers, each 1pt wide and 32pt tall.
    final dividers = t
        .widgetList<Container>(find.byType(Container))
        .where((c) => c.constraints?.maxWidth == 1)
        .length;
    expect(dividers, 2,
        reason: 'a gap re-creates the two-objects defect in disguise');
  });

  testWidgets('renders at two and at three — CR178 is an insertion',
      (t) async {
    await _pump(t, ['SETTINGS', 'JOURNAL'], 0, (_) {});
    final twoWide = t.getSize(find.text('SETTINGS')).width;
    expect(find.text('JOURNAL'), findsOneWidget);

    await _pump(t, ['SETTINGS', 'JOURNAL', 'INSIGHTS'], 0, (_) {});
    expect(find.text('INSIGHTS'), findsOneWidget);
    // Labels must still render at full size at three: `_Cell` deliberately has
    // no FittedBox, so a too-narrow bar overflows loudly instead of silently
    // shrinking type (CR108's failure). Measured, not eyeballed.
    expect(t.getSize(find.text('SETTINGS')).width, twoWide);
    expect(t.takeException(), isNull);
  });

  testWidgets('tapping a segment reports its index', (t) async {
    int? tapped;
    await _pump(t, ['SETTINGS', 'JOURNAL', 'INSIGHTS'], 0, (i) => tapped = i);
    await t.tap(find.text('INSIGHTS'));
    expect(tapped, 2);
    await t.tap(find.text('JOURNAL'));
    expect(tapped, 1);
  });

  testWidgets('only the selected segment is filled', (t) async {
    await _pump(t, ['A', 'B', 'C'], 1, (_) {});
    final fills = _fills(t);
    expect(fills.where((c) => c == AmiColors.hexBlue).length, 1);
    expect(fills.where((c) => c == AmiColors.slate800).length, 2);
  });

  testWidgets('an out-of-range selection fills nothing rather than guessing',
      (t) async {
    // A caller mid-transition should look like a caller mid-transition.
    await _pump(t, ['A', 'B'], 5, (_) {});
    final fills = _fills(t);
    expect(fills.every((c) => c == AmiColors.slate800), isTrue);
  });
}
