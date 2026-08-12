/// CR109 slice 5 — the period arc's beat card and the Wind-Up.
///
/// The properties under test are the two fences the design puts on this
/// surface, plus the one that keeps the ceremony from breaking the product:
///
///   - **The near-miss points up only.** §10 permits *"2nd is 1.1% ahead"*
///     and forbids the downward twin. The client cannot cross that line
///     because [GameArc] carries no number for it — asserted here as an
///     absence in the rendered output, not as a copy review.
///   - **Day one shows no standing.** An unmeasured run and a run that is
///     exactly flat are different facts; rendering a rank of 0 or a gap of
///     0.0 collapses them. This is the `?? 0` class that has bitten this
///     feature repeatedly.
///   - **The beat never blocks the book.** The run screen below it is the
///     actual product; a failed arc call renders nothing at all.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/widgets/games/games_arc_beat.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ami_trade/state/games_providers.dart';

const _runId = 'run-1';

Future<void> _pumpArc(WidgetTester tester, GameArc? arc) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesArcProvider(_runId).overrideWith((ref) async {
          if (arc == null) throw Exception('arc unavailable');
          return arc;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: GamesArcBeat(runId: _runId)),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

GameArc _arc({
  String phase = GameArcPhase.live,
  int daysLeft = 4,
  int entrantCount = 8,
  bool standingsOpen = true,
  int? yourRank = 4,
  double? yourTwrPct = 2.3,
  double? gapToNextPct,
  int? gapToNextRank,
  GameAttribution? attribution,
  DateTime? locksAt,
}) =>
    GameArc(
      runId: _runId,
      cadence: 'week',
      phase: phase,
      daysLeft: daysLeft,
      entrantCount: entrantCount,
      standingsOpen: standingsOpen,
      yourRank: yourRank,
      yourTwrPct: yourTwrPct,
      gapToNextPct: gapToNextPct,
      gapToNextRank: gapToNextRank,
      attribution: attribution,
      locksAt: locksAt,
    );

void main() {
  group('the beat card', () {
    testWidgets('states your standing out of the ranked field',
        (tester) async {
      await _pumpArc(tester, _arc());

      expect(find.textContaining("You're 4th of 8"), findsOneWidget);
    });

    testWidgets('the gap points UP at the entrant above, and only up',
        (tester) async {
      await _pumpArc(
        tester,
        _arc(gapToNextPct: 1.1, gapToNextRank: 2),
      );

      expect(find.textContaining('2nd is 1.1% ahead'), findsOneWidget);
      // The downward twin — "you are x% from dropping a place" — cannot be
      // written because no number for it exists in the payload.
      expect(find.textContaining('behind you'), findsNothing);
      expect(find.textContaining('drop'), findsNothing);
    });

    testWidgets('day one says standings are closed, never a rank of zero',
        (tester) async {
      await _pumpArc(
        tester,
        _arc(standingsOpen: false, yourRank: null, yourTwrPct: null),
      );

      expect(find.textContaining('Standings open after'), findsOneWidget);
      expect(find.textContaining('0th'), findsNothing);
      expect(find.textContaining('0.0% ahead'), findsNothing);
    });

    testWidgets('attribution names the mover against the run total',
        (tester) async {
      await _pumpArc(
        tester,
        _arc(
          attribution: const GameAttribution(
            ticker: 'NVDA',
            pctPoints: 1.9,
            priceSource: 'live',
          ),
        ),
      );

      expect(
        find.textContaining('NVDA drove +1.9pp of your +2.30%'),
        findsOneWidget,
      );
    });

    testWidgets('a mock-priced attribution is caveated, not shown as fact',
        (tester) async {
      await _pumpArc(
        tester,
        _arc(
          attribution: const GameAttribution(
            ticker: 'NVDA',
            pctPoints: 1.9,
            priceSource: 'mock',
          ),
        ),
      );

      final l = await AppLocalizations.delegate.load(const Locale('en'));
      expect(find.text(l.gamesRunMarksStaleNote), findsOneWidget);
    });

    testWidgets('the entry-open beat counts down to the lock', (tester) async {
      await _pumpArc(
        tester,
        _arc(
          phase: GameArcPhase.entryOpen,
          locksAt: DateTime.now().add(const Duration(hours: 2, minutes: 14)),
        ),
      );

      expect(find.textContaining('Entries close in 2h'), findsOneWidget);
    });

    testWidgets('the bell reveals the field size', (tester) async {
      await _pumpArc(tester, _arc(phase: GameArcPhase.bell));

      expect(find.textContaining('8 entrants'), findsOneWidget);
    });

    testWidgets('the settling beat withholds the result', (tester) async {
      await _pumpArc(tester, _arc(phase: GameArcPhase.settling, daysLeft: 0));

      expect(find.textContaining('being scored'), findsOneWidget);
      expect(find.textContaining("You're"), findsNothing);
    });

    testWidgets('an unavailable arc renders nothing rather than an error',
        (tester) async {
      await _pumpArc(tester, null);

      expect(find.byKey(const Key('games_arc_beat')), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  group('the countdown format', () {
    test('is coarse — never a ticking seconds display', () {
      expect(formatCountdown(const Duration(days: 3, hours: 4)), '3d 4h');
      expect(formatCountdown(const Duration(hours: 2, minutes: 14)), '2h 14m');
      expect(formatCountdown(const Duration(minutes: 8)), '8m');
      expect(formatCountdown(const Duration(seconds: -5)), '0m');
    });
  });

  group('rank ordinals', () {
    test('handle the teens, which the naive rule gets wrong', () {
      expect(rankOrdinal(1), '1st');
      expect(rankOrdinal(2), '2nd');
      expect(rankOrdinal(3), '3rd');
      expect(rankOrdinal(4), '4th');
      expect(rankOrdinal(11), '11th');
      expect(rankOrdinal(12), '12th');
      expect(rankOrdinal(13), '13th');
      expect(rankOrdinal(21), '21st');
    });
  });

  group('the Wind-Up model', () {
    test('reads the nested worst-contributor block', () {
      final windUp = GameWindUp.fromJson(const {
        'reason': 'busted',
        'final_twr_pct': -100.0,
        'nav_shortfall': 240.0,
        'worst': {'ticker': 'TSLA', 'pct_points': -62.4},
        'trade_count': 7,
      });

      expect(windUp.isBust, isTrue);
      expect(windUp.hasWorst, isTrue);
      expect(windUp.worstTicker, 'TSLA');
      expect(windUp.navShortfall, 240.0);
    });

    test('a run with no stored attribution still winds up', () {
      final windUp = GameWindUp.fromJson(const {
        'reason': 'heavy_loss',
        'final_twr_pct': -22.0,
        'worst': null,
      });

      expect(windUp.hasWorst, isFalse);
      expect(windUp.isBust, isFalse);
    });

    test('the Close carries no wind_up on an ordinary close', () {
      final close = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'field_id': 'f1',
        'cadence': 'week',
        'wind_up': null,
      });

      expect(close.isWindUp, isFalse);
    });
  });
}
