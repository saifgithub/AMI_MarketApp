// DEF343 — a shared rank must read as shared, and the YOU row must not sit
// last among equals.
//
// The field screenshot (0.1.0+94, iOS): two entrants tied at +0.05%, both
// carrying rank 3 of 4 by competition ranking. The hero said "You're #3 of 4";
// the listing put the YOU row *below* its tied peer with no tie marker, so the
// player read it as "the listing shows I am no 4". The maths was right and the
// presentation contradicted it.
//
// Both halves are pure list functions on purpose — the bug is entirely about
// which row is where and what the rank cell says, and neither needs a pump.

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_board_screen.dart';
import 'package:flutter_test/flutter_test.dart';

GameBoardRow _row({required int? rank, bool isYou = false, String handle = 'x'}) =>
    GameBoardRow(
      handle: handle,
      rank: rank,
      twrPct: 0.05,
      isYou: isYou,
      isDesk: false,
    );

void main() {
  group('DEF343 — tie detection', () {
    test('a rank held by two entrants is tied', () {
      final rows = [_row(rank: 1), _row(rank: 3), _row(rank: 3, isYou: true)];
      expect(isTiedRank(rows, 3), isTrue);
    });

    test('a rank held by one entrant is not tied', () {
      final rows = [_row(rank: 1), _row(rank: 3), _row(rank: 3, isYou: true)];
      expect(isTiedRank(rows, 1), isFalse);
    });

    test('an unmeasured rank is never tied — absence is not a shared value', () {
      final rows = [_row(rank: null), _row(rank: null)];
      expect(isTiedRank(rows, null), isFalse);
    });
  });

  group('DEF343 — the YOU row leads its tie group', () {
    test('YOU moves to the front of its own tie group and nothing else moves', () {
      final rows = [
        _row(rank: 1, handle: 'a'),
        _row(rank: 2, handle: 'b'),
        _row(rank: 3, handle: 'peer'),
        _row(rank: 3, handle: 'me', isYou: true),
      ];
      final out = orderedRows(rows);
      expect(out.map((r) => r.handle), ['a', 'b', 'me', 'peer']);
    });

    test('a three-way tie still puts YOU first', () {
      final rows = [
        _row(rank: 2, handle: 'p1'),
        _row(rank: 2, handle: 'p2'),
        _row(rank: 2, handle: 'me', isYou: true),
      ];
      expect(orderedRows(rows).first.handle, 'me');
    });

    test('an untied YOU row does not move', () {
      final rows = [
        _row(rank: 1, handle: 'a'),
        _row(rank: 2, handle: 'me', isYou: true),
        _row(rank: 3, handle: 'c'),
      ];
      expect(orderedRows(rows).map((r) => r.handle), ['a', 'me', 'c']);
    });

    test('two unranked rows are not a tie group, so YOU does not jump one', () {
      // The mutation this is aimed at: dropping the `rank == null` guard from
      // orderedRows. With rows [ranked, unranked-peer, unranked-YOU] the group
      // walk compares null == null, decides the two unmeasured rows share a
      // rank, and promotes YOU above a peer it is not tied with. Absence of a
      // measurement is not a shared value — the same rule isTiedRank already
      // holds to. A fixture whose only unranked row IS the YOU row cannot see
      // this: there is no null neighbour to compare against.
      final rows = [
        _row(rank: 1, handle: 'a'),
        _row(rank: null, handle: 'peer'),
        _row(rank: null, handle: 'me', isYou: true),
      ];
      expect(orderedRows(rows).map((r) => r.handle), ['a', 'peer', 'me']);
    });

    test('a board with no YOU row is returned untouched', () {
      final rows = [_row(rank: 1, handle: 'a'), _row(rank: 1, handle: 'b')];
      expect(orderedRows(rows).map((r) => r.handle), ['a', 'b']);
    });
  });

  group('CR207 — one producer for the placement rule', _cr207Tests);
}

// ── CR207 — the Close reads the server's resolved placement ────────────────
//
// Criterion 6: the placement rule gets exactly ONE producer. Before this the
// client re-derived `rankedFieldSize` from `scored_entrant_count` /
// `entrant_count` with its own never-zero rule, while `games_placement.py`
// resolved the same thing server-side for the settlement push. Two live
// derivations of one rule disagree the first time either moves.

GameCloseResult _close(Map<String, dynamic> extra) => GameCloseResult.fromJson({
      'run_id': 'r',
      'field_id': 'f',
      'cadence': 'week',
      'state': 'finished',
      'scoring_basis': 'placement',
      'entrant_count': 9,
      'scored_entrant_count': 7,
      'rank': 3,
      'career_points_delta': 0,
      'trade_count': 0,
      ...extra,
    });

void _cr207Tests() {
  test('the server-resolved field size wins over the local derivation', () {
    final r = _close({
      'placement': {'field_size': 4, 'tie_count': 1, 'asserts_position': true},
    });
    expect(r.rankedFieldSize, 4);
  });

  test('a payload with no placement block still renders, from the old rule', () {
    // Not a fallback for convenience — a payload predating the block must not
    // render "of 0" or throw. The scored count still beats the raw entrant
    // count here, for the reason it always did: entries that voided were
    // never comparable.
    expect(_close({}).rankedFieldSize, 7);
  });

  test('a shared rank is carried from the server, not counted by the client', () {
    // The client is only ever sent its OWN entry, so it cannot count a tie.
    final r = _close({
      'placement': {'field_size': 4, 'tie_count': 2, 'asserts_position': true},
    });
    expect(r.isTiedFinish, isTrue);
    expect(_close({}).isTiedFinish, isFalse);
  });

  test('a non-asserting placement is carried through as such', () {
    final r = _close({
      'state': 'void',
      'placement': {
        'field_size': 4,
        'tie_count': 0,
        'asserts_position': false,
      },
    });
    expect(r.placementAssertsPosition, isFalse);
  });
}
