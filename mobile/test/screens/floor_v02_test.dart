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
import 'package:ami_trade/models/sector_watch.dart';
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
  // Day-0 by default: card 3 teaches, so the default carousel is 3 cards.
  SectorWatch sector = const SectorWatch(state: 'empty'),
  bool sectorError = false,
  // Quote / reconstructed-close fixtures for the CR184 delta column. Absent
  // ticker == the read failed == dash (CR040), same as the live providers.
  Map<String, double?> prices = const {},
  ({double close, DateTime date})? conveneClose,
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
      sectorWatchProvider.overrideWith((ref) async =>
          sectorError ? throw Exception('feed down') : sector),
      callPriceProvider.overrideWith((ref, ticker) async => prices[ticker]),
      conveneCloseProvider.overrideWith((ref, k) async => conveneClose),
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
      // Three cards at rest: portfolio, calls, sector. The NOT ACTIONED card
      // is collapsed (nothing unactioned in the default fixture) — its dot
      // must not exist, because a dot for an omitted card is a blank frame.
      await _pumpFloor(t, portfolio: _portfolio());
      expect(find.bySemanticsLabel('card 1 of 3'), findsOneWidget);
      expect(find.bySemanticsLabel('card 3 of 3'), findsOneWidget);
      expect(find.bySemanticsLabel('card 4 of 4'), findsNothing);
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

  group('CR183 — SECTOR WATCH is card 3', () {
    const ok = SectorWatch(
      state: 'ok',
      sector: 'Technology',
      movePct: 2.0,
      leader: 'NVDA',
      leaderChangePct: 3.0,
      tickersConsidered: 3,
      headline: SectorHeadline(
          title: 'Blackwell demand outpaces supply', publisher: 'Reuters'),
      quoteSource: 'yfinance',
      newsSource: 'yfinance',
    );

    Future<void> toCard3(WidgetTester t) async {
      await t.drag(find.byType(PageView), const Offset(-400, 0));
      await t.pumpAndSettle();
      await t.drag(find.byType(PageView), const Offset(-400, 0));
      await t.pumpAndSettle();
    }

    testWidgets('day-0 teaches what fills the card', (t) async {
      await _pumpFloor(t, portfolio: _portfolio());
      await toCard3(t);
      expect(find.textContaining('Follow a ticker'), findsOneWidget,
          reason: 'acceptance #4 — cards 2-3 collapse or teach when empty; '
              'this one teaches');
    });

    testWidgets('renders the glance line and the leader\'s headline',
        (t) async {
      await _pumpFloor(t, portfolio: _portfolio(), sector: ok);
      await toCard3(t);
      expect(find.textContaining('Technology +2.0% — NVDA leads.'),
          findsOneWidget);
      expect(find.textContaining('Blackwell demand'), findsOneWidget);
    });

    testWidgets('a feed it cannot read says so — never a flat 0.0%',
        (t) async {
      await _pumpFloor(t,
          portfolio: _portfolio(),
          sector: const SectorWatch(
              state: 'unavailable', reason: 'no_live_quotes'));
      await toCard3(t);
      expect(find.textContaining('sector feed'), findsOneWidget);
      expect(find.textContaining('0.0%'), findsNothing,
          reason: 'CR040 — an unreadable feed rendered as a zero move is a '
              'fabricated measurement');
    });

    testWidgets('an unrecognised state renders as unavailable, never as ok',
        (t) async {
      await _pumpFloor(t,
          portfolio: _portfolio(),
          sector: const SectorWatch(state: 'brand_new_state'));
      await toCard3(t);
      expect(find.textContaining('sector feed'), findsOneWidget);
    });

    testWidgets('the glance is a tap target for the leader (rule 3)',
        (t) async {
      await _pumpFloor(t, portfolio: _portfolio(), sector: ok);
      await toCard3(t);
      final tap = find.byKey(const Key('sector_watch_tap'));
      expect(tap, findsOneWidget);
      expect(t.widget<InkWell>(tap).onTap, isNotNull,
          reason: 'rule 3 — the card is a glance whose real home is the '
              'leader\'s TickerDetail screen');
    });
  });

  group('CR184 — NOT ACTIONED is card 4, collapsed when empty', () {
    final approve = TeamCall(
        ticker: 'NVDA',
        action: 'APPROVE',
        at: DateTime(2026, 8, 10),
        entry: 100.0,
        actioned: false);
    final pass = TeamCall(
        ticker: 'AAPL',
        action: 'PASS',
        at: DateTime(2026, 8, 12),
        actioned: false);

    Future<void> toCard4(WidgetTester t) async {
      for (var i = 0; i < 3; i++) {
        await t.drag(find.byType(PageView), const Offset(-400, 0));
        await t.pumpAndSettle();
      }
    }

    testWidgets('collapses entirely when nothing is unactioned — and null '
        'is N/A, never false', (t) async {
      await _pumpFloor(t, portfolio: _portfolio(), calls: [
        TeamCall(
            ticker: 'MSFT',
            action: 'APPROVE',
            at: DateTime(2026, 8, 10),
            entry: 50.0,
            actioned: true),
        TeamCall(
            ticker: 'TSLA',
            action: 'PASS',
            at: DateTime(2026, 8, 11),
            actioned: null),
      ]);
      expect(find.byType(UnactionedCallsCard), findsNothing,
          reason: 'everything actioned (or N/A) needs no permanent card — '
              'acceptance #4 says collapse or teach, this card collapses');
      expect(find.bySemanticsLabel('card 1 of 3'), findsOneWidget);
    });

    testWidgets('shows an APPROVE and a PASS with measured, framed deltas',
        (t) async {
      await _pumpFloor(t,
          portfolio: _portfolio(),
          calls: [pass, approve],
          prices: const {'NVDA': 110.0, 'AAPL': 210.0},
          conveneClose: (close: 200.0, date: DateTime(2026, 8, 12)));
      await toCard4(t);
      expect(find.byType(UnactionedCallsCard), findsOneWidget);
      // APPROVE: measured against the entry the PM named (100 → 110).
      expect(find.textContaining('+10.0% since the call'), findsOneWidget);
      // PASS: measured against the reconstructed convene-day close
      // (200 → 210), disclosed as such.
      expect(
          find.textContaining('+5.0% vs close on Aug 12'), findsOneWidget);
    });

    testWidgets(
        'a PASS whose close cannot be honestly read renders a dash, not a '
        'number', (t) async {
      await _pumpFloor(t,
          portfolio: _portfolio(),
          calls: [pass],
          prices: const {'AAPL': 210.0},
          // What conveneDayClose returns for a mock_walk (or unread) history.
          conveneClose: null);
      await toCard4(t);
      expect(
          find.descendant(
              of: find.byType(UnactionedCallsCard),
              matching: find.text('—')),
          findsOneWidget,
          reason: 'CR040 — a delta against a fabricated close is a number '
              'that looks measured and is not');
      expect(find.textContaining('vs close on'), findsNothing);
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