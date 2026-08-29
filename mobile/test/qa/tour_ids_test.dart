/// DEF375 / DEF382 — the coach-mark tours' dismissal controls are addressable.
///
/// Five tours (floor, portfolio, lessons, journal, you) render through the one
/// `TourCard`, and they are **modal**: until one is dismissed the tab behind it
/// is unreachable. On a fresh install that is every tab, and it cost the iOS
/// phase1 gate 7 of 19 tests — `test_portfolio_renders_heading` failed with the
/// app parked on YOU behind the *YOU* tour, having never reached Portfolio.
///
/// This asserts against the rendered SEMANTICS NODE, not the widget and not the
/// source. The distinction is the whole defect. The first version of this file
/// carried this same sentence while asserting `find.byWidgetPredicate((w) => w
/// is Semantics && w.properties.identifier == ...)` — which is the WIDGET tree.
/// It passed for weeks over a build where `ami.tour.skip` was not addressable on
/// device at all: a bare `Semantics(identifier:)` around a `TextButton` renders
/// TWO nodes, the identifier landing on a parent with `tap=false,
/// isButton=false` while the real button underneath carries no identifier. On
/// iOS the addressable element is the button, so the harness asked for an id
/// nothing answered to, and three rounds of harness work chased it.
///
/// P18's shape exactly — proven on the builder, never on the caller that has to
/// consume it — and P30's, since the docstring recorded a check that was not
/// being performed. So the assertions below read the node: identifier AND tap
/// action AND button flag, on ONE node.
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

class _FakeController implements TutorialCoachMarkController {
  int skips = 0;
  int nexts = 0;
  @override
  void next() => nexts++;
  @override
  void previous() {}
  @override
  void skip() => skips++;
}

Future<_FakeController> _pump(WidgetTester t,
    {String skipLabel = 'Skip tour', String nextLabel = 'Next'}) async {
  final controller = _FakeController();
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: TourCard(
        title: 'THREE THINGS, ONE TAB',
        body: 'Settings, your Decision Journal and your Insights.',
        controller: controller,
        skipLabel: skipLabel,
        nextLabel: nextLabel,
      ),
    ),
  ));
  return controller;
}

/// The rendered node carrying [identifier], or null. Walks the real semantics
/// tree — the thing the iOS engine turns into `UIAccessibilityElement`s — rather
/// than the widget tree, which says nothing about addressability.
SemanticsData? _nodeWithIdentifier(WidgetTester t, String identifier) {
  SemanticsData? found;
  void walk(SemanticsNode n) {
    final d = n.getSemanticsData();
    if (d.identifier == identifier && !n.isMergedIntoParent) found = d;
    n.visitChildren((c) {
      walk(c);
      return true;
    });
  }

  t.binding.rootPipelineOwner.visitChildren((owner) {
    final root = owner.semanticsOwner?.rootSemanticsNode;
    if (root != null) walk(root);
  });
  return found;
}

void main() {
  testWidgets('the identifier lands on a node that is actually addressable',
      (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);

    final node = _nodeWithIdentifier(t, TourIds.skip);
    expect(node, isNotNull,
        reason: 'no rendered semantics node carries ${TourIds.skip}');
    // The three properties that make it an element XCUITest can find and tap.
    // Asserting the identifier alone is what let the broken build ship.
    expect(node!.hasAction(SemanticsAction.tap), isTrue,
        reason: 'the identified node cannot be tapped, so the harness would '
            'resolve it and then tap nothing — the DEF362 failure again');
    expect(node.flagsCollection.isButton, isTrue,
        reason: 'the identified node is not a button, so it is a container and '
            'the real control is a separate node with no identifier');
    expect(node.label, isNotEmpty,
        reason: 'an element with no label is the container, not the control');
    semantics.dispose();
  });

  testWidgets('the identifier survives translation', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, skipLabel: 'تخطي الجولة');
    final node = _nodeWithIdentifier(t, TourIds.skip);
    expect(node, isNotNull,
        reason: 'the harness must not need the translated label to escape a tour');
    expect(node!.hasAction(SemanticsAction.tap), isTrue);
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

  // DEF382 — Next is what the harness actually walks tours with, because Skip
  // takes the iOS accessibility tree down with the overlay. It therefore needs
  // every property Skip needs, not fewer.
  testWidgets('the Next control is addressable on the same terms as Skip',
      (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t);

    final node = _nodeWithIdentifier(t, TourIds.next);
    expect(node, isNotNull,
        reason: 'no rendered semantics node carries ${TourIds.next}');
    expect(node!.hasAction(SemanticsAction.tap), isTrue,
        reason: 'the harness would resolve it and then tap nothing');
    expect(node.flagsCollection.isButton, isTrue);
    expect(node.label, isNotEmpty);
    semantics.dispose();
  });

  testWidgets('the two controls are different nodes and do different things',
      (t) async {
    final semantics = t.ensureSemantics();
    final controller = await _pump(t);
    await t.tap(find.byWidgetPredicate(
        (w) => w is Semantics && w.properties.identifier == TourIds.next));
    await t.pump();
    expect(controller.nexts, 1,
        reason: 'ami.tour.next must advance the tour');
    expect(controller.skips, 0,
        reason: 'if Next reached skip() the harness would take the whole iOS '
            'accessibility tree down on its first tour — DEF382');
    semantics.dispose();
  });

  testWidgets('the Next identifier survives translation', (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, nextLabel: 'التالي');
    final node = _nodeWithIdentifier(t, TourIds.next);
    expect(node, isNotNull);
    expect(node!.hasAction(SemanticsAction.tap), isTrue);
    semantics.dispose();
  });
}
