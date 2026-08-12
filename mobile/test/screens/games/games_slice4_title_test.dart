/// CR109 slice 4 — the title on the Record, and the rank's honest denominator.
///
/// Two surfaces, one property each:
///
///   - The Record states the rung above and the distance to it. Amendment D
///     correction 3's finding was that the median player — oscillating around
///     `p = 0.5` and netting ~0 per run BY CONSTRUCTION — can see no
///     progression at all. A running total that moves on placement noise says
///     nothing about where it is going.
///   - The Close shows a rank out of the number it was actually taken over,
///     never out of everyone who entered. "3rd of 9" in a field where two runs
///     voided is a sentence about a contest that did not happen.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_record_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, GameRecord record) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesRecordProvider.overrideWith((ref) async => record),
        gamesRecordPrsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesRecordScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  group('the title and the rung above it', () {
    testWidgets('a new player is pointed at the milestone, not at 500 points',
        (tester) async {
      await _pump(
        tester,
        const GameRecord(
          careerPoints: 8,
          finishedCount: 1,
          title: 'apprentice',
          nextTitle: GameTitleGoal(
            title: 'associate',
            requirement: 'finished_runs',
            remaining: 2,
          ),
        ),
      );

      expect(find.text('APPRENTICE'), findsOneWidget);
      expect(find.textContaining('2 more finished runs'), findsOneWidget);
      expect(find.textContaining('ASSOCIATE'), findsOneWidget);
    });

    testWidgets('a points rung is stated in points, not in runs',
        (tester) async {
      // The two units are NOT interchangeable: the milestone counts runs,
      // every rung above it counts points, and rendering the wrong one
      // describes a threshold that does not exist.
      await _pump(
        tester,
        const GameRecord(
          careerPoints: 380,
          finishedCount: 9,
          title: 'associate',
          nextTitle: GameTitleGoal(
            title: 'analyst',
            requirement: 'career_points',
            remaining: 120,
          ),
        ),
      );

      expect(find.text('ASSOCIATE'), findsOneWidget);
      expect(find.textContaining('120 career points'), findsOneWidget);
      expect(find.textContaining('finished runs'), findsNothing);
    });

    testWidgets('the top of the ladder shows no goal line', (tester) async {
      await _pump(
        tester,
        const GameRecord(
          careerPoints: 31000,
          finishedCount: 40,
          title: 'floor_veteran',
        ),
      );

      expect(find.text('FLOOR_VETERAN'), findsOneWidget);
      // Neither goal string, in either unit — there is nothing above this
      // rung, and inventing a target would be the goal gradient lying.
      expect(find.textContaining('career points to'), findsNothing);
      expect(find.textContaining('finished run'), findsNothing);
    });

    testWidgets('a backend with no title renders no identity section',
        (tester) async {
      // The mutation guard. A section that rendered unconditionally would
      // put an empty rung on the Record of every player served by a backend
      // that predates slice 4.
      await _pump(tester, const GameRecord(careerPoints: 8, finishedCount: 1));

      expect(find.text('IDENTITY'), findsNothing);
      expect(find.text('CAREER POINTS'), findsOneWidget);
    });
  });

  group('the rank is shown out of what it was taken over', () {
    GameCloseResult close({int entrants = 9, int? scored}) => GameCloseResult(
          runId: 'r1',
          fieldId: 'f1',
          cadence: 'week',
          state: 'finished',
          scoringBasis: 'placement',
          entrantCount: entrants,
          scoredEntrantCount: scored,
          rank: 3,
        );

    test('prefers the scored count over everyone who entered', () {
      // Two of the nine voided, so it was a field of seven.
      expect(close(entrants: 9, scored: 7).rankedFieldSize, 7);
    });

    test('falls back to the field total for a pre-slice-4 run', () {
      expect(close(entrants: 9, scored: null).rankedFieldSize, 9);
    });

    test('never falls back to zero', () {
      // "1st of 0" is the one rendering worse than showing the wider
      // number — a `?? 0` here would produce it on every legacy row.
      expect(close(entrants: 9, scored: 0).rankedFieldSize, 9);
    });

    test('a placed field reads its own size', () {
      expect(close(entrants: 8, scored: 8).rankedFieldSize, 8);
    });
  });
}
