/// CR109 slice 3b — the duel card. Design §11.1.
///
/// At alpha field sizes the duel IS the competition: the open board needs
/// `n >= 8` before placement means anything, and every field is below that.
/// So this card is the surface that has to carry the contest, and the two
/// ways it can lie are what these tests pin.
///
/// **One: the sign.** Both TWRs are on the wire, so a client could subtract
/// them — and one that got it backwards would tell a losing player they were
/// ahead. The server sends a signed `lead_pct`; this card reads it and never
/// re-derives it.
///
/// **Two: the null.** A duel where either side has no close yet has an
/// UNKNOWN gap, which is not the same as a level one. Drawing it as level
/// would announce a dead heat that is not happening — the ninth-instance
/// `?? 0` bug class this feature keeps producing.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_run_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

GameRunDetail _detail({GameDuel? duel}) => GameRunDetail(
      runId: _runId,
      fieldId: 'f1',
      cadence: 'week',
      state: 'active',
      stake: 10000,
      cash: 5000,
      holdings: const [
        GameHolding(ticker: 'AAPL', quantity: 4, avgCost: 150, mark: 180),
      ],
      duel: duel,
      priceSource: 'yfinance',
      daysLeft: 3,
      twrPct: 1.0,
    );

Future<void> _pump(WidgetTester tester, {GameDuel? duel}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
        gamesRunDetailProvider(_runId)
            .overrideWith((ref) async => _detail(duel: duel)),
        gamesQueuedOrdersProvider(_runId).overrideWith((ref) async => []),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesRunScreen(runId: _runId),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

const _live = GameDuel(
  kind: 'auto',
  cadence: 'week',
  state: 'live',
  opponentHandle: 'VECTOR_11',
  opponentTwrPct: 0.4,
  myTwrPct: 1.5,
  leadPct: 1.1,
  pointsAtStake: 10,
);

void main() {
  group('the opponent is named', () {
    testWidgets('§11.1 — naming one opponent is what a thin field lacks',
        (tester) async {
      await _pump(tester, duel: _live);
      expect(find.textContaining('VECTOR_11'), findsOneWidget);
      expect(find.text('DUEL'), findsOneWidget);
    });

    testWidgets('a run with no duel shows no card at all', (tester) async {
      await _pump(tester);
      expect(find.text('DUEL'), findsNothing);
      expect(find.text('YOUR FIRST RUN'), findsNothing);
      // Not an error state and not an empty card — an odd player out simply
      // is not paired, and the rest of the screen is unaffected.
      expect(find.text('POSITIONS'), findsOneWidget);
    });

    testWidgets('a first-run duel is framed as the first run, not as a duel',
        (tester) async {
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'first_run',
          cadence: 'week',
          state: 'live',
          opponentHandle: 'INDEX_DESK',
          opponentIsDesk: true,
          opponentDeskRule: 'Holds the benchmark (SPY) for the whole run.',
          leadPct: -0.3,
          pointsAtStake: 10,
        ),
      );
      expect(find.text('YOUR FIRST RUN'), findsOneWidget);
      expect(find.text('DUEL'), findsNothing);
    });

    testWidgets('a desk opponent discloses its published rule', (tester) async {
      // "Beat the Index Desk" only means something if the player knows the
      // desk holds the benchmark.
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'first_run',
          cadence: 'week',
          state: 'live',
          opponentHandle: 'INDEX_DESK',
          opponentIsDesk: true,
          opponentDeskRule: 'Holds the benchmark (SPY) for the whole run.',
          leadPct: 0.5,
        ),
      );
      expect(find.textContaining('Holds the benchmark'), findsOneWidget);
    });
  });

  group('the sign of the lead', () {
    testWidgets('ahead reads as ahead', (tester) async {
      await _pump(tester, duel: _live);
      expect(find.textContaining('1.10% ahead'), findsOneWidget);
    });

    testWidgets('behind reads as behind, with the magnitude unsigned',
        (tester) async {
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto',
          cadence: 'week',
          state: 'live',
          opponentHandle: 'VECTOR_11',
          leadPct: -2.25,
        ),
      );
      expect(find.textContaining('2.25% behind'), findsOneWidget);
      expect(find.textContaining('ahead'), findsNothing);
      // The magnitude is printed unsigned — "−2.25% behind" would read as a
      // double negative.
      expect(find.textContaining('-2.25'), findsNothing);
    });

    test('isAhead is false on an unknown gap, not just on a losing one', () {
      const unknown = GameDuel(
        kind: 'auto', cadence: 'week', state: 'live',
        opponentHandle: 'X', leadPct: null,
      );
      const losing = GameDuel(
        kind: 'auto', cadence: 'week', state: 'live',
        opponentHandle: 'X', leadPct: -1.0,
      );
      const level = GameDuel(
        kind: 'auto', cadence: 'week', state: 'live',
        opponentHandle: 'X', leadPct: 0.0,
      );
      expect(unknown.isAhead, isFalse);
      expect(losing.isAhead, isFalse);
      // Level is not ahead either — `>= 0` would have called this a lead.
      expect(level.isAhead, isFalse);
    });
  });

  group('unknown is not level', () {
    testWidgets('no closes yet says the gap is not measurable', (tester) async {
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto',
          cadence: 'week',
          state: 'live',
          opponentHandle: 'VECTOR_11',
          leadPct: null,
        ),
      );
      expect(find.textContaining('not measurable'), findsOneWidget);
      expect(find.text('Dead level'), findsNothing);
    });

    testWidgets('a measured tie DOES say dead level', (tester) async {
      // The mutation guard for the test above: if "unknown" were rendered
      // through the same branch as "level", scoring both as level would pass.
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto',
          cadence: 'week',
          state: 'live',
          opponentHandle: 'VECTOR_11',
          leadPct: 0.0,
        ),
      );
      expect(find.text('Dead level'), findsOneWidget);
      expect(find.textContaining('not measurable'), findsNothing);
    });
  });

  group('settled outcomes', () {
    testWidgets('a win states the points gained', (tester) async {
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto', cadence: 'week', state: 'settled',
          opponentHandle: 'VECTOR_11', leadPct: 2.0,
          outcome: 'won', pointsDelta: 10,
        ),
      );
      expect(find.textContaining('You won'), findsOneWidget);
      expect(find.textContaining('10'), findsWidgets);
    });

    testWidgets('a void is stated, never drawn as a draw', (tester) async {
      // Unmeasurable is a different thing from tied, and CR040 requires the
      // difference be visible rather than collapsed into the friendlier one.
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto', cadence: 'week', state: 'void',
          opponentHandle: 'VECTOR_11', outcome: 'void',
        ),
      );
      expect(find.textContaining('could not be measured'), findsOneWidget);
      expect(find.textContaining('A draw'), findsNothing);
    });

    testWidgets('a settled duel shows no points-at-stake line', (tester) async {
      await _pump(
        tester,
        duel: const GameDuel(
          kind: 'auto', cadence: 'week', state: 'settled',
          opponentHandle: 'VECTOR_11', leadPct: 2.0,
          outcome: 'won', pointsDelta: 10,
        ),
      );
      expect(find.text('10 pts'), findsNothing);
    });
  });

  group('the wire contract', () {
    test('the duel parses off the run-detail payload', () {
      final d = GameRunDetail.fromJson(const {
        'run_id': _runId,
        'current_cash': 5000.0,
        'holdings': [],
        'duel': {
          'kind': 'first_run',
          'cadence': 'week',
          'state': 'live',
          'opponent': {
            'handle': 'INDEX_DESK',
            'is_desk': true,
            'desk_key': 'index',
            'desk_rule': 'Holds the benchmark (SPY) for the whole run.',
            'twr_pct': 0.8,
          },
          'my_twr_pct': 1.9,
          'lead_pct': 1.1,
          'outcome': null,
          'points_delta': 0,
          'points_at_stake': 10,
        },
      });
      expect(d.duel, isNotNull);
      expect(d.duel!.opponentHandle, 'INDEX_DESK');
      expect(d.duel!.opponentIsDesk, isTrue);
      expect(d.duel!.leadPct, 1.1);
      expect(d.duel!.isFirstRun, isTrue);
      expect(d.duel!.isLive, isTrue);
    });

    test('a null lead_pct survives as null and is never coerced to zero', () {
      final d = GameRunDetail.fromJson(const {
        'run_id': _runId,
        'current_cash': 5000.0,
        'holdings': [],
        'duel': {
          'kind': 'auto',
          'cadence': 'week',
          'state': 'live',
          'opponent': {'handle': 'VECTOR_11', 'twr_pct': null},
          'my_twr_pct': null,
          'lead_pct': null,
        },
      });
      expect(d.duel!.leadPct, isNull);
      expect(d.duel!.opponentTwrPct, isNull);
      expect(d.duel!.myTwrPct, isNull);
    });

    test('a payload with no duel key yields null, never an empty duel', () {
      final d = GameRunDetail.fromJson(const {
        'run_id': _runId,
        'current_cash': 5000.0,
        'holdings': [],
      });
      expect(d.duel, isNull);
    });

    test('the wire carries no currency figure for either side', () {
      // §6.1, applied to the surface where the temptation is strongest: a
      // duel is the only place two books are deliberately compared.
      const payload = {
        'kind': 'auto',
        'cadence': 'week',
        'state': 'live',
        'opponent': {'handle': 'VECTOR_11', 'twr_pct': 0.4},
        'my_twr_pct': 1.5,
        'lead_pct': 1.1,
      };
      final keys = {...payload.keys, ...(payload['opponent'] as Map).keys};
      for (final banned in ['cash', 'total_value', 'nav', 'stake']) {
        expect(keys.contains(banned), isFalse, reason: '$banned on the wire');
      }
    });
  });
}
