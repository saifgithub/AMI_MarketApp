/// DEF249 — Concierge answer chips must be exposed as BUTTONS, not static text.
///
/// `_Chip` was a bare `GestureDetector`. Flutter only marks a node with the
/// platform's button trait when semantics say so, so on iOS the chips arrived
/// as `XCUIElementTypeStaticText` — a VoiceOver user on the first question of
/// onboarding heard four phrases with no indication any was tappable.
///
/// Android hid this completely: its accessibility bridge marks any tappable
/// node `clickable` regardless of semantics flags, so the Appium harness had
/// walked this interview happily since CR080. It only surfaced when the app was
/// first driven on iOS (CR162). That is exactly why this guard is a *semantics*
/// assertion rather than a tap test — a tap test passes on the broken build.
library;

import 'package:ami_trade/widgets/chat/chip_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';

const _chips = ['Save for retirement', 'Build long-term wealth'];

Future<void> _pump(WidgetTester t, {ValueChanged<String>? onSelected}) {
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ChipRow(chips: _chips, onSelected: onSelected ?? (_) {}),
    ),
  ));
}

void main() {
  testWidgets('every chip carries the button semantics flag', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);

    for (final chip in _chips) {
      final node = t.getSemantics(find.bySemanticsLabel(chip));
      expect(node.hasFlag(SemanticsFlag.isButton), isTrue,
          reason: 'DEF249: $chip is announced as static text, so assistive '
              'technology gives no signal that it is tappable — and iOS UI '
              'automation cannot reach it either. Restore Semantics(button: '
              'true) in chip_row.dart.');
    }

    semantics.dispose();
  });

  testWidgets('the chips still submit their own label', (t) async {
    final selected = <String>[];
    await _pump(t, onSelected: selected.add);

    await t.tap(find.text('Save for retirement'));
    expect(selected, ['Save for retirement'],
        reason: 'wrapping in Semantics must not swallow the tap');
  });

  testWidgets('no chips renders nothing', (t) async {
    await t.pumpWidget(const MaterialApp(
      home: Scaffold(body: ChipRow(chips: [], onSelected: _noop)),
    ));
    expect(find.byType(SizedBox), findsWidgets);
    expect(t.takeException(), isNull);
  });
}

void _noop(String _) {}
