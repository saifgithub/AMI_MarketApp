/// CR173 slice 2 — the Floor, as frame A′.
///
/// The acceptance criteria this file is the mechanical half of:
///
///  - **#1 one fold** — the column fits 390×720 with CONVENE on screen 1, and
///    nothing overflows. Measured here rather than asserted in a doc, because
///    the first build of the carousel overflowed by 100px and the doc would
///    still have said 632px.
///  - **#2 one primary** — exactly one green CTA on the screen.
///  - **#3 carousel rules** — no auto-rotation, portfolio first, a peek slice,
///    ≤5 cards, dots inside the surface.
///  - **#4 day-0** — card 1 always renders, and its number is the *configured*
///    stake, not a literal.
///  - **#5 omnibox** — the CTA names the route before it is taken.
///  - **#7 the firm row's live seat count**, which §5.7 calls load-bearing.
///  - **nothing orphaned** — the twelve, and every path that hung off them,
///    are one tap down rather than deleted.
library;

import 'dart:io';

import 'package:ami_trade/features/tour/floor_tour.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/floor/floor_cards.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/floor/floor_carousel.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The reference geometry acceptance #1 names.
const _reference = Size(390, 720);

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

SimPortfolio _portfolio({
  double starting = 10000,
  double? total,
  double? cash,
  List<SimHolding> holdings = const [],
}) =>
    SimPortfolio(
      userId: 'u',
      portfolioId: 'p',
      startingCapital: starting,
      currentCash: cash ?? starting,
      holdings: holdings,
      totalValue: total ?? starting,
      drawdownPct: 0,
    );

Future<void> _pumpFloor(
  WidgetTester t, {
  SimPortfolio? portfolio,
  List<TeamCall> calls = const [],
}) async {
  await t.binding.setSurfaceSize(_reference);
  addTearDown(() => t.binding.setSurfaceSize(null));
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetDevicePixelRatio);

  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith(
          (ref) => _FixedSim(ref, SimState(portfolio: portfolio))),
      teamCallsProvider.overrideWith((ref) async => calls),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: FloorScreen(),
    ),
  ));
  // The Floor's league + daily-challenge providers each fire a Dio request on
  // creation; the futures never resolve against no server, but their timers
  // are pending until the fake clock has moved. Same idiom as
  // `home_shell_test.dart`.
  await _settle(t);
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  // Seen, so the first-run tour intro sheet does not open over the surface
  // these tests measure — it is a modal, and it absorbed taps aimed at the
  // Floor beneath it. The tour itself is asserted separately, below.
  setUp(() => SharedPreferences.setMockInitialValues({'tour_floor_seen': true}));

  group('acceptance #1 — one fold at 390×720', () {
    testWidgets('nothing overflows', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(t.takeException(), isNull,
          reason: 'a RenderFlex overflow is the fold budget being wrong, and '
              'it is invisible in a doc that says 632px');
    });

    testWidgets('CONVENE is on screen 1, unscrolled', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      final cta = t.getRect(find.byType(HexButton));
      expect(cta.bottom, lessThanOrEqualTo(_reference.height),
          reason: 'the whole point of A′ — the shipped Floor put it 1.63 '
              'folds down');
    });
  });

  testWidgets('acceptance #2 — CONVENE is the only primary', (t) async {
    await _pumpFloor(t, portfolio: _portfolio());
    expect(find.byType(HexButton), findsOneWidget);
    // And no second green ElevatedButton competing with it.
    final greens = t
        .widgetList<ElevatedButton>(find.byType(ElevatedButton))
        .where((b) =>
            b.style?.backgroundColor?.resolve({}) == AmiColors.hexGreen);
    expect(greens, isEmpty);
  });

  group('acceptance #3 — the five carousel rules', () {
    testWidgets('it never rotates on its own', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      final before = t.widget<PageView>(find.byType(PageView)).controller?.page;
      // Odd, coprime offsets — NOT one long pump.
      //
      // The first version of this test pumped 60 seconds and compared the page
      // before and after. A real 5-second autoplay was then added as a
      // mutation and the test stayed GREEN: with two cards, twelve ticks land
      // back on page 0, so the assertion was measuring the modulus, not the
      // rule. That is the DEF190 shape exactly — a check that keeps passing
      // through the very change it exists to catch.
      for (final seconds in [3, 7, 11, 13]) {
        await t.pump(Duration(seconds: seconds));
        await _settle(t);
        expect(t.widget<PageView>(find.byType(PageView)).controller?.page,
            before,
            reason: 'rule 1 — moved on its own after ${seconds}s');
      }
    });

    test('and there is no clock in the file at all', () {
      // The behavioural check above is now hard to fool, but the structural
      // one cannot be fooled: a carousel that moves under the thumb between
      // the decision to tap and the tap needs a timer to do it, and there is
      // no legitimate reason for one to exist here.
      // Comments stripped first — the library doc above the class explains
      // the rule by naming `Timer`, and a guard that trips on its own
      // documentation is a guard nobody keeps.
      final code = File('lib/widgets/floor/floor_carousel.dart')
          .readAsLinesSync()
          .where((line) => !line.trimLeft().startsWith('//'))
          .join('\n');
      expect(code, isNot(contains('Timer')));
      expect(code, isNot(contains('animateToPage')));
    });

    testWidgets('the portfolio leads and a peek slice shows', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.byType(PortfolioAnswerCard), findsOneWidget);
      final controller =
          t.widget<PageView>(find.byType(PageView)).controller!;
      expect(controller.viewportFraction, lessThan(1.0),
          reason: 'rule 4 — a full-width card does not read as swipeable');
      expect(controller.initialPage, 0);
    });

    testWidgets('dots are inside the surface, one per card', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.bySemanticsLabel('card 1 of 2'), findsOneWidget);
      expect(find.bySemanticsLabel('card 2 of 2'), findsOneWidget);
    });

    test('rule 5 is a limit, not a convention', () {
      expect(kMaxFloorCards, 5);
    });
  });

  group('acceptance #4 — day-0 states', () {
    testWidgets('card 1 shows the CONFIGURED stake, not a literal', (t) async {
      // The server's stake is $10,000; the mock-up's was $100,000. A hardcoded
      // figure is wrong the first time either moves.
      await _pumpFloor(t, portfolio: _portfolio(starting: 25000));
      expect(find.textContaining(r'$25,000'), findsWidgets);
      expect(find.textContaining(r'$100,000'), findsNothing);
    });

    testWidgets('an untouched portfolio reports no return', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.textContaining('all-time'), findsNothing,
          reason: '+0.0% all-time on a portfolio that never traded implies a '
              'measurement nobody made');
      expect(find.textContaining('no positions yet'), findsOneWidget);
    });

    testWidgets('card 1 renders even before the portfolio loads', (t) async {
      await _pumpFloor(t);
      expect(find.byType(PortfolioAnswerCard), findsOneWidget);
      expect(find.textContaining(r'$0'), findsNothing,
          reason: 'not-yet-loaded is not "you have nothing", and this is the '
              'first number a user sees about their money');
    });

    testWidgets('card 2 teaches rather than collapsing', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      await t.drag(find.byType(PageView), const Offset(-400, 0));
      await t.pumpAndSettle();
      expect(find.textContaining('No verdicts yet'), findsOneWidget);
    });
  });

  group('acceptance #5 — the omnibox names its route first', () {
    testWidgets('empty → CONVENE, ticker → CONVENE ON, prose → ASK AMI',
        (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.text('CONVENE THE ROOM'), findsOneWidget);

      await t.enterText(find.byType(TextField), 'nvda');
      await t.pump();
      expect(find.textContaining('NVDA'), findsWidgets,
          reason: 'the CTA names the ticker it is about to spend a credit on');

      await t.enterText(find.byType(TextField), 'what is a P/E ratio?');
      await t.pump();
      expect(find.text('ASK AMI'), findsOneWidget);
    });
  });

  group('nothing was orphaned', () {
    testWidgets('acceptance #7 — the firm row carries a live seat count',
        (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.textContaining('seats filled'), findsOneWidget,
          reason: '§5.7 — dropping this changes the design and needs a '
              're-review, so it is asserted, not remembered');
    });

    testWidgets('the twelve are one tap down, not gone', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      // Not on the Floor…
      expect(find.byType(AgentTile), findsNothing);
      // …but one tap away, all twelve.
      // The firm row sits below the fold by design — acceptance #1 puts
      // CONVENE on screen 1, not everything.
      await t.ensureVisible(find.textContaining('seats filled'));
      await t.pump();
      await t.tap(find.textContaining('seats filled'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 400)); // route transition
      await _settle(t);
      expect(find.byType(AgentTile), findsNWidgets(12),
          reason: 'D-012 — twelve agents hidden is a design, twelve agents '
              'deleted is a different product');
    });

    testWidgets('the league card is gone and the streak chip is not',
        (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      // The league card is CR109 Amendment A's removal; the streak chip stays
      // until CR109 re-homes it (§3). Two neighbouring widgets, opposite fates
      // — worth pinning so the next edit does not take both.
      expect(find.byType(FloorOmnibox), findsOneWidget);
      expect(find.textContaining('Weekly League'), findsNothing);
    });
  });

  group('acceptance #10 — the tour is three stops', () {
    testWidgets('carousel, omnibox, firm row — and nothing else', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      final l = await AppLocalizations.delegate.load(const Locale('en'));
      final targets = buildFloorTargets(
        l: l,
        carouselKey: GlobalKey(),
        omniboxKey: GlobalKey(),
        firmKey: GlobalKey(),
      );
      expect(targets.map((x) => x.identify).toList(),
          ['floor_carousel', 'floor_omnibox', 'floor_firm'],
          reason: '§5.10 — five stops was the symptom, not the fix: a landing '
              'screen that needs five explanations does not explain itself');
    });
  });
}