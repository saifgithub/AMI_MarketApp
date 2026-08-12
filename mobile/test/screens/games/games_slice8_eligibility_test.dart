/// CR109 slice 8 — §8.5 on the board, §8.4's marker on the Close.
///
/// The property that matters most here is a rendering one, and it is the
/// design's own sentence: *"When an ineligible entrant places first, say so
/// plainly — 'Title: SLATE_07 (2nd overall)' — rather than silently
/// renumbering. A board that quietly promotes second place looks like a bug;
/// one that explains itself looks like a rule."*
///
/// So these tests assert what is SAID, not just what is computed: the leader
/// keeps rank 1, the row admits it cannot hold the title, and the title line
/// names both the holder and where they actually placed.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_board_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/widgets/games/games_marker_line.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _runId = 'run-1';

Future<void> _pumpBoard(WidgetTester tester, GameBoard board) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        gamesBoardProvider(_runId).overrideWith((ref) async => board),
        gamesDesksProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesBoardScreen(runId: _runId),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

GameBoard _closedBoard({GameChampion? champion}) => GameBoard(
      fieldId: 'f1',
      cadence: 'week',
      state: 'closed',
      entrantCount: 2,
      deskCount: 1,
      standingsOpen: true,
      champion: champion,
      rows: const [
        GameBoardRow(
          handle: 'SLATE_07',
          isDesk: true,
          rank: 1,
          twrPct: 4.2,
          titleIneligibleReason: 'house_desk',
        ),
        GameBoardRow(
          handle: 'you',
          isDesk: false,
          rank: 2,
          twrPct: 3.1,
          isYou: true,
        ),
      ],
    );

void main() {
  group('§8.5 — the board explains itself', () {
    testWidgets('the ineligible leader keeps rank 1 and says why',
        (tester) async {
      await _pumpBoard(
        tester,
        _closedBoard(
          champion: const GameChampion(
            handle: 'you', rank: 2, displaced: true,
          ),
        ),
      );

      final l = await AppLocalizations.delegate.load(const Locale('en'));
      expect(find.text('SLATE_07'), findsOneWidget,
          reason: 'ineligible does not mean invisible');
      expect(find.text(l.gamesBoardIneligibleNote), findsOneWidget);
    });

    testWidgets('a displaced title names the rank it actually placed at',
        (tester) async {
      await _pumpBoard(
        tester,
        _closedBoard(
          champion: const GameChampion(
            handle: 'you', rank: 2, displaced: true,
          ),
        ),
      );

      expect(find.textContaining('2nd overall'), findsOneWidget);
    });

    testWidgets('an undisplaced title states no rank at all', (tester) async {
      await _pumpBoard(
        tester,
        _closedBoard(
          champion: const GameChampion(handle: 'you', rank: 1),
        ),
      );

      expect(find.textContaining('overall'), findsNothing);
      expect(find.textContaining('Title: you'), findsOneWidget);
    });

    testWidgets('a closed all-desk field says nobody holds the title',
        (tester) async {
      await _pumpBoard(tester, _closedBoard());

      final l = await AppLocalizations.delegate.load(const Locale('en'));
      expect(find.text(l.gamesBoardNoChampion), findsOneWidget);
    });

    testWidgets('a LIVE field claims no champion yet', (tester) async {
      await _pumpBoard(
        tester,
        GameBoard(
          fieldId: 'f1',
          cadence: 'week',
          state: 'live',
          entrantCount: 2,
          standingsOpen: true,
          rows: _closedBoard().rows,
        ),
      );

      final l = await AppLocalizations.delegate.load(const Locale('en'));
      expect(find.textContaining('Title:'), findsNothing);
      expect(find.text(l.gamesBoardNoChampion), findsNothing);
    });
  });

  group('§8.4 — the marker line', () {
    late AppLocalizations l;

    setUp(() async {
      l = await AppLocalizations.delegate.load(const Locale('en'));
    });

    test('every shipped kind has a sentence', () {
      for (final kind in const [
        'first_finish',
        'first_positive',
        'first_podium',
        'personal_best_twr',
        'clean_streak',
      ]) {
        expect(
          markerLine(l, GameMarker(kind: kind, value: 3)),
          isNotEmpty,
          reason: '$kind renders nothing',
        );
      }
    });

    test('an unknown kind renders nothing rather than a raw enum', () {
      expect(markerLine(l, const GameMarker(kind: 'time_traveller')), isEmpty);
    });

    test('a rank marker reads as an ordinal, not as a bare integer', () {
      expect(
        markerLine(l, const GameMarker(kind: 'first_podium', value: 2)),
        contains('2nd'),
      );
    });

    test('a return marker carries its sign', () {
      expect(
        markerLine(l, const GameMarker(kind: 'personal_best_twr', value: 6.8)),
        contains('+6.80%'),
      );
    });

    test('a Close with no marker parses to null, never to an empty marker',
        () {
      final close = GameCloseResult.fromJson(const {
        'run_id': _runId,
        'field_id': 'f1',
        'cadence': 'week',
        'marker': null,
      });

      expect(close.marker, isNull);
    });
  });
}
