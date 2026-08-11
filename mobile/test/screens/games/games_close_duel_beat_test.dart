/// CR109 slice 3b — the duel verdict as beat 2 of the Close. Design §10.2.
///
/// > **Budget: three beats.**
/// > **1 — The result.** **2 — One insight**, chosen by priority: the duel
/// > verdict on a first run · the post-mortem on a blowup · the near-miss ·
/// > otherwise the counterfactual. **3 — The way back in.**
///
/// The budget exists because the Close had become *"eleven blocks on a
/// screen whose entire job is one emotional payoff"* — a report with
/// confetti. So the two things these tests pin are: **exactly one insight
/// renders**, and the client **obeys** the server's choice rather than
/// making its own (the priority rule is written down in one place, and a
/// client that re-derived it would drift from it).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_close_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _runId = 'run-1';

GameCloseResult _result({GameCloseDuel? duel}) => GameCloseResult(
      runId: _runId,
      fieldId: 'f1',
      cadence: 'week',
      state: 'finished',
      scoringBasis: 'benchmark',
      entrantCount: 6,
      rank: 2,
      careerPointsDelta: 21,
      finalTwrPct: 4.0,
      alphaScored: 1.0,
      alphaDisplay: 1.3,
      counterfactualFirstPicksPct: 2.1,
      counterfactualIndexPct: 0.6,
      duelVerdict: duel,
    );

Future<void> _pump(WidgetTester tester, {required GameCloseResult result}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesCloseProvider(_runId).overrideWith((ref) async => result),
        gamesCadencesProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesCloseScreen(runId: _runId),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 700));
}

void main() {
  group('the duel takes beat 2 when the server chose it', () {
    testWidgets('a first-run win reads as beating the market', (tester) async {
      // Not "you beat INDEX_DESK": a beginner has no duel history to read a
      // handle against, and "beat the market" needs no tutorial.
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'won',
            duelKind: 'first_run',
            opponentHandle: 'INDEX_DESK',
            opponentIsDesk: true,
            opponentDeskRule: 'Holds the benchmark (SPY) for the whole run.',
            marginPct: 3.2,
            pointsDelta: 10,
          ),
        ),
      );
      expect(find.text('You beat the market.'), findsOneWidget);
      expect(find.textContaining('INDEX_DESK'), findsNothing);
    });

    testWidgets('a first-run loss says so plainly', (tester) async {
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'lost',
            duelKind: 'first_run',
            opponentHandle: 'INDEX_DESK',
            opponentIsDesk: true,
            marginPct: -1.4,
            pointsDelta: 10,
          ),
        ),
      );
      expect(find.text('The market beat you.'), findsOneWidget);
    });

    testWidgets('a human duel names the opponent', (tester) async {
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'won',
            opponentHandle: 'VECTOR_11',
            marginPct: 0.9,
            pointsDelta: 10,
          ),
        ),
      );
      expect(find.textContaining('VECTOR_11'), findsOneWidget);
    });

    testWidgets('the margin renders unsigned — the headline carries the sign',
        (tester) async {
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'lost',
            opponentHandle: 'VECTOR_11',
            marginPct: -1.4,
            pointsDelta: 10,
          ),
        ),
      );
      // "By −1.4%" under "VECTOR_11 beat you" reads as a double negative.
      expect(find.textContaining('1.4'), findsOneWidget);
      expect(find.textContaining('-1.4'), findsNothing);
      expect(find.textContaining('−1.4'), findsNothing);
    });

    testWidgets('a desk opponent still discloses its published rule',
        (tester) async {
      // "You beat the market" is a claim the player can check, not one they
      // have to take on trust.
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'won',
            duelKind: 'first_run',
            opponentHandle: 'INDEX_DESK',
            opponentIsDesk: true,
            opponentDeskRule: 'Holds the benchmark (SPY) for the whole run.',
            marginPct: 3.2,
            pointsDelta: 10,
          ),
        ),
      );
      expect(find.textContaining('Holds the benchmark'), findsOneWidget);
    });
  });

  group('exactly one insight', () {
    testWidgets('the counterfactual does NOT also render beside a duel',
        (tester) async {
      // The three-beat budget. Both would be "a report with confetti", which
      // is the thing §10.2 exists to prevent.
      await _pump(
        tester,
        result: _result(
          duel: const GameCloseDuel(
            outcome: 'won',
            opponentHandle: 'VECTOR_11',
            marginPct: 0.9,
            pointsDelta: 10,
          ),
        ),
      );
      expect(find.byKey(const Key('games_close_beat_insight')), findsOneWidget);
      expect(find.textContaining('first picks'), findsNothing);
      expect(find.textContaining('held the'), findsNothing);
    });

    testWidgets('with no duel the counterfactual still renders', (tester) async {
      // The mutation guard: wiring the duel in must not have removed the
      // fallback that the majority of runs use.
      await _pump(tester, result: _result());
      expect(find.byKey(const Key('games_close_beat_insight')), findsOneWidget);
      expect(find.textContaining('2.1'), findsWidgets);
    });
  });

  group('the client obeys the server\'s choice', () {
    test('a counterfactual insight yields no duel verdict', () {
      final r = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'state': 'finished',
        'counterfactual_hold_index_pct': 0.6,
        'beats': {
          'insight': {
            'kind': 'counterfactual',
            'hold_index_pct': 0.6,
            'hold_first_picks_pct': 2.1,
          },
        },
      });
      expect(r.duelVerdict, isNull);
    });

    test('a duel insight parses, including the renamed duel_kind', () {
      // `duel_kind`, not `kind` — the envelope uses `kind` as its own
      // discriminator, and the duel's own value ('first_run') silently
      // overwrote it until this was renamed.
      final r = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'state': 'finished',
        'beats': {
          'insight': {
            'kind': 'duel',
            'duel_kind': 'first_run',
            'state': 'settled',
            'outcome': 'won',
            'opponent_handle': 'INDEX_DESK',
            'opponent_is_desk': true,
            'opponent_desk_rule': 'Holds the benchmark (SPY).',
            'my_twr_pct': 4.0,
            'opponent_twr_pct': 0.8,
            'margin_pct': 3.2,
            'points_delta': 10,
          },
        },
      });
      expect(r.duelVerdict, isNotNull);
      expect(r.duelVerdict!.outcome, 'won');
      expect(r.duelVerdict!.isFirstRun, isTrue);
      expect(r.duelVerdict!.marginPct, 3.2);
      expect(r.duelVerdict!.pointsDelta, 10);
    });

    test('a payload with no beats yields no duel verdict', () {
      final r = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'state': 'finished',
      });
      expect(r.duelVerdict, isNull);
    });

    test('an unrecognised insight kind yields no duel verdict', () {
      // A future beat kind (the paid post-mortem) must not be mistaken for a
      // duel just because it is not a counterfactual.
      final r = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'state': 'finished',
        'beats': {
          'insight': {'kind': 'post_mortem', 'summary': '...'},
        },
      });
      expect(r.duelVerdict, isNull);
    });
  });
}
