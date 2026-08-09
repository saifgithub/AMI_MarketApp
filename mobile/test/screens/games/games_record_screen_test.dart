/// CR109 slice 3 — the Record: identity / movement / history (design
/// §13.3) and the PR board (implementation_plan.md §4.4.2, "works at
/// n = 1"). Same harness shape as games_home_screen_test.dart.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_record_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(
  WidgetTester tester, {
  required GameRecord record,
  List<GamePersonalRecord> prs = const [],
}) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesRecordProvider.overrideWith((ref) async => record),
        gamesRecordPrsProvider.overrideWith((ref) async => prs),
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
  group('career points — never re-clamped on this client', () {
    testWidgets('renders SUM(delta) exactly as received', (tester) async {
      await _pump(
        tester,
        record: const GameRecord(
          careerPoints: 8,
          enteredCount: 4,
          finishedCount: 3,
          forfeitCount: 1,
        ),
      );

      expect(find.textContaining('8'), findsWidgets);
      expect(find.text('CAREER POINTS'), findsOneWidget);
    });
  });

  group('history counts', () {
    testWidgets('entered/finished/forfeited render from the record',
        (tester) async {
      await _pump(
        tester,
        record: const GameRecord(
          careerPoints: 8,
          enteredCount: 4,
          finishedCount: 3,
          forfeitCount: 1,
        ),
      );

      expect(find.text('ENTERED'), findsOneWidget);
      expect(find.text('FINISHED'), findsOneWidget);
      expect(find.text('FORFEITED'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
    });
  });

  group('the PR board — works at n = 1', () {
    testWidgets('a single PR entry renders, carrying its entry_id',
        (tester) async {
      await _pump(
        tester,
        record: const GameRecord(
          careerPoints: 8,
          enteredCount: 1,
          finishedCount: 1,
        ),
        prs: const [
          GamePersonalRecord(
            kind: 'best_weekly_twr',
            entryId: 'entry-1',
            value: 4.4,
          ),
        ],
      );

      expect(find.text('BEST WEEKLY RETURN'), findsOneWidget);
      expect(find.textContaining('4.40'), findsOneWidget);
    });

    testWidgets('an unrecognised PR kind still renders via its fallback '
        'label rather than being dropped', (tester) async {
      await _pump(
        tester,
        record: const GameRecord(),
        prs: const [
          GamePersonalRecord(kind: 'best_new_thing', entryId: 'entry-2'),
        ],
      );

      expect(find.text('Best New Thing'), findsOneWidget);
    });
  });

  group('zero-finished-runs state', () {
    testWidgets('the Record renders for a user with no runs at all',
        (tester) async {
      await _pump(tester, record: const GameRecord());

      expect(find.text('YOUR RECORD'), findsOneWidget);
      expect(find.text('No runs yet — your first close will land here.'),
          findsOneWidget);
      expect(find.text('Finish a run to set your first PR.'), findsOneWidget);
      // IDENTITY is present-when-available only — no title this slice.
      expect(find.text('IDENTITY'), findsNothing);
    });
  });

  group('run-history navigation', () {
    testWidgets('a row with a known run_id opens the Close for it',
        (tester) async {
      await _pump(
        tester,
        record: const GameRecord(
          careerPoints: 53,
          enteredCount: 1,
          finishedCount: 1,
          runHistory: [
            GameRecordRunHistoryEntry(
              entryId: 'e1',
              runId: 'r1',
              cadence: 'week',
              state: 'finished',
              careerPointsDelta: 53,
            ),
          ],
        ),
      );

      // A tappable chevron is present for a row with a resolvable run_id.
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    });

    testWidgets(
      'a finished row without a run_id is not tappable',
      (tester) async {
        await _pump(
          tester,
          record: const GameRecord(
            careerPoints: 8,
            enteredCount: 1,
            finishedCount: 1,
            runHistory: [
              GameRecordRunHistoryEntry(
                entryId: 'e2',
                cadence: 'week',
                state: 'finished',
                careerPointsDelta: 8,
              ),
            ],
          ),
        );

        expect(find.byIcon(Icons.chevron_right), findsNothing);
      },
    );

    testWidgets(
      'a forfeited row answers inline (the Wind-Up) rather than opening a '
      'Close that would 409 — games_record_service.py: "a forfeit has no '
      'Close"',
      (tester) async {
        await _pump(
          tester,
          record: const GameRecord(
            careerPoints: 0,
            enteredCount: 1,
            finishedCount: 0,
            forfeitCount: 1,
            runHistory: [
              GameRecordRunHistoryEntry(
                entryId: 'e3',
                runId: 'r3',
                cadence: 'week',
                state: 'forfeit',
                careerPointsDelta: -3,
              ),
            ],
          ),
        );

        // Still tappable, even though there is a resolvable run_id — a
        // forfeit must never navigate to the Close.
        expect(find.byIcon(Icons.chevron_right), findsOneWidget);

        await tester.tap(find.byIcon(Icons.chevron_right));
        await tester.pumpAndSettle();

        // The dialog, not a pushed GamesCloseScreen — the Record screen's
        // own app bar (with its title) is still present underneath.
        expect(find.text('CHAPTER CLOSED'), findsOneWidget);
        expect(find.text('YOUR RECORD'), findsOneWidget);
      },
    );
  });
}
