/// CR109 — the field board, tested on the rules rather than the pixels.
///
/// Every assertion here corresponds to a decision the design wrote down
/// *because* the obvious implementation gets it wrong:
///
///   * §6.1 — rank on % return, never on money. A board that ranks AMI Cash
///     makes capital tier pay-to-win.
///   * §11.2 — a desk is visibly a desk on every surface that renders an
///     entrant, with its rule reachable. Saiful's own framing: an undisclosed
///     house account means the user "is copying what they thought is a
///     person", and a screenshot leaving the app carries no disclosure.
///   * The `?? 0` class, ninth instance and counting — an entrant with no
///     completed close must draw as a dash, not as 0.00%. Flat and unmeasured
///     are different facts, and this feature has now conflated them nine
///     separate times in nine different places.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_board_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

GameBoardRow _row({
  required String handle,
  int? rank,
  double? twrPct,
  bool isDesk = false,
  String? deskRule,
  bool isYou = false,
  int closesCounted = 1,
}) =>
    GameBoardRow(
      handle: handle,
      isDesk: isDesk,
      deskKey: isDesk ? 'momentum' : null,
      deskRule: deskRule,
      twrPct: twrPct,
      rank: rank,
      closesCounted: closesCounted,
      isYou: isYou,
    );

GameBoard _board({
  required List<GameBoardRow> rows,
  int? yourRank,
  double? yourTwrPct,
  bool standingsOpen = true,
  int? entrantCount,
  int deskCount = 0,
}) =>
    GameBoard(
      fieldId: 'f1',
      cadence: 'week',
      rows: rows,
      entrantCount: entrantCount ?? rows.length,
      deskCount: deskCount,
      standingsOpen: standingsOpen,
      yourRank: yourRank,
      yourTwrPct: yourTwrPct,
    );

Future<void> _pump(WidgetTester tester, GameBoard board) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient(board: board)),
        gamesBoardProvider(_runId).overrideWith((ref) async => board),
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

void main() {
  group('standings', () {
    testWidgets('ranks the field and marks the player', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
            _row(handle: 'Index Desk', rank: 3, twrPct: -0.2, isDesk: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 2,
        ),
      );

      expect(find.text("You're #2 of 3"), findsOneWidget);
      expect(find.text('Momentum Desk'), findsOneWidget);
      expect(find.text('+4.50%'), findsOneWidget);
      expect(find.text('+2.00%'), findsWidgets);
      expect(find.text('-0.20%'), findsOneWidget);
    });

    testWidgets('discloses how much of the field is house desks',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );
      expect(find.text('2 entrants'), findsOneWidget);
      expect(find.text('including 1 house desk'), findsOneWidget);
    });

    testWidgets('says out loud that it only moves once per close',
        (tester) async {
      await _pump(tester, _board(rows: [_row(handle: 'me', rank: 1, twrPct: 1)]));
      expect(
        find.text('Standings move once per US close — not tick by tick.'),
        findsOneWidget,
      );
    });
  });

  group('unmeasured is not zero — the ?? 0 class, ninth instance', () {
    testWidgets('an entrant with no close draws a dash, never 0.00%',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'measured', rank: 1, twrPct: 1.0),
            _row(handle: 'brand-new', closesCounted: 0),
          ],
          yourRank: 1,
          yourTwrPct: 1.0,
        ),
      );

      expect(find.text('0.00%'), findsNothing);
      expect(find.text('+0.00%'), findsNothing);
      expect(find.text('No close yet'), findsOneWidget);
      // Both the rank column and the return column render a dash.
      expect(find.text('—'), findsNWidgets(2));
    });

    testWidgets('the player with no close is told so, not shown a position',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [_row(handle: 'brand-new', isYou: true, closesCounted: 0)],
          standingsOpen: false,
        ),
      );

      expect(find.text('Not ranked yet'), findsOneWidget);
      expect(find.text('Standings open after the first US close.'),
          findsOneWidget);
      expect(find.textContaining("You're #"), findsNothing);
    });
  });

  group('disclosure — §11.2', () {
    testWidgets('every desk row carries the DESK chip', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'Index Desk', rank: 2, twrPct: 1.0, isDesk: true),
            _row(handle: 'careful-vector', rank: 3, twrPct: 0.5, isYou: true),
          ],
          yourRank: 3,
          yourTwrPct: 0.5,
          deskCount: 2,
        ),
      );
      expect(find.text('DESK'), findsNWidgets(2));
      expect(find.text('YOU'), findsOneWidget);
    });

    testWidgets("tapping a desk shows the rule the SERVER published",
        (tester) async {
      const rule = 'Equal-weights the 5 highest trailing 12-month returns.';
      await _pump(
        tester,
        _board(
          rows: [
            _row(
              handle: 'Momentum Desk',
              rank: 1,
              twrPct: 4.5,
              isDesk: true,
              deskRule: rule,
            ),
          ],
          yourRank: null,
        ),
      );

      await tester.tap(find.text('Momentum Desk'));
      await tester.pumpAndSettle();

      expect(find.text(rule), findsOneWidget);
      expect(find.text('How this desk trades'), findsOneWidget);
      // The disclosure line must never let a desk read as a person.
      expect(
        find.textContaining('Desks are AMI-run strategies, not people.'),
        findsOneWidget,
      );
    });

    testWidgets('a human row opens nothing — the board renders no one\'s book',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [_row(handle: 'other-player', rank: 1, twrPct: 3.0)],
        ),
      );

      await tester.tap(find.text('other-player'));
      await tester.pumpAndSettle();
      expect(find.text('How this desk trades'), findsNothing);
    });
  });

  group('§6.1 — the board ranks percentages, never money', () {
    testWidgets('renders no currency amount for anyone', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );

      // A currency glyph or a thousands-separated figure on this screen would
      // mean somebody's AMI Cash reached it.
      final texts = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data ?? '')
          .toList();
      for (final t in texts) {
        expect(t.contains(r'$'), isFalse, reason: 'money on the board: $t');
        expect(
          RegExp(r'\d{1,3},\d{3}').hasMatch(t),
          isFalse,
          reason: 'money-shaped figure on the board: $t',
        );
      }
    });
  });

  group('empty', () {
    testWidgets('an empty field says so', (tester) async {
      await _pump(tester, _board(rows: const [], standingsOpen: false));
      expect(find.text('No one has entered this field yet.'), findsOneWidget);
    });
  });
}
