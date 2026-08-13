/// CR173 — the consensus strip's honesty rules.
///
/// The strip makes a claim in one line about what eleven analysts thought and
/// who objected. Every way it could be confidently wrong is a test here, and
/// the two that matter most are the ones where the right answer is **to say
/// nothing**: an unrecorded run, and a verdict that is not a position.
library;

import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/models/room_consensus.dart';
import 'package:flutter_test/flutter_test.dart';

RoomVoice _v(String id, String? stance,
        {String? conviction, String? headline}) =>
    RoomVoice(
      agentId: id,
      content: '',
      stance: stance,
      conviction: conviction,
      headline: headline,
      stanceRecorded: true,
    );

RoomBoardData _board({
  required VerdictOutcome outcome,
  required List<RoomVoice> voices,
  String action = 'APPROVE',
}) =>
    RoomBoardData(
      ticker: 'NVDA',
      outcome: outcome,
      actionToken: action,
      reason: 'because',
      voices: voices,
    );

void main() {
  test('an APPROVE splits for-against, with `for` on the call\'s side', () {
    final c = consensusFor(_board(
      outcome: VerdictOutcome.approve,
      voices: [
        _v('bull_researcher', 'for'),
        _v('market_analyst', 'for'),
        _v('bear_researcher', 'against', headline: 'multiple is stretched'),
        _v('news_analyst', 'neutral'),
      ],
    ))!;
    expect(c.withCall, 2);
    expect(c.againstCall, 1);
    expect(c.neutral, 1);
    expect(c.dissenter?.agentId, 'bear_researcher');
  });

  test('a REJECT flips which side is dissenting', () {
    // The PM declined the idea. The analyst still arguing FOR it is the one
    // who disagreed with the call — naming the `against` voices here would
    // name the people who AGREED.
    final c = consensusFor(_board(
      outcome: VerdictOutcome.reject,
      action: 'REJECT',
      voices: [
        _v('bear_researcher', 'against'),
        _v('bull_researcher', 'for', headline: 'the setup is intact'),
      ],
    ))!;
    expect(c.withCall, 1);
    expect(c.againstCall, 1);
    expect(c.dissenter?.agentId, 'bull_researcher');
  });

  test('a PASS is a decision not to act, so `for` dissents from it', () {
    final c = consensusFor(_board(
      outcome: VerdictOutcome.pass,
      action: 'PASS',
      voices: [
        _v('bull_researcher', 'for', headline: 'worth a starter position'),
        _v('conservative_debator', 'against'),
      ],
    ))!;
    expect(c.dissenter?.agentId, 'bull_researcher');
  });

  test('the loudest objection is the one named', () {
    final c = consensusFor(_board(
      outcome: VerdictOutcome.approve,
      voices: [
        _v('bull_researcher', 'for'),
        _v('news_analyst', 'against', conviction: 'low'),
        _v('bear_researcher', 'against', conviction: 'high'),
      ],
    ))!;
    expect(c.dissenter?.agentId, 'bear_researcher',
        reason: 'one line names one analyst, so it should be the one who '
            'argued hardest, not whoever spoke first');
  });

  test('unanimous is a finding, not an empty line', () {
    final c = consensusFor(_board(
      outcome: VerdictOutcome.approve,
      voices: [_v('bull_researcher', 'for'), _v('market_analyst', 'for')],
    ))!;
    expect(c.unanimous, isTrue);
    expect(c.dissenter, isNull);
  });

  group('when the honest answer is to say nothing', () {
    test('a run that recorded no stances gets no strip', () {
      // Pre-CR106-B2 entries have eleven null stances. `0–0` would read as
      // "nobody had a view" rather than "we did not write this down".
      final data = _board(
        outcome: VerdictOutcome.approve,
        voices: const [
          RoomVoice(agentId: 'bull_researcher', content: 'x'),
          RoomVoice(agentId: 'bear_researcher', content: 'y'),
        ],
      );
      expect(consensusFor(data), isNull);
    });

    test('stances recorded but all "no view" gets no strip', () {
      final data = _board(
        outcome: VerdictOutcome.approve,
        voices: [_v('bull_researcher', null), _v('bear_researcher', null)],
      );
      expect(consensusFor(data), isNull);
    });

    test('NO_VERDICT reports the split and names nobody', () {
      // The PM refused to price a trade without a market read. A professional
      // refusal is not a position, so nothing can dissent from it — and naming
      // an analyst as a dissenter here would invent a disagreement.
      final c = consensusFor(_board(
        outcome: VerdictOutcome.noVerdict,
        action: 'NO_VERDICT',
        voices: [
          _v('bull_researcher', 'for'),
          _v('bear_researcher', 'against', headline: 'wait for the print'),
        ],
      ))!;
      expect(c.dissentApplies, isFalse);
      expect(c.dissenter, isNull);
      expect(c.stated, 2, reason: 'the split is still real and still shown');
    });

    test('an action this build does not know names nobody either', () {
      // DEF210 — a wrong-but-known reading is indistinguishable from a right
      // one. We cannot say which side of DEFER a voice is on, so we do not.
      final c = consensusFor(_board(
        outcome: VerdictOutcome.unknown,
        action: 'DEFER',
        voices: [_v('bull_researcher', 'for'), _v('bear_researcher', 'against')],
      ))!;
      expect(c.dissentApplies, isFalse);
      expect(c.dissenter, isNull);
    });
  });
}
