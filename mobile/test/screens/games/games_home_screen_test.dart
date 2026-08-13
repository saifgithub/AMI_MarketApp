/// CR109 slice 2 — the landing screen's state machine (implementation_plan.md
/// §8.2): only state B (a live run) and the shared A/C fallback ship this
/// slice. Mirrors `portfolio_equity_chart_test.dart`'s harness shape —
/// override the read providers directly, pump just the screen.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_home_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(
  WidgetTester tester, {
  required List<GameRunSummary> runs,
  List<GameCadenceInfo> cadences = const [],
}) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesRunsProvider.overrideWith((ref) async => runs),
        gamesCadencesProvider.overrideWith((ref) async => cadences),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesHomeScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  group('DEF284 — the lobby door exists in BOTH states', () {
    /// The CTA used to live in `_NextFieldFallback` only, and `build` renders
    /// that branch just while you hold no live run — so entering the weekly
    /// game removed the only route to the other four cadences, at exactly the
    /// moment you would go looking for it. Saiful, on 0.1.0+88: *"I am in the
    /// weekly game. How do I join the other available cadence?"*
    ///
    /// Both states are asserted rather than only the broken one, because the
    /// bug was never "the button is missing" — it was "the button is in one
    /// branch of a two-branch screen."
    testWidgets('holding a live run still offers ALL GAMES', (tester) async {
      await _pump(
        tester,
        runs: [
          const GameRunSummary(
            runId: 'r1', fieldId: 'f1', cadence: 'week',
            twrPct: 2.35, daysLeft: 3, state: 'active',
          ),
        ],
      );

      expect(find.text('ALL GAMES'), findsOneWidget);
    });

    testWidgets('holding no run offers ALL GAMES too', (tester) async {
      await _pump(tester, runs: const []);

      expect(find.text('ALL GAMES'), findsOneWidget);
    });
  });

  group('state B — a run is live', () {
    testWidgets('shows the run card, not the fallback card', (tester) async {
      await _pump(
        tester,
        runs: [
          const GameRunSummary(
            runId: 'r1',
            fieldId: 'f1',
            cadence: 'week',
            twrPct: 2.35,
            daysLeft: 3,
            state: 'active',
          ),
        ],
      );

      expect(find.text('+2.35%'), findsOneWidget);
      expect(find.text('TRADE'), findsOneWidget);
      expect(find.text('Enter the next weekly field'), findsNothing,
          reason: 'state B must not also render the A/C fallback card');
    });

    testWidgets('negative TWR renders without a leading +', (tester) async {
      await _pump(
        tester,
        runs: [
          const GameRunSummary(
            runId: 'r1',
            fieldId: 'f1',
            cadence: 'week',
            twrPct: -1.2,
            daysLeft: 1,
            state: 'active',
          ),
        ],
      );
      expect(find.text('-1.20%'), findsOneWidget);
    });

    testWidgets('a finished run does not count as live', (tester) async {
      await _pump(
        tester,
        runs: [
          const GameRunSummary(
            runId: 'r1',
            fieldId: 'f1',
            cadence: 'week',
            twrPct: 4.0,
            state: 'finished',
          ),
        ],
        cadences: const [GameCadenceInfo(cadence: 'week')],
      );
      // No live run → falls to the shared fallback, not the run card.
      expect(find.text('Enter the next weekly field'), findsOneWidget);
      expect(find.text('TRADE'), findsNothing);
    });
  });

  group('states A/C — the shared fallback (implementation_plan.md §8.2)',
      () {
    testWidgets('no live runs shows the single next-field card, not a lobby',
        (tester) async {
      await _pump(
        tester,
        runs: const [],
        cadences: const [
          GameCadenceInfo(
            cadence: 'week',
            nextField: GameFieldSummary(fieldId: 'f2', entrantCount: 7),
          ),
        ],
      );

      expect(find.text('Enter the next weekly field'), findsOneWidget);
      expect(find.text("ENTER THIS WEEK'S FIELD"), findsOneWidget);
      expect(find.text('7 traders already in'), findsOneWidget);
      // The five-cadence lobby is explicitly NOT this screen (design §13.3).
      expect(find.text('month'), findsNothing);
      expect(find.text('quarter'), findsNothing);
    });

    testWidgets('the enter CTA is disabled once the cadence is already held',
        (tester) async {
      await _pump(
        tester,
        runs: const [],
        cadences: const [
          GameCadenceInfo(cadence: 'week', alreadyHolds: true),
        ],
      );

      final button = tester.widget<GestureDetector>(
        find.ancestor(
          of: find.text("ENTER THIS WEEK'S FIELD"),
          matching: find.byType(GestureDetector),
        ),
      );
      expect(button.onTap, isNull);
    });
  });
}
