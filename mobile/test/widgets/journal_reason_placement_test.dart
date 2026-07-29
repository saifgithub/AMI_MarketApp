/// DEF150 (client half) — the Journal opened with an argument for a conclusion
/// the reader had not been given yet, and that copy was cut mid-word.
///
/// The report asked for the reason to be moved below `NO POSITION`. Measuring
/// first showed it already is: `RoomBoard` renders `_ReasonBlock` after
/// `_HeroTile`, on both surfaces, from the untruncated `verdict.reason` in the
/// payload. What sat *above* the board was `entry.summary` — the same sentence
/// with the action prefixed, stored clipped to 240 chars by the backend. So
/// the fix is a deletion, not a move, and these tests pin the three properties
/// that make the deletion safe:
///
/// 1. the duplicate is gone when the board carries the reason;
/// 2. it is **kept** when the board does not, because then it is the only
///    account of what happened (T-BACKFILL — degrade per entry);
/// 3. the board's copy is the full one, which is the reason deleting the
///    other is a fix rather than a loss of information.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:flutter_test/flutter_test.dart';

const _fullReason =
    'The Research Manager and Trader correctly identify a binary risk event '
    'inside the horizon, and the mandate\'s drawdown cap leaves no room to sit '
    'through it. The bull case rests on a re-rating that the multiple does not '
    'yet support given the 3.05 PEG and the potential for a guide-down at the '
    'next print.';

/// What the backend stored: the same sentence, prefixed, cut at 240.
final _storedSummary = 'PASS — $_fullReason'.substring(0, 240);

JournalEntry _entry({
  JournalEntryType type = JournalEntryType.roomRun,
  Map<String, dynamic>? payload,
  String? summary,
}) =>
    JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: type,
      title: 'Room on NVDA — PASS',
      summary: summary,
      createdAt: DateTime.utc(2026, 7, 29),
      agentsInvolved: const [],
      tags: const ['room'],
      ticker: 'NVDA',
      payload: payload ?? const {},
    );

Map<String, dynamic> _roomPayload(String reason) => {
      'verdict': {'action': 'PASS', 'reason': reason},
      'model_tier': 'mid',
      'transcript': const [
        {'agent_id': 'bull_researcher', 'content': 'x', 'stance': 'FOR'},
      ],
    };

void main() {
  group('DEF150 — the duplicated reasoning above the board', () {
    test('the fixture really is the reported failure', () {
      // Vacuity guard: if the stored summary were not clipped mid-word, this
      // file would pass while testing a bug that is not the one reported.
      // The reported instance ended "…the 3.05 PEG and the potential fo"; what
      // matters is the shape, so assert the shape — the 240th character lands
      // inside a word, with no marker of any kind.
      expect(_storedSummary.length, 240);
      final full = 'PASS — $_fullReason';
      expect(_storedSummary.endsWith(' '), isFalse);
      expect(full[240], isNot(' '),
          reason: 'the cut must land inside a word for this to be DEF150');
      expect(_storedSummary.endsWith('…'), isFalse,
          reason: 'and unmarked — the copy asserts it is the whole thought');
    });

    test('a room run with a verdict suppresses the summary above the board',
        () {
      final entry =
          _entry(payload: _roomPayload(_fullReason), summary: _storedSummary);
      expect(boardCarriesTheReason(entry), isTrue);
    });

    test('the board copy is the full one — that is why deleting is safe', () {
      final entry =
          _entry(payload: _roomPayload(_fullReason), summary: _storedSummary);
      final board = boardFromJournalEntry(entry)!;
      expect(board.reason, _fullReason);
      expect(board.reason.length, greaterThan(entry.summary!.length));
      expect(board.reason, isNot(endsWith('fo')));
    });

    test('a room run with NO board keeps its summary', () {
      // Neither verdict nor transcript → `boardFromJournalEntry` returns null
      // and nothing else on the screen describes the run. Suppressing here
      // would leave the entry blank, which is a worse defect than the one
      // being fixed.
      final entry = _entry(payload: const {}, summary: 'Run stopped after 4 of 12 agents');
      expect(boardFromJournalEntry(entry), isNull);
      expect(boardCarriesTheReason(entry), isFalse);
    });

    test('a room run whose verdict carries an empty reason keeps its summary',
        () {
      final entry = _entry(payload: _roomPayload('   '), summary: 'something');
      expect(boardCarriesTheReason(entry), isFalse,
          reason: 'a board with a blank reason block hides nothing, so the '
              'summary is still the only prose');
    });

    test('non-room entries are untouched', () {
      for (final type in JournalEntryType.values
          .where((t) => t != JournalEntryType.roomRun)) {
        expect(boardCarriesTheReason(_entry(type: type, summary: 'note')),
            isFalse,
            reason: '$type draws no board; its summary is its content');
      }
    });
  });
}
