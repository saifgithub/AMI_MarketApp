/// CR178 — the INSIGHTS aggregation.
///
/// These are the acceptance criteria, not coverage. Every one of them is a way
/// this screen could render a confident number that is not true:
///
///   * `NO_VERDICT` folded into REJECT tells the user their idea was turned
///     down when it was never judged (CR098);
///   * a null `payload.verdict` counted as PASS invents a ruling out of a
///     crashed run;
///   * the Day Trader preset rendered as seven loosenings describes a spree
///     that never happened;
///   * a `1/1` bar reading 100% is not a weak signal, it is no signal wearing
///     a strong one;
///   * a limit read as `0` because it was unset is the `?? 0` family — an
///     unmeasured value and a real zero becoming the same fact;
///   * and an unlabelled aggregate past 100 entries describes the most recent
///     100 while presenting itself as all-time.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:flutter_test/flutter_test.dart';

var _seq = 0;

JournalEntry _entry({
  required JournalEntryType type,
  List<String> tags = const [],
  List<String> agents = const [],
  Map<String, dynamic> payload = const {},
}) {
  _seq++;
  return JournalEntry(
    id: 'e$_seq',
    userId: 'u1',
    entryType: type,
    title: 't$_seq',
    // Newest-first is what the endpoint returns; the fixture builders below
    // hand lists to `buildInsights` in the order they are written, so a test
    // that cares about order says so.
    createdAt: DateTime(2026, 1, 1).add(Duration(minutes: _seq)),
    agentsInvolved: agents,
    tags: tags,
    payload: payload,
  );
}

JournalEntry _closed(String ending) => _entry(
      type: JournalEntryType.simTrade,
      tags: ['sim_trade', 'closed', ending],
    );

JournalEntry _room(String? action) => _entry(
      type: JournalEntryType.roomRun,
      tags: ['room'],
      payload: {'verdict': action == null ? null : {'action': action}},
    );

JournalEntry _challenge(String type, bool correct) => _entry(
      type: JournalEntryType.dailyChallenge,
      payload: {'type': type, 'correct': correct, 'difficulty': 'medium'},
    );

JournalEntry _mandateEdit(
        Map<String, dynamic> before, Map<String, dynamic> after) =>
    _entry(
      type: JournalEntryType.mandateEdit,
      tags: ['mandate'],
      payload: {'before': before, 'after': after},
    );

void main() {
  group('card 1 — how your trades ended', () {
    test('hidden under three closes, because 1/1 reads as 100%', () {
      expect(buildInsights([_closed('won'), _closed('lost')]).trades, isNull);
      expect(buildInsights([_closed('won'), _closed('lost'), _closed('manual')])
          .trades, isNotNull);
    });

    test('open trades are not closes', () {
      final open = List.generate(
          5, (_) => _entry(type: JournalEntryType.simTrade, tags: ['sim_trade']));
      expect(buildInsights(open).trades, isNull);
    });

    test('buckets on the tag the backend actually writes', () {
      final data = buildInsights([
        _closed('won'),
        _closed('won'),
        _closed('lost'),
        _closed('manual'),
      ]);
      expect(data.trades!.counts[TradeEnding.won], 2);
      expect(data.trades!.counts[TradeEnding.lost], 1);
      expect(data.trades!.counts[TradeEnding.manual], 1);
      expect(data.trades!.unclassified, 0);
      expect(data.trades!.total, 4);
    });

    test('a close with no known ending is disclosed, not dropped', () {
      // Dropping it silently makes every percentage in the card wrong by an
      // amount nobody can see.
      final data = buildInsights([
        _closed('won'),
        _closed('lost'),
        _entry(type: JournalEntryType.simTrade, tags: ['sim_trade', 'closed']),
      ]);
      expect(data.trades!.unclassified, 1);
      expect(data.trades!.total, 3);
    });
  });

  group('card 2 — what your PM decided', () {
    test('NO_VERDICT is its own outcome, never folded into REJECT', () {
      final data = buildInsights([
        _room('REJECT'),
        _room('NO_VERDICT'),
        _room('NO_VERDICT'),
      ]);
      expect(data.verdicts!.counts[VerdictOutcome.reject], 1,
          reason: 'CR098 — the PM declining to rule because the run had no '
              'market read is not the PM turning the idea down');
      expect(data.verdicts!.counts[VerdictOutcome.noVerdict], 2);
    });

    test('a run with no verdict recorded is excluded, never counted as PASS',
        () {
      final data = buildInsights([
        _room('APPROVE'),
        _room(null),
        _room(null),
      ]);
      expect(data.verdicts!.counts[VerdictOutcome.pass], isNull);
      expect(data.verdicts!.noVerdictRecorded, 2);
      expect(data.verdicts!.ruled, 1,
          reason: 'the denominator is rulings, not runs');
    });

    test('an action this build does not know is not bucketed as anything', () {
      final data = buildInsights([_room('APPROVE'), _room('DEFER')]);
      expect(data.verdicts!.ruled, 1);
      expect(data.verdicts!.noVerdictRecorded, 1);
    });

    test('no rooms, no card — and no rulings, no card either', () {
      expect(buildInsights([_closed('won')]).verdicts, isNull);
      expect(buildInsights([_room(null), _room(null)]).verdicts, isNull,
          reason: 'a window of runs that all failed says nothing about what '
              'the PM decides');
    });
  });

  group('card 3 — analysts you sought out', () {
    test('counts the doors you opened, not who spoke in the Room', () {
      final data = buildInsights([
        _entry(type: JournalEntryType.oneOnOne, agents: ['bull_researcher']),
        _entry(type: JournalEntryType.agentCoach, agents: ['bull_researcher']),
        _entry(type: JournalEntryType.agentUnlock, agents: ['trader']),
        // A Room run names all 12 agents. If this contributed, the chart would
        // report participation and label it readership.
        _entry(
          type: JournalEntryType.roomRun,
          agents: const [
            'fundamentals_analyst',
            'market_analyst',
            'bull_researcher',
            'trader',
          ],
          payload: const {'verdict': {'action': 'APPROVE'}},
        ),
      ]);
      expect(data.analysts.map((a) => a.agentId).toList(),
          ['bull_researcher', 'trader']);
      expect(data.analysts.first.count, 2);
    });

    test('sorted by how often, descending', () {
      final data = buildInsights([
        _entry(type: JournalEntryType.oneOnOne, agents: ['trader']),
        for (var i = 0; i < 3; i++)
          _entry(type: JournalEntryType.oneOnOne, agents: ['bear_researcher']),
      ]);
      expect(data.analysts.first.agentId, 'bear_researcher');
    });
  });

  group('card 4 — how your mandate has moved', () {
    test('the Day Trader preset is one edit, not seven loosenings', () {
      final data = buildInsights([
        _mandateEdit(
          {'risk_score': 3, 'max_drawdown_pct': 20, 'max_trades_per_day': 2},
          {'risk_score': 8, 'max_drawdown_pct': 40, 'max_trades_per_day': 20},
        ),
      ]);
      expect(data.mandate!.editCount, 1,
          reason: 'seven limits in one edit is one event; rendering it as '
              'seven describes a spree that never happened');
      expect(data.mandate!.moves, hasLength(3));
    });

    test('trajectory runs earliest→latest across the whole window', () {
      // Newest-first, as the endpoint returns: the LAST element holds the
      // earliest `before`. Getting this backwards reverses every direction
      // label, and a wrong direction reads exactly as confidently as a right
      // one.
      final data = buildInsights([
        _mandateEdit({'risk_score': 5}, {'risk_score': 9}), // newest
        _mandateEdit({'risk_score': 3}, {'risk_score': 5}), // oldest
      ]);
      final move = data.mandate!.moves.single;
      expect(move.from, 3);
      expect(move.to, 9);
      expect(move.loosened, isTrue);
    });

    test('a limit edited and edited back does not appear', () {
      final data = buildInsights([
        _mandateEdit({'risk_score': 7}, {'risk_score': 3}),
        _mandateEdit({'risk_score': 3}, {'risk_score': 7}),
      ]);
      expect(data.mandate!.moves, isEmpty);
      expect(data.mandate!.editCount, 2,
          reason: 'the edits still happened — only the net move is zero');
    });

    test('an unset limit is not a limit of zero', () {
      // The `?? 0` family: reading a null cap as 0 invents a move from "no
      // cap" to "cap of zero", which is both wrong and alarming.
      final data = buildInsights([
        _mandateEdit(
          {'risk_score': 3, 'sector_cap_pct': null},
          {'risk_score': 3, 'sector_cap_pct': 25},
        ),
      ]);
      expect(data.mandate!.moves, isEmpty);
    });

    test('tightening is distinguished from loosening', () {
      final data = buildInsights([
        _mandateEdit({'max_drawdown_pct': 40}, {'max_drawdown_pct': 15}),
      ]);
      expect(data.mandate!.moves.single.loosened, isFalse);
    });

    test('no edits, no card', () {
      expect(buildInsights([_closed('won')]).mandate, isNull);
    });
  });

  group('card 5 — daily challenge by type', () {
    test('a type under five attempts is omitted and counted, not shown', () {
      final data = buildInsights([
        for (var i = 0; i < 5; i++) _challenge('valuation', i.isEven),
        for (var i = 0; i < 4; i++) _challenge('risk', true),
      ]);
      expect(data.challenges!.rows.map((r) => r.type).toList(), ['valuation']);
      expect(data.challenges!.omittedTypes, 1,
          reason: 'named rather than dropped — "not enough attempts yet" is a '
              "true statement about the user's data; silence is one about ours");
    });

    test('a single 1/1 type never becomes a 100% row', () {
      final data = buildInsights([_challenge('valuation', true)]);
      expect(data.challenges, isNull);
    });

    test('counts correctness per type', () {
      final data = buildInsights([
        for (var i = 0; i < 6; i++) _challenge('valuation', i < 4),
      ]);
      final row = data.challenges!.rows.single;
      expect(row.attempts, 6);
      expect(row.correct, 4);
    });
  });

  group('the window is named honestly', () {
    test('under the cap, it is not "last 100"', () {
      final data = buildInsights(List.generate(12, (_) => _closed('won')));
      expect(data.entryCount, 12);
      expect(data.windowIsCapped, isFalse);
    });

    test('at the cap, it is', () {
      final data = buildInsights(
          List.generate(kInsightsWindow, (_) => _closed('won')));
      expect(data.windowIsCapped, isTrue,
          reason: 'past 100 an unlabelled aggregate describes the most recent '
              '100 while presenting itself as all-time');
    });
  });

  group('what is deliberately absent', () {
    test('the three non-computable panels are recorded, not rendered as zero',
        () {
      // Kept as a named list rather than a comment so a later session cannot
      // "fix" the gap by rendering a confident 0 (CR040).
      expect(InsightsData.notMeasured, [
        NotMeasured.voicesRead,
        NotMeasured.followedVsOverrode,
        NotMeasured.safetyFloorStops,
      ]);
    });

    test('an empty journal produces an empty aggregate, not zeroed cards', () {
      final data = buildInsights([]);
      expect(data.isEmpty, isTrue);
      expect(data.trades, isNull);
      expect(data.verdicts, isNull);
      expect(data.mandate, isNull);
      expect(data.challenges, isNull);
      expect(data.analysts, isEmpty);
    });
  });
}
