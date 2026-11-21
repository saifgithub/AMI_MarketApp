/// CR267 WP-25 — the flip explainer on the wire: the verdict object, the SSE
/// `verdict` event (same parser) and Journal ROOM_RUN payloads.
///
/// Pinned: a full block parses, a minimal one parses with the backend's
/// defaults, an unknown input `kind` is `other` (never a throw), absence is
/// `null` (never an empty explainer), and the Journal helper reads only a
/// ROOM_RUN entry's `payload.verdict.flip_explainer`.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _full() => {
      'previous_run_id': 'run-1',
      'previous_action': 'PASS',
      'new_action': 'APPROVE',
      'changed_inputs': [
        {'kind': 'price', 'summary': 'Price moved +4.2% since 12 Nov.'},
        {'kind': 'news', 'summary': '3 new headlines.'},
        {'kind': 'filings', 'summary': 'A new 10-Q was filed.'},
        {'kind': 'mandate', 'summary': 'Max drawdown 20% to 25%.'},
        {'kind': 'portfolio', 'summary': 'Holdings changed.'},
        {'kind': 'brief', 'summary': 'Brief edited.'},
        {'kind': 'policy', 'summary': 'Room policy updated.'},
        {'kind': 'model', 'summary': 'Model changed.'},
        {'kind': 'other', 'summary': 'Something else.'},
      ],
      'inputs_compared': true,
      'same_inputs_flip': false,
      'changed_answers': [
        {
          'question': 'catalyst_in_horizon',
          'before': 'no',
          'after': 'yes',
        },
      ],
      'answers_available': true,
      'answers_unavailable_reason': null,
      'cards_changes': [
        {'desk': 'bull', 'item': 'revenue', 'before': 'up', 'after': 'flat'},
      ],
    };

JournalEntry _entry(JournalEntryType type, Map<String, dynamic> payload) =>
    JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: type,
      title: 'Room on NVDA',
      createdAt: DateTime.utc(2026, 11, 20),
      agentsInvolved: const [],
      tags: const [],
      payload: payload,
    );

void main() {
  group('FlipExplainer.tryParse', () {
    test('a full block parses every field', () {
      final e = FlipExplainer.tryParse(_full())!;
      expect(e.previousRunId, 'run-1');
      expect(e.previousAction, 'PASS');
      expect(e.newAction, 'APPROVE');
      expect(e.changedInputs.map((c) => c.kind), [
        FlipInputKind.price,
        FlipInputKind.news,
        FlipInputKind.filings,
        FlipInputKind.mandate,
        FlipInputKind.portfolio,
        FlipInputKind.brief,
        FlipInputKind.policy,
        FlipInputKind.model,
        FlipInputKind.other,
      ]);
      expect(e.changedInputs.first.summary, 'Price moved +4.2% since 12 Nov.');
      expect(e.inputsCompared, isTrue);
      expect(e.sameInputsFlip, isFalse);
      expect(e.answersAvailable, isTrue);
      expect(e.answersUnavailableReason, isNull);
      expect(e.changedAnswers.single.question, 'catalyst_in_horizon');
      expect(e.changedAnswers.single.before, 'no');
      expect(e.changedAnswers.single.after, 'yes');
      expect(e.cardsChanges!.single.desk, 'bull');
    });

    test('a minimal block parses with the backend defaults', () {
      final e = FlipExplainer.tryParse({
        'previous_run_id': 'r0',
        'previous_action': 'REJECT',
        'new_action': 'PASS',
      })!;
      expect(e.changedInputs, isEmpty);
      expect(e.inputsCompared, isTrue);
      expect(e.sameInputsFlip, isFalse);
      expect(e.changedAnswers, isEmpty);
      expect(e.answersAvailable, isFalse);
      expect(e.answersUnavailableReason, isNull);
      expect(e.cardsChanges, isNull);
    });

    test('an unknown input kind is `other`, and one bad row does not throw', () {
      final e = FlipExplainer.tryParse({
        'previous_run_id': 'r0',
        'previous_action': 'PASS',
        'new_action': 'APPROVE',
        'changed_inputs': [
          {'kind': 'weather', 'summary': 'Cloudy.'},
          'not a map',
          {'summary': 'No kind at all.'},
        ],
      })!;
      expect(e.changedInputs.length, 2);
      expect(e.changedInputs.every((c) => c.kind == FlipInputKind.other), isTrue);
    });

    test('not a map is null', () {
      expect(FlipExplainer.tryParse(null), isNull);
      expect(FlipExplainer.tryParse('x'), isNull);
      expect(FlipExplainer.tryParse([1]), isNull);
    });
  });

  group('RoomVerdict.fromJson', () {
    test('carries previous_action and the explainer', () {
      final v = RoomVerdict.fromJson({
        'action': 'APPROVE',
        'reason': 'r',
        'previous_action': 'PASS',
        'flip_explainer': _full(),
      });
      expect(v.previousAction, 'PASS');
      expect(v.flipExplainer!.newAction, 'APPROVE');
    });

    test('a verdict that predates the fields has neither', () {
      final v = RoomVerdict.fromJson({'action': 'PASS', 'reason': 'r'});
      expect(v.previousAction, isNull);
      expect(v.flipExplainer, isNull);
    });

    test('a non-flip with a previous action has no explainer', () {
      final v = RoomVerdict.fromJson({
        'action': 'PASS',
        'reason': 'r',
        'previous_action': 'PASS',
        'flip_explainer': null,
      });
      expect(v.previousAction, 'PASS');
      expect(v.flipExplainer, isNull);
    });
  });

  group('Journal payload', () {
    test('a ROOM_RUN entry with the block yields the explainer', () {
      final e = flipExplainerFromJournalEntry(_entry(
        JournalEntryType.roomRun,
        {
          'verdict': {'action': 'APPROVE', 'flip_explainer': _full()},
        },
      ));
      expect(e!.previousAction, 'PASS');
    });

    test('no block, no verdict, or another entry type yields null', () {
      expect(
          flipExplainerFromJournalEntry(_entry(JournalEntryType.roomRun, {
            'verdict': {'action': 'PASS'},
          })),
          isNull);
      expect(
          flipExplainerFromJournalEntry(
              _entry(JournalEntryType.roomRun, const {})),
          isNull);
      expect(
          flipExplainerFromJournalEntry(_entry(JournalEntryType.simTrade, {
            'verdict': {'flip_explainer': _full()},
          })),
          isNull);
    });
  });
}
