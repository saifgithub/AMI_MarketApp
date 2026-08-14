/// DEF249-class — `HexButton` must announce its label exactly ONCE.
///
/// `Semantics(label: label)` wrapped a subtree whose child is a `Text` of that
/// same string. Semantics merges its own label with its merged descendants',
/// so the node carried the label twice. Measured on the Android rig device
/// with the app on Floor, the Convene CTA's content-desc came back as:
///
///     'CONVENE THE ROOM\nCONVENE THE ROOM'
///
/// Two costs, and the second is what makes this worth a guard rather than a
/// tidy-up. A screen-reader user hears the button announced twice — that is
/// the real defect. But it also made every exact-text locator for the CTA
/// miss, which failed three Appium tests as if the button were absent; a whole
/// debugging session went into "why is CONVENE THE ROOM not on screen" when it
/// was on screen and correctly rendered.
///
/// The visible `Text` is deliberately the single source of the label. That is
/// the same resolution DEF249 reached for the bottom nav (which produced
/// "FLOOR\nFLOOR") and the Concierge chips, so this is the third occurrence of
/// one pattern: **never set `Semantics(label:)` over a subtree that already
/// renders the string.** Per failure_patterns.md, a second occurrence gets a
/// guard — this is that guard, generalised to the shared button widget rather
/// than to one call site.
library;

import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';

const _label = 'CONVENE THE ROOM';

Future<void> _pump(WidgetTester t, {VoidCallback? onPressed}) {
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Center(
        child: HexButton(label: _label, onPressed: onPressed ?? () {}),
      ),
    ),
  ));
}

void main() {
  testWidgets('the label is announced exactly once', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);

    final node = t.getSemantics(find.byType(HexButton));
    final announced = node.label;
    final occurrences = _label.allMatches(announced).length;

    expect(
      occurrences,
      1,
      reason: 'HexButton announces its label $occurrences times '
          '(label was "$announced"). Semantics(label:) must not be set over a '
          'child Text that already renders the string — the merged node '
          'concatenates both. Drop the label: argument in hex_button.dart and '
          'let the Text supply it.',
    );

    semantics.dispose();
  });

  testWidgets('it is still exposed as a button, and still enabled', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);

    final node = t.getSemantics(find.byType(HexButton));
    expect(node.hasFlag(SemanticsFlag.isButton), isTrue,
        reason: 'removing label: must not cost the button trait — assistive '
            'technology and iOS automation both key off it (DEF249)');
    expect(node.hasFlag(SemanticsFlag.isEnabled), isTrue);

    semantics.dispose();
  });

  testWidgets('a disabled button announces itself disabled, not absent',
      (t) async {
    final semantics = t.ensureSemantics();
    await t.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: Center(child: HexButton(label: _label, onPressed: null)),
      ),
    ));

    final node = t.getSemantics(find.byType(HexButton));
    expect(node.hasFlag(SemanticsFlag.isEnabled), isFalse);
    expect(node.label, contains(_label),
        reason: 'a disabled CTA must still be findable and readable');

    semantics.dispose();
  });

  testWidgets('wrapping in Semantics does not swallow the tap', (t) async {
    var taps = 0;
    await _pump(t, onPressed: () => taps++);
    await t.tap(find.byType(HexButton));
    expect(taps, 1);
  });

  testWidgets('the label renders visibly exactly once', (t) async {
    await _pump(t);
    expect(find.text(_label), findsOneWidget,
        reason: 'the visible Text is the single source of the label; if this '
            'ever finds two, the duplication moved into the render tree');
  });
}
