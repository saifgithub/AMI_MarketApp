/// CR209 — the Concierge interview's automation contract.
///
/// The onboarding walk (`qa/appium/helpers/onboarding.py`) used to select an
/// answer by geometry — "the bottom-most labelled control". On iOS the bottom
/// of the screen never belongs to the chips, and three different controls were
/// measured occupying that slot across three consecutive runs: the keyboard's
/// globe key (186 taps), the composer (180), the send arrow (579). Excluding
/// them one at a time cannot converge, because the pool is the platform's.
///
/// So the walk now addresses the chips by identifier, and this is the local,
/// loud failure that keeps that possible. Nothing in the app *renders* an
/// identifier, so dropping one during a refactor is invisible until a device
/// run goes red days later — which is the failure mode CR162 built this
/// pattern to end, and which DEF362 then spent three rounds inside.
library;

import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/widgets/chat/chip_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Deliberately not English: an identifier that moved with the rendered label
/// would re-couple the harness to translation, which is the coupling the
/// identifier contract exists to remove.
const _chips = <String>['التقاعد', 'ثروة طويلة الأجل', 'دخل الآن'];

Future<void> _pump(WidgetTester t, List<String> chips) {
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ChipRow(chips: chips, onSelected: (_) {}),
    ),
  ));
}

void main() {
  testWidgets('every answer chip is addressable by identifier', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, _chips);

    expect(
      find.bySemanticsLabel(RegExp(r'.*')),
      findsWidgets,
      reason: 'sanity: the row rendered something',
    );
    expect(
      find.byWidgetPredicate((w) =>
          w is Semantics &&
          w.properties.identifier == OnboardingIds.answerChip),
      findsNWidgets(_chips.length),
      reason:
          'every chip must carry the id — the walk taps whichever it finds, '
          'so a chip without one is an answer the walk cannot give',
    );
    semantics.dispose();
  });

  testWidgets('the identifier does not vary with the rendered label',
      (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, const ['Save for retirement']);
    final english = t
        .widgetList<Semantics>(find.byWidgetPredicate(
            (w) => w is Semantics && w.properties.identifier != null))
        .map((w) => w.properties.identifier)
        .toList();
    await _pump(t, const ['التقاعد']);
    final arabic = t
        .widgetList<Semantics>(find.byWidgetPredicate(
            (w) => w is Semantics && w.properties.identifier != null))
        .map((w) => w.properties.identifier)
        .toList();
    expect(english, arabic);
    expect(english, [OnboardingIds.answerChip]);
    semantics.dispose();
  });

  testWidgets('the chip is still announced as a button (DEF249 holds)',
      (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, const ['Save for retirement']);
    expect(
      find.byWidgetPredicate(
          (w) => w is Semantics && w.properties.button == true),
      findsOneWidget,
      reason:
          'adding an identifier must not displace the button trait — without '
          'it a VoiceOver user gets no signal the chips are tappable at all',
    );
    semantics.dispose();
  });

  test('the three interview ids are distinct and namespaced', () {
    final ids = <String>{
      OnboardingIds.answerChip,
      OnboardingIds.composer,
      OnboardingIds.send,
    };
    expect(ids.length, 3, reason: 'a duplicated id makes two things one thing');
    for (final id in ids) {
      expect(id, startsWith('ami.onboarding.'));
    }
  });
}
