/// CR109 slice 3 — the Close's three-beat ceremony budget (design §10.2)
/// and the Wind-Up's dignified forfeit framing (§10, §6.7). Same harness
/// shape as games_home_screen_test.dart: override the read providers
/// directly, pump just the screen.
///
/// Numeric values the screen renders through `_isolateNumeric` (the T-BIDI
/// wrap) carry invisible U+2066/U+2069 marks around them, so assertions on
/// those use `find.textContaining` rather than an exact `find.text` match —
/// see `games_close_screen.dart`'s `_isolateNumeric`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_close_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _runId = 'run-1';

Future<void> _pump(
  WidgetTester tester, {
  required GameCloseResult result,
  List<GameCadenceInfo> cadences = const [GameCadenceInfo(cadence: 'week')],
}) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesCloseProvider(_runId).overrideWith((ref) async => result),
        gamesCadencesProvider.overrideWith((ref) async => cadences),
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
  // Settles the ceremony's bounded ≤600ms reveal so widget queries see the
  // final tree (it is one-time and non-repeating, so pumpAndSettle would
  // work too, but an explicit pump keeps the wait bounded and obvious).
  await tester.pump(const Duration(milliseconds: 700));
}

void main() {
  group('the three-beat ceremony budget', () {
    testWidgets(
      'renders exactly three beats; debrief-only content stays behind the '
      'debrief panel until it is opened',
      (tester) async {
        await _pump(
          tester,
          result: const GameCloseResult(
            runId: _runId,
            fieldId: 'f1',
            cadence: 'week',
            state: 'finished',
            scoringBasis: 'placement',
            entrantCount: 12,
            rank: 3,
            careerPointsDelta: 53,
            counterfactualFirstPicksPct: 2.1,
            counterfactualIndexPct: 0.6,
            alphaScored: 1.0,
            alphaDisplay: 1.3,
            wildnessIndex: 0.42,
            feesPaid: 12.5,
            tradeCount: 6,
          ),
        );

        expect(find.byKey(const Key('games_close_beat_result')),
            findsOneWidget);
        expect(find.byKey(const Key('games_close_beat_insight')),
            findsOneWidget);
        expect(find.byKey(const Key('games_close_beat_reentry')),
            findsOneWidget);

        // Debrief-only content is not on the main screen yet.
        expect(find.text('WILDNESS INDEX'), findsNothing);
        expect(find.text('SCORED · NET OF ENTRY FEE'), findsNothing);
        expect(find.text('VS COSTLESS INDEX'), findsNothing);

        await tester.tap(find.text('FULL DEBRIEF'));
        await tester.pumpAndSettle();

        expect(find.text('WILDNESS INDEX'), findsOneWidget);
        expect(find.text('SCORED · NET OF ENTRY FEE'), findsOneWidget);
        expect(find.text('VS COSTLESS INDEX'), findsOneWidget);
      },
    );
  });

  group('the free Close is complete', () {
    testWidgets('contains both counterfactual lines', (tester) async {
      await _pump(
        tester,
        result: const GameCloseResult(
          runId: _runId,
          fieldId: 'f1',
          cadence: 'week',
          state: 'finished',
          scoringBasis: 'placement',
          entrantCount: 12,
          rank: 3,
          careerPointsDelta: 53,
          counterfactualFirstPicksPct: 2.1,
          counterfactualIndexPct: 0.6,
        ),
      );

      // Both lines render on the Close itself (not gated behind the
      // debrief tap) — the free Close is complete.
      expect(
        find.textContaining("held your first picks untouched"),
        findsOneWidget,
      );
      expect(find.textContaining('+2.10%'), findsOneWidget);
      expect(find.textContaining("just held the S&P"), findsOneWidget);
      expect(find.textContaining('+0.60%'), findsOneWidget);
    });
  });

  group('alpha_scored vs alpha_display', () {
    testWidgets('both render, each straight from its own wire field',
        (tester) async {
      await _pump(
        tester,
        result: const GameCloseResult(
          runId: _runId,
          fieldId: 'f1',
          cadence: 'week',
          state: 'finished',
          scoringBasis: 'benchmark',
          entrantCount: 3,
          alphaScored: 1.10,
          alphaDisplay: 1.35,
        ),
      );

      await tester.tap(find.text('FULL DEBRIEF'));
      await tester.pumpAndSettle();

      expect(find.textContaining('+1.10%'), findsOneWidget);
      expect(find.textContaining('+1.35%'), findsOneWidget);
    });
  });

  group('a VOID run', () {
    testWidgets('states its reason instead of a score', (tester) async {
      await _pump(
        tester,
        result: const GameCloseResult(
          runId: _runId,
          fieldId: 'f1',
          cadence: 'week',
          state: 'void',
          voidReason: 'Mock-priced day — Aug 12',
        ),
      );

      expect(find.textContaining('Mock-priced day'), findsOneWidget);
      // No fabricated score: neither the finished- nor the forfeit-run
      // heading ever renders for a VOID run.
      expect(find.text('RUN CLOSED'), findsNothing);
      expect(find.text('CHAPTER CLOSED'), findsNothing);
      // The way back in still renders — VOID or not, beat 3 is unconditional.
      expect(find.byKey(const Key('games_close_beat_reentry')),
          findsOneWidget);
    });

    testWidgets('a still-paid stipend is labelled as a stipend, not a score',
        (tester) async {
      await _pump(
        tester,
        result: const GameCloseResult(
          runId: _runId,
          fieldId: 'f1',
          cadence: 'week',
          state: 'void',
          voidReason: 'Feed outage — Aug 12',
          stipendAwarded: true,
          careerPointsDelta: 5,
        ),
      );

      expect(find.textContaining('finish stipend'), findsOneWidget);
    });
  });

  group('the Wind-Up', () {
    testWidgets(
      'a forfeited run gets the dignified chapter-closed framing, never a '
      'fail screen, and still ends on the re-entry beat',
      (tester) async {
        await _pump(
          tester,
          result: const GameCloseResult(
            runId: _runId,
            fieldId: 'f1',
            cadence: 'week',
            state: 'forfeit',
            scoringBasis: 'placement',
            entrantCount: 12,
            rank: 9,
            careerPointsDelta: -6,
          ),
        );

        expect(find.text('CHAPTER CLOSED'), findsOneWidget);
        expect(find.text('RUN CLOSED'), findsNothing);
        expect(find.byKey(const Key('games_close_beat_reentry')),
            findsOneWidget);
        expect(find.text("THE NEXT ONE'S OPEN"), findsOneWidget);
      },
    );
  });
}
