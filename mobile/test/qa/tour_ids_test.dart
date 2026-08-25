/// DEF375 — the coach-mark tours' Skip control is addressable.
///
/// Five tours (floor, portfolio, lessons, journal, you) render through the one
/// `TourCard`, and they are **modal**: until one is dismissed the tab behind it
/// is unreachable. On a fresh install that is every tab, and it cost the iOS
/// phase1 gate 7 of 19 tests — `test_portfolio_renders_heading` failed with the
/// app parked on YOU behind the *YOU* tour, having never reached Portfolio.
///
/// This asserts against the rendered semantics tree, not the source. A test
/// that greps `tour_card.dart` for the identifier would pass on a file that
/// mentions it in a comment, which is a mistake this project has already made
/// once (DEF370).
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

class _FakeController implements TutorialCoachMarkController {
  int skips = 0;
  @override
  void next() {}
  @override
  void previous() {}
  @override
  void skip() => skips++;
}

Future<_FakeController> _pump(WidgetTester t, {String skipLabel = 'Skip tour'}) async {
  final controller = _FakeController();
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: TourCard(
        title: 'THREE THINGS, ONE TAB',
        body: 'Settings, your Decision Journal and your Insights.',
        controller: controller,
        skipLabel: skipLabel,
        nextLabel: 'Next',
      ),
    ),
  ));
  return controller;
}

void main() {
  testWidgets('the Skip control carries the identifier', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);
    expect(
      find.byWidgetPredicate(
          (w) => w is Semantics && w.properties.identifier == TourIds.skip),
      findsOneWidget,
    );
    semantics.dispose();
  });

  testWidgets('the identifier survives translation', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, skipLabel: 'تخطي الجولة');
    expect(
      find.byWidgetPredicate(
          (w) => w is Semantics && w.properties.identifier == TourIds.skip),
      findsOneWidget,
      reason: 'the harness must not need the translated label to escape a tour',
    );
    semantics.dispose();
  });

  testWidgets('tapping the identified control actually skips the tour',
      (t) async {
    final semantics = t.ensureSemantics();
    final controller = await _pump(t);
    await t.tap(find.byWidgetPredicate(
        (w) => w is Semantics && w.properties.identifier == TourIds.skip));
    await t.pump();
    expect(controller.skips, 1,
        reason:
            'an identifier on a control that does not dismiss the tour would '
            'leave the harness tapping something harmless forever — which is '
            'exactly the DEF362 failure this pattern exists to end');
    semantics.dispose();
  });
}
