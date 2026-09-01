/// DEF382 — our own tour overlay must LEAVE when the tour ends.
///
/// The defect this primitive exists for was not a visual bug: the third-party
/// overlay it replaces took the app's entire iOS accessibility tree with it on
/// dismissal, permanently, with the app still in the foreground. So the primary
/// assertion here is not "did the card render" but "is the entry GONE" — a
/// leaked `OverlayEntry` is this defect's own shape, and a tour that ends while
/// its barrier is still in the tree is a tour that still owns the screen.
///
/// The secondary assertions are the ones the UAT harness depends on: `next()`
/// advances exactly one step (the harness walks tours with `ami.tour.next`
/// because dismissing with Skip is what destroyed the tree), `skip()` ends the
/// tour immediately, and both identifiers actually render.
library;

import 'dart:io';

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Minimal card: enough to tell steps apart and to carry the two identifiers
/// the harness addresses, without pulling l10n into this file.
class _TestCard extends StatelessWidget {
  const _TestCard({required this.tag, required this.controller});

  final String tag;
  final AmiTourController controller;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Flexible(child: Text(tag, overflow: TextOverflow.clip)),
        Semantics(
          identifier: TourIds.skip,
          button: true,
          child: GestureDetector(
            onTap: controller.skip,
            child: const Text('SKIP'),
          ),
        ),
        Semantics(
          identifier: TourIds.next,
          button: true,
          child: GestureDetector(
            onTap: controller.next,
            child: const Text('NEXT'),
          ),
        ),
      ],
    );
  }
}

/// A scrollable with three keyed targets, and a button that starts a tour —
/// the shape every screen has: the targets exist before the tour is shown.
Future<void> pumpStage(
  WidgetTester t, {
  int steps = 3,
  List<GlobalKey>? keys,
}) async {
  final targets = keys ??
      List.generate(3, (_) => GlobalKey()).take(steps).toList();
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListView(
        children: [
          for (var i = 0; i < targets.length; i++)
            SizedBox(
              key: targets[i],
              height: 60,
              child: Text('target $i'),
            ),
          Builder(builder: (context) => TextButton(
            onPressed: () => showAmiTour(
              context: context,
              steps: [
                for (var i = 0; i < steps; i++)
                  AmiTourStep(
                    identify: 'step_$i',
                    target: targets[i],
                    shape: AmiTourShape.roundedRect,
                    radius: 8,
                    paddingFocus: 6,
                    builder: (ctx, ctrl) =>
                        _TestCard(tag: 'card $i', controller: ctrl),
                  ),
              ],
            ),
            child: const Text('START'),
          )),
        ],
      ),
    ),
  ));
}

Future<void> start(WidgetTester t) async {
  await t.tap(find.text('START'));
  // The overlay defers its first focus one frame, and ensureVisible animates
  // for 350ms on top of that.
  await t.pumpAndSettle();
}

void main() {
  testWidgets('showing a tour inserts the overlay and renders step one',
      (t) async {
    await pumpStage(t);
    expect(find.byType(AmiTourOverlay), findsNothing);

    await start(t);
    expect(find.byType(AmiTourOverlay), findsOneWidget,
        reason: 'the tour must actually be on screen before it can be walked');
    expect(find.text('card 0'), findsOneWidget);
    expect(find.text('card 1'), findsNothing);
  });

  testWidgets('skip() ends the tour and REMOVES the entry', (t) async {
    await pumpStage(t);
    await start(t);
    expect(find.byType(AmiTourOverlay), findsOneWidget);

    await t.tap(find.text('SKIP'));
    await t.pumpAndSettle();

    expect(find.byType(AmiTourOverlay), findsNothing,
        reason: 'a barrier left in the tree after skip is DEF382 — the tour '
            'ended but the overlay still owns the screen');
    expect(find.text('SKIP'), findsNothing);
    // The screen underneath is reachable again.
    await t.tap(find.text('START'));
    await t.pumpAndSettle();
    expect(find.byType(AmiTourOverlay), findsOneWidget);
  });

  testWidgets('next() advances exactly one step', (t) async {
    await pumpStage(t);
    await start(t);

    await t.tap(find.text('NEXT'));
    await t.pumpAndSettle();

    expect(find.text('card 1'), findsOneWidget);
    expect(find.text('card 0'), findsNothing,
        reason: 'a step that leaves the previous card behind stacks cards');
    expect(find.text('card 2'), findsNothing);
    expect(find.byType(AmiTourOverlay), findsOneWidget);
  });

  testWidgets('finishing the last step removes the entry too', (t) async {
    await pumpStage(t);
    await start(t);

    for (var i = 0; i < 3; i++) {
      await t.tap(find.text('NEXT'));
      await t.pumpAndSettle();
    }

    expect(find.byType(AmiTourOverlay), findsNothing,
        reason: 'the last NEXT is the finish path — leaking here is the same '
            'defect as leaking on skip, reached by the button the harness uses');
  });

  testWidgets('onFinish fires on the finish path and not on skip',
      (t) async {
    var finishes = 0;
    final key = GlobalKey();
    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) {
          return Column(
            children: [
              SizedBox(key: key, height: 60, child: const Text('target')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                      identify: 'only',
                      target: key,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 'card', controller: ctrl),
                    ),
                  ],
                  onFinish: () => finishes++,
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));

    await start(t);
    await t.tap(find.text('SKIP'));
    await t.pumpAndSettle();
    expect(finishes, 0,
        reason: 'every screen shows its completion toast from onFinish — '
            'firing it on skip would congratulate a user who opted out');

    await start(t);
    await t.tap(find.text('NEXT'));
    await t.pumpAndSettle();
    expect(finishes, 1);
  });

  testWidgets('the card renders both harness identifiers', (t) async {
    final semantics = t.ensureSemantics();
    await pumpStage(t);
    await start(t);

    expect(
        find.byWidgetPredicate((w) =>
            w is Semantics && w.properties.identifier == TourIds.skip),
        findsOneWidget);
    expect(
        find.byWidgetPredicate((w) =>
            w is Semantics && w.properties.identifier == TourIds.next),
        findsOneWidget,
        reason: 'the harness walks tours with ami.tour.next; if the overlay '
            'did not surface it there is no way out but Skip');
    semantics.dispose();
  });

  // The identifiers above come from a test card. This one puts the REAL
  // `TourCard` inside the overlay and walks the tour by tapping the identified
  // control, which is what the UAT harness does on device — the overlay must
  // host the card's own semantics, not merely tolerate its own.
  testWidgets('a real TourCard inside the overlay is walked by ami.tour.next',
      (t) async {
    final semantics = t.ensureSemantics();
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    final key = GlobalKey();
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Builder(builder: (context) {
          return Column(
            children: [
              SizedBox(key: key, height: 60, child: const Text('target')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                      identify: 'one',
                      target: key,
                      builder: (ctx, ctrl) => TourCard(
                        title: 'ONE',
                        body: l.tourYouJournalBody,
                        controller: ctrl,
                        skipLabel: l.tourSkip,
                        nextLabel: l.tourNext,
                      ),
                    ),
                    AmiTourStep(
                      identify: 'two',
                      target: key,
                      builder: (ctx, ctrl) => TourCard(
                        title: 'TWO',
                        body: l.tourYouJournalBody,
                        controller: ctrl,
                        skipLabel: l.tourSkip,
                        nextLabel: l.tourDone,
                      ),
                    ),
                  ],
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));
    await start(t);
    expect(find.byType(TourCard), findsOneWidget);
    final nextFinder = find.byWidgetPredicate((w) =>
        w is Semantics && w.properties.identifier == TourIds.next);
    expect(nextFinder, findsOneWidget);

    await t.tap(nextFinder);
    await t.pumpAndSettle();
    expect(find.text('TWO'), findsOneWidget,
        reason: 'ami.tour.next is the handle the harness walks with');

    await t.tap(nextFinder);
    await t.pumpAndSettle();
    expect(find.byType(AmiTourOverlay), findsNothing,
        reason: 'the DONE step must take the overlay down with it');
    semantics.dispose();
  });

  testWidgets('a step whose target is gone is stepped over, not shown',
      (t) async {
    // A key with no element in the tree: `_focus` must skip past it rather
    // than paint a full-screen dim with nothing to point at.
    final live = GlobalKey();
    final dead = GlobalKey();
    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) {
          return Column(
            children: [
              SizedBox(key: live, height: 60, child: const Text('target')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                      identify: 'dead',
                      target: dead,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 'dead', controller: ctrl),
                    ),
                    AmiTourStep(
                      identify: 'live',
                      target: live,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 'live', controller: ctrl),
                    ),
                  ],
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));

    await start(t);
    expect(find.text('dead'), findsNothing);
    expect(find.text('live'), findsOneWidget);
  });

  // -------------------------------------------------------------------------
  // DEF395 — both found by the CR215 foreign auditor (kimi-code/k3) on the
  // batch SHA, AFTER the same-family gate returned COMPLETE with zero findings
  // and asserted the entry was "removed on every exit path".
  // -------------------------------------------------------------------------

  testWidgets(
      'DEF395 a target that vanishes MID-DISPLAY closes the tour, '
      'it does not leave a full-screen dim', (t) async {
    // The existing sibling test covers a target already gone when the step is
    // REACHED. This is the other case: the step is on screen and its target
    // then leaves the tree. `_focus`'s skip only ran at step transitions, so
    // `_rect` went null, the settle counter ran out, and the barrier was left
    // painting with no hole over a step pointing at nothing.
    final key = GlobalKey();
    var alive = true;
    late StateSetter setOuter;

    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StatefulBuilder(builder: (context, setState) {
          setOuter = setState;
          return Column(
            children: [
              if (alive)
                SizedBox(key: key, height: 60, child: const Text('target')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                      identify: 'only',
                      target: key,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 'only', controller: ctrl),
                    ),
                  ],
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));

    await start(t);
    expect(find.text('only'), findsOneWidget,
        reason: 'precondition: the step is on screen');

    setOuter(() => alive = false);
    await t.pumpAndSettle();

    expect(find.text('only'), findsNothing,
        reason: 'the overlay must not survive its target vanishing — a '
            'retained entry with a null rect is a full-screen dim, which is '
            'this defect\'s own shape');
  });

  testWidgets(
      'DEF395 onFinish does NOT fire when a target dies PART WAY through',
      (t) async {
    // Round 2 of the foreign audit. The first fix gated the `_focus`
    // fall-through on "was any step ever shown", which is true here — the user
    // saw step one — so a mid-tour death fired the completion toast and marked
    // a partly-seen tour complete, on zero user action. `next()` on the LAST
    // step calls `_close(finished: true)` itself and never routes through
    // `_focus`, so the fall-through is never a user completion.
    var finishes = 0;
    final first = GlobalKey();
    final second = GlobalKey();
    var secondAlive = true;
    late StateSetter setOuter;

    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StatefulBuilder(builder: (context, setState) {
          setOuter = setState;
          return Column(
            children: [
              SizedBox(key: first, height: 40, child: const Text('t1')),
              if (secondAlive)
                SizedBox(key: second, height: 40, child: const Text('t2')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                      identify: 's1',
                      target: first,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 's1', controller: ctrl),
                    ),
                    AmiTourStep(
                      identify: 's2',
                      target: second,
                      builder: (ctx, ctrl) =>
                          _TestCard(tag: 's2', controller: ctrl),
                    ),
                  ],
                  onFinish: () => finishes++,
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));

    await start(t);
    expect(find.text('s1'), findsOneWidget);

    // Kill step two's target, then advance onto it.
    setOuter(() => secondAlive = false);
    await t.pumpAndSettle();
    await t.tap(find.text('NEXT'));
    await t.pumpAndSettle();

    expect(finishes, 0,
        reason: 'the user never reached the end — a target died under them, '
            'and a partly-seen tour must not be marked complete');
  });

  test('DEF395 the rect-watch chain is generation-guarded', () {
    // HONEST LIMIT, stated rather than papered over. Round 2 of the foreign
    // audit found that every step arms a rect-watch chain and, once the chain
    // re-armed for the life of the tour, none ever retired: N+1 concurrent
    // chains each burn a settle frame per frame, so the 8-frame budget drains
    // N+1x too fast and a merely SLOW target is skipped as dead.
    //
    // The behavioural case is NOT reproducible in a widget test: `_focus`
    // skips a step whose `currentContext` is null outright, so the settle
    // budget only engages for a target that HAS a context but has not laid
    // out, which `flutter_test` lays out synchronously. A behavioural test was
    // written first, and removing the guard did not fail it — a passing test
    // that proved nothing. This source pin replaces it and is deliberately
    // narrower than the defect: it stops the guard being deleted, and does not
    // claim to prove the frame accounting.
    final src = File('lib/features/tour/ami_tour_overlay.dart').readAsStringSync();
    expect(src.contains('generation != _watchGeneration'), isTrue,
        reason: 'the stale-chain guard is gone; every step will leave an '
            'immortal watcher behind and drain the settle budget');
    expect(src.contains('final generation = ++_watchGeneration;'), isTrue,
        reason: 'chains must be issued a generation when armed');
  });

  testWidgets(
      'DEF395 a three-step tour still walks to its last step',
      (t) async {
    // Smoke cover for the navigation path the generation guard sits on.
    final k1 = GlobalKey();
    final k2 = GlobalKey();
    final k3 = GlobalKey();
    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) {
          return Column(
            children: [
              SizedBox(key: k1, height: 30, child: const Text('a')),
              SizedBox(key: k2, height: 30, child: const Text('b')),
              SizedBox(key: k3, height: 30, child: const Text('c')),
              TextButton(
                onPressed: () => showAmiTour(
                  context: context,
                  steps: [
                    AmiTourStep(
                        identify: 'x1',
                        target: k1,
                        builder: (ctx, c) => _TestCard(tag: 'x1', controller: c)),
                    AmiTourStep(
                        identify: 'x2',
                        target: k2,
                        builder: (ctx, c) => _TestCard(tag: 'x2', controller: c)),
                    AmiTourStep(
                        identify: 'x3',
                        target: k3,
                        builder: (ctx, c) => _TestCard(tag: 'x3', controller: c)),
                  ],
                ),
                child: const Text('START'),
              ),
            ],
          );
        }),
      ),
    ));

    await start(t);
    await t.tap(find.text('NEXT'));
    await t.pumpAndSettle();
    await t.tap(find.text('NEXT'));
    await t.pumpAndSettle();
    expect(find.text('x3'), findsOneWidget,
        reason: 'the third step must still render — stale watcher chains from '
            'steps one and two must not have consumed its settle budget');
  });

  testWidgets('DEF395 onFinish does NOT fire for a tour nobody saw',
      (t) async {
    // Every target unmounted: `_focus` walks the whole list, falls off the end,
    // and reaches the same `_close` the last "Got it" tap does. Firing onFinish
    // there shows the completion toast, and marks the tour seen, for a tour
    // that was never displayed.
    var finishes = 0;
    final dead1 = GlobalKey();
    final dead2 = GlobalKey();

    await t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) {
          return TextButton(
            onPressed: () => showAmiTour(
              context: context,
              steps: [
                AmiTourStep(
                  identify: 'd1',
                  target: dead1,
                  builder: (ctx, ctrl) =>
                      _TestCard(tag: 'd1', controller: ctrl),
                ),
                AmiTourStep(
                  identify: 'd2',
                  target: dead2,
                  builder: (ctx, ctrl) =>
                      _TestCard(tag: 'd2', controller: ctrl),
                ),
              ],
              onFinish: () => finishes++,
            ),
            child: const Text('START'),
          );
        }),
      ),
    ));

    await start(t);

    expect(finishes, 0,
        reason: '"finished" must mean the USER reached the end, not that the '
            'loop did');
    expect(find.text('d1'), findsNothing);
    expect(find.text('d2'), findsNothing,
        reason: 'the entry must still be torn down — not finishing is not the '
            'same as leaking');
  });
}
