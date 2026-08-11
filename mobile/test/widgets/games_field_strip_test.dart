/// CR109 — the field strip. Saiful: *"In the standing page, it is so very
/// boring."*
///
/// A painter is mostly untestable by pixel, so these pin the DECISIONS
/// instead — the ones where being wrong would state something false about
/// the field rather than merely look bad:
///
///   * an unmeasured entrant is not placed on the axis at all;
///   * a one-entrant "race" draws nothing, rather than a mark implying a
///     spread that does not exist;
///   * a dead-flat field does not divide by zero;
///   * no currency ever reaches this widget (§6.1).
library;

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/widgets/games/games_field_strip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

GameBoardRow _row({
  required String handle,
  double? twr,
  int? rank,
  bool isDesk = false,
  bool isYou = false,
}) =>
    GameBoardRow(
      handle: handle,
      twrPct: twr,
      rank: rank,
      isDesk: isDesk,
      isYou: isYou,
    );

Future<void> _pump(WidgetTester tester, List<GameBoardRow> rows) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SizedBox(width: 360, child: GamesFieldStrip(rows: rows)),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  group('what it refuses to draw', () {
    testWidgets('a single measured entrant is not a race', (tester) async {
      // One mark on an axis implies a spread. The ordered list below the
      // strip says "you are 1st of 1" far more honestly.
      await _pump(tester, [
        _row(handle: 'YOU', twr: 1.2, rank: 1, isYou: true),
        _row(handle: 'NOBODY', twr: null),
      ]);
      expect(find.byKey(const Key('games_field_strip')), findsNothing);
    });

    testWidgets('an empty field draws nothing', (tester) async {
      await _pump(tester, const []);
      expect(find.byKey(const Key('games_field_strip')), findsNothing);
    });

    testWidgets('two measured entrants IS a race', (tester) async {
      // The mutation guard for the two above: a strip that never drew would
      // pass both of them.
      await _pump(tester, [
        _row(handle: 'YOU', twr: 1.2, rank: 1, isYou: true),
        _row(handle: 'VECTOR_11', twr: 0.4, rank: 2),
      ]);
      expect(find.byKey(const Key('games_field_strip')), findsOneWidget);
    });
  });

  group('unmeasured is not a position', () {
    testWidgets('an unmeasured entrant does not make a one-mark field a race',
        (tester) async {
      // If an unmeasured row were being placed at zero, this would render —
      // and would show a player sitting on the axis at a position nobody
      // measured. That is the `?? 0` class this feature keeps producing.
      await _pump(tester, [
        _row(handle: 'YOU', twr: 2.0, rank: 1, isYou: true),
        _row(handle: 'NOT_CLOSED_YET', twr: null),
        _row(handle: 'ALSO_NOT', twr: null),
      ]);
      expect(find.byKey(const Key('games_field_strip')), findsNothing);
    });

    testWidgets('unmeasured entrants alongside measured ones still draw',
        (tester) async {
      await _pump(tester, [
        _row(handle: 'YOU', twr: 2.0, rank: 1, isYou: true),
        _row(handle: 'RIVAL', twr: -1.0, rank: 2),
        _row(handle: 'NOT_CLOSED_YET', twr: null),
      ]);
      expect(find.byKey(const Key('games_field_strip')), findsOneWidget);
    });
  });

  group('degenerate ranges do not throw', () {
    testWidgets('a dead-flat field paints without dividing by zero',
        (tester) async {
      await _pump(tester, [
        _row(handle: 'YOU', twr: 1.0, rank: 1, isYou: true),
        _row(handle: 'A', twr: 1.0, rank: 1),
        _row(handle: 'B', twr: 1.0, rank: 1),
      ]);
      await tester.pump();
      expect(tester.takeException(), isNull);
    });

    testWidgets('an all-negative field paints, and needs no zero line',
        (tester) async {
      await _pump(tester, [
        _row(handle: 'YOU', twr: -0.5, rank: 1, isYou: true),
        _row(handle: 'A', twr: -3.2, rank: 2),
      ]);
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('games_field_strip')), findsOneWidget);
    });

    testWidgets('a field straddling zero paints', (tester) async {
      await _pump(tester, [
        _row(handle: 'YOU', twr: 2.4, rank: 1, isYou: true),
        _row(handle: 'A', twr: -1.8, rank: 2),
      ]);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a large field paints', (tester) async {
      await _pump(tester, [
        for (var i = 0; i < 24; i++)
          _row(handle: 'P$i', twr: i * 0.37 - 4, rank: i + 1, isYou: i == 7),
      ]);
      expect(tester.takeException(), isNull);
    });
  });

  group('§6.1 — no currency reaches this widget', () {
    test('GameBoardRow carries no money field at all', () {
      // Asserted on the MODEL rather than on the paint: the invariant is
      // that there is nothing here to render even by accident, which is a
      // stronger guarantee than "we chose not to draw it".
      final row = _row(handle: 'YOU', twr: 1.0, rank: 1, isYou: true);
      final fields = row.toString().toLowerCase();
      for (final banned in ['cash', 'nav', 'stake', 'value', 'capital']) {
        expect(fields.contains(banned), isFalse,
            reason: '$banned is reachable from a board row');
      }
    });
  });
}
