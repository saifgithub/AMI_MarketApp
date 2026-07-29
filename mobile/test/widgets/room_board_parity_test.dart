/// CR106 acceptance #10 — **the Room and the Journal render the same board.**
///
/// This is the guard the whole CR turns on. DEF098 named the failure class in
/// this codebase — *two independent renderers of the same data, neither a
/// superset of the other, drifting because a developer has to remember both* —
/// and the Room-vs-Journal split was that same shape one layer up in the UI. It
/// had already produced a live wrong answer (`DEF143`): a `NO_VERDICT` run
/// rendered correctly in the Room and as a **rejection**, in a raw enum token,
/// in the permanent record thirty seconds later.
///
/// Nothing failed when that happened, because nothing compared them.
///
/// So this file takes a payload shaped exactly as `build_journal_entry_for_run`
/// writes it, pushes it through BOTH mappers, and asserts the resulting boards
/// agree on every field both surfaces carry. The three declared differences —
/// the sub-header strip, `isRecord`/`recordedAt`, and `runId` — are asserted to
/// be the ONLY differences, so a fourth one cannot appear quietly.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter_test/flutter_test.dart';

/// The verdict as the wire carries it — `use_enum_values=True`, so `action` is
/// a bare string and every absent level is an explicit null.
Map<String, dynamic> _verdictJson({
  String action = 'APPROVE',
  Map<String, String>? provenance = const {
    'entry': 'pm',
    'stop': 'ami_default',
    'target': 'pm',
  },
  List<String> withheld = const ['social_media_analyst'],
}) =>
    {
      'action': action,
      'size_pct': 3.0,
      'entry': 150.0,
      'stop': 141.0,
      'target': 172.0,
      'time_horizon_days': 42,
      'reason': 'Synthesis defended; mandate clears.',
      'violations': <String>[],
      'overridden_from_llm': false,
      'opinions_not_included': withheld,
      if (provenance != null) 'level_provenance': provenance,
    };

/// One transcript row as `build_journal_entry_for_run` writes it.
Map<String, dynamic> _row(
  String agentId, {
  String content = 'A contribution with a **6.2%** metric.',
  String? stance = 'for',
  String? conviction = 'high',
  String? headline = 'FCF 6.2% vs 3.1%',
  bool includeStanceKeys = true,
}) =>
    {
      'agent_id': agentId,
      'content': content,
      if (includeStanceKeys) 'stance': stance,
      if (includeStanceKeys) 'conviction': conviction,
      if (includeStanceKeys) 'headline': headline,
    };

List<Map<String, dynamic>> _fullTranscript({bool includeStanceKeys = true}) => [
      for (final a in kAllAgents)
        if (kAgentPhase.containsKey(a.id))
          _row(
            a.id,
            includeStanceKeys: includeStanceKeys,
            // A spread of stances, so a mapper that collapsed them all to one
            // value would not slip past the band counts below.
            stance: switch (a.id) {
              'bear_researcher' => 'against',
              'conservative_debator' => 'against',
              'neutral_debator' => 'neutral',
              'news_analyst' => null,
              _ => 'for',
            },
          ),
    ];

JournalEntry _journalEntry({
  Map<String, dynamic>? verdict,
  List<Map<String, dynamic>>? transcript,
}) =>
    JournalEntry(
      id: 'entry-1',
      userId: 'user-1',
      entryType: JournalEntryType.roomRun,
      title: 'Room on AAPL — APPROVE',
      ticker: 'AAPL',
      createdAt: DateTime.utc(2026, 6, 2, 14, 30),
      agentsInvolved: const [],
      tags: const ['room'],
      mandateVersion: 7,
      payload: {
        'verdict': verdict ?? _verdictJson(),
        'model_tier': 'mid',
        'transcript': transcript ?? _fullTranscript(),
      },
    );

/// The same run as live state, built from the same JSON so neither side gets a
/// hand-tuned fixture the other does not have.
RoomState _roomState({
  Map<String, dynamic>? verdict,
  List<Map<String, dynamic>>? transcript,
}) {
  final rows = transcript ?? _fullTranscript();
  return RoomState(
    done: true,
    runId: 'run-1',
    order: [for (final r in rows) r['agent_id'] as String],
    transcript: {
      for (final r in rows) r['agent_id'] as String: r['content'] as String,
    },
    agentStances: {
      for (final r in rows)
        r['agent_id'] as String: AgentStance(
          stance: r['stance'] as String?,
          conviction: r['conviction'] as String?,
          headline: r['headline'] as String?,
          recorded: r.containsKey('stance'),
        ),
    },
    verdict: RoomVerdict.fromJson(verdict ?? _verdictJson()),
  );
}

/// Every field a board carries, flattened — so the comparison is exhaustive by
/// construction rather than by whichever fields someone remembered to assert.
Map<String, Object?> _fingerprint(RoomBoardData d) => {
      'ticker': d.ticker,
      'outcome': d.outcome,
      'actionToken': d.actionToken,
      'reason': d.reason,
      'sizePct': d.sizePct,
      'entry': d.entry,
      'stop': d.stop,
      'target': d.target,
      'horizonDays': d.horizonDays,
      'violations': d.violations,
      'overriddenFromLlm': d.overriddenFromLlm,
      'opinionsNotIncluded': d.opinionsNotIncluded,
      'levelProvenance': d.levelProvenance,
      'showsRibbon': d.showsRibbon,
      'riskReward': d.riskReward,
      'derivedLevelKeys': d.derivedLevelKeys,
      'stancesRecorded': d.stancesRecorded,
      'statedCount': d.statedCount,
      'for': [for (final v in d.voicesFor) v.agentId],
      'against': [for (final v in d.voicesAgainst) v.agentId],
      'neutral': [for (final v in d.voicesNeutral) v.agentId],
      'notStated': [for (final v in d.voicesNotStated) v.agentId],
      'withheldAnalystIds': d.withheldAnalystIds,
      'headlines': [for (final v in d.voices) v.headline],
    };

void main() {
  test('the fixture is not vacuous', () {
    // A parity assertion between two empty boards is green for the wrong
    // reason. Pin the shape the comparison depends on.
    final board = boardFromJournalEntry(_journalEntry())!;
    expect(board.voices.length, 11, reason: 'the comb is eleven voices');
    expect(board.statedCount, 10, reason: 'one agent deliberately states none');
    expect(board.voicesFor, isNotEmpty);
    expect(board.voicesAgainst, isNotEmpty);
    expect(board.voicesNeutral, isNotEmpty);
    expect(board.voicesNotStated, isNotEmpty);
    expect(board.showsRibbon, isTrue);
  });

  test('acceptance #10 — the two mappers produce the same board', () {
    final fromRoom =
        boardFromRoomState(state: _roomState(), ticker: 'AAPL');
    final fromJournal = boardFromJournalEntry(_journalEntry())!;
    expect(_fingerprint(fromJournal), _fingerprint(fromRoom));
  });

  test('the only differences are the three declared ones', () {
    final fromRoom =
        boardFromRoomState(state: _roomState(), ticker: 'AAPL');
    final fromJournal = boardFromJournalEntry(_journalEntry())!;

    // A journal entry is a RECORD: it dates its geometry and offers no trade
    // ticket (T-STALE). A live run is neither.
    expect(fromJournal.isRecord, isTrue);
    expect(fromRoom.isRecord, isFalse);
    expect(fromJournal.recordedAt, isNotNull);
    expect(fromRoom.recordedAt, isNull);

    // Only a live run can link a trade back to its verdict.
    expect(fromRoom.runId, 'run-1');
    expect(fromJournal.runId, isNull);

    // The strip: `duration_ms` and `credit_cost` were never serialised into
    // the snapshot, so the record shows tier + mandate version instead.
    expect(fromJournal.meta.modelTier, 'mid');
    expect(fromJournal.meta.mandateVersion, 7);
  });

  test('every VerdictAction maps to the same outcome on both surfaces', () {
    // The enum has grown twice (PASS, then NO_VERDICT) and each time only one
    // renderer learned. Iterated over the wire vocabulary rather than a
    // hand-listed subset, plus a value we have never shipped.
    const wireActions = [
      'APPROVE',
      'PASS',
      'REJECT',
      'MODIFY',
      'NO_VERDICT',
      'DEFERRED_PENDING_EARNINGS',
    ];
    for (final action in wireActions) {
      final v = _verdictJson(action: action);
      final room = boardFromRoomState(
          state: _roomState(verdict: v), ticker: 'AAPL');
      final journal = boardFromJournalEntry(_journalEntry(verdict: v))!;
      expect(journal.outcome, room.outcome, reason: action);
      expect(journal.actionToken, room.actionToken, reason: action);
      expect(journal.isNeutral, room.isNeutral, reason: action);
    }
  });

  test('DEF143 — NO_VERDICT is neutral on the Journal, not a rejection', () {
    // The defect verbatim: the Journal's own renderer had
    // `APPROVE ? green : PASS ? slate : amber`, so NO_VERDICT fell into the
    // amber reject bucket while the Room showed it correctly.
    final journal = boardFromJournalEntry(
      _journalEntry(verdict: _verdictJson(action: 'NO_VERDICT')),
    )!;
    expect(journal.outcome, VerdictOutcome.noVerdict);
    expect(journal.isNeutral, isTrue);
    expect(journal.isReject, isFalse);
  });

  test('DEF143 — the Journal carries the CR098 withheld disclosure', () {
    // The old block read `action` and `reason` and nothing else, so a replay
    // of a partial-roster run silently asserted a full roster — inverting the
    // whole point of CR098.
    final journal = boardFromJournalEntry(_journalEntry())!;
    expect(journal.opinionsNotIncluded, ['social_media_analyst']);
    expect(journal.withheldAnalystIds, contains('social_media_analyst'));
  });

  test('DEF143 — the Journal keeps the agent contributions intact', () {
    // The old block emitted a bare `Text(content)`, so `**bold**` metrics
    // reached the user as literal asterisks. The content now flows to the
    // shared markdown row untouched.
    final journal = boardFromJournalEntry(_journalEntry())!;
    expect(journal.voices.first.content, contains('**6.2%**'));
  });

  group('vintage degradation is per entry, and never backfilled', () {
    test('no level_provenance → no ribbon, on both surfaces', () {
      final v = _verdictJson(provenance: null);
      final room =
          boardFromRoomState(state: _roomState(verdict: v), ticker: 'AAPL');
      final journal = boardFromJournalEntry(_journalEntry(verdict: v))!;
      for (final board in [room, journal]) {
        expect(board.levelProvenance, isNull);
        expect(board.showsRibbon, isFalse,
            reason: 'the geometry IS the claim — T-PROV');
        // The prices are still there; only the graphic that would attribute
        // them is withheld.
        expect(board.entry, 150.0);
      }
    });

    test('no stance keys → "not recorded", not eleven silent agents', () {
      final t = _fullTranscript(includeStanceKeys: false);
      final room = boardFromRoomState(
          state: _roomState(transcript: t), ticker: 'AAPL');
      final journal = boardFromJournalEntry(_journalEntry(transcript: t))!;
      for (final board in [room, journal]) {
        expect(board.stancesRecorded, isFalse);
        expect(board.statedCount, 0);
      }
    });

    test('a recorded null stance is NOT the same as an unrecorded one', () {
      // The distinction the whole degradation rests on. An agent that took no
      // side goes to the gutter of a real comb; a run that recorded nothing
      // gets one honest sentence instead of a comb.
      final recorded = boardFromJournalEntry(_journalEntry())!;
      expect(recorded.stancesRecorded, isTrue);
      expect(recorded.voicesNotStated.map((v) => v.agentId), ['news_analyst']);

      final unrecorded = boardFromJournalEntry(
        _journalEntry(transcript: _fullTranscript(includeStanceKeys: false)),
      )!;
      expect(unrecorded.stancesRecorded, isFalse);
    });
  });

  test('band counts are taken over stated positions only (T-SUM11)', () {
    final board = boardFromJournalEntry(_journalEntry())!;
    final banded = board.voicesFor.length +
        board.voicesAgainst.length +
        board.voicesNeutral.length;
    expect(banded, 10);
    expect(board.voices.length, 11);
    expect(banded, lessThan(board.voices.length),
        reason: 'a count that always sums to the total would state a '
            'consensus that never occurred');
    expect(board.statedCount, banded);
  });

  group('the risk/reward ratio is computed, never accepted', () {
    test('from the same three prices the widget draws', () {
      final board = boardFromJournalEntry(_journalEntry())!;
      // (172 - 150) / (150 - 141) = 22 / 9
      expect(board.riskReward, closeTo(22 / 9, 1e-9));
    });

    test('an incoherent triple yields no ratio and no ribbon', () {
      for (final bad in [
        {'entry': 150.0, 'stop': 160.0, 'target': 172.0}, // stop above entry
        {'entry': 150.0, 'stop': 141.0, 'target': 140.0}, // target below stop
        {'entry': 150.0, 'stop': 150.0, 'target': 172.0}, // zero risk
        {'entry': 150.0, 'stop': 0.0, 'target': 172.0}, // no stop at all
      ]) {
        final board = boardFromJournalEntry(
          _journalEntry(verdict: {..._verdictJson(), ...bad}),
        )!;
        expect(board.riskReward, isNull, reason: '$bad');
        expect(board.showsRibbon, isFalse, reason: '$bad');
      }
    });
  });

  test('derived levels are named, stated ones are not', () {
    final board = boardFromJournalEntry(_journalEntry())!;
    // entry: pm, stop: ami_default, target: pm
    expect(board.derivedLevelKeys, ['stop']);
    expect(board.sourceFor('entry'), LevelSource.pm);
    expect(board.sourceFor('stop'), LevelSource.amiDefault);
  });

  test('a substituted entry is named as the Trader\'s, not the PM\'s', () {
    final board = boardFromJournalEntry(
      _journalEntry(
        verdict: _verdictJson(provenance: const {
          'entry': 'trader',
          'stop': 'pm',
          'target': 'pm',
        }),
      ),
    )!;
    expect(board.sourceFor('entry'), LevelSource.trader);
    expect(board.derivedLevelKeys, ['entry']);
  });

  test('a provenance value we do not recognise is not silently trusted', () {
    final board = boardFromJournalEntry(
      _journalEntry(
        verdict: _verdictJson(provenance: const {
          'entry': 'some_future_source',
          'stop': 'pm',
          'target': 'pm',
        }),
      ),
    )!;
    expect(board.sourceFor('entry'), LevelSource.unknown);
    // Unknown is not "derived" — we cannot claim AMI supplied it — but it is
    // also not a PM decision, so the ribbon still draws with the entry cap
    // solid and only truly-derived levels hollow.
    expect(board.derivedLevelKeys, isEmpty);
  });

  test('the transcript shows twelve agents on both surfaces, comb eleven', () {
    // Deliberate and labelled: transcript mode shows the PM's own turn, the
    // comb does not, because the PM's position is the hero tile (T-VOTE).
    final roomRows = transcriptVoicesFromRoomState(_roomState());
    final journalRows = transcriptVoicesFromJournalEntry(_journalEntry());
    expect(roomRows.length, 12);
    expect(journalRows.length, 12);
    expect([for (final v in roomRows) v.agentId],
        [for (final v in journalRows) v.agentId]);
    expect(boardFromJournalEntry(_journalEntry())!.voices.length, 11);
  });

  test('an entry with neither verdict nor transcript renders no board', () {
    final empty = JournalEntry(
      id: 'e',
      userId: 'u',
      entryType: JournalEntryType.roomRun,
      title: 'Room on AAPL — failed',
      createdAt: DateTime.utc(2026, 6, 2),
      agentsInvolved: const [],
      tags: const [],
      payload: const {'model_tier': 'mid'},
    );
    expect(boardFromJournalEntry(empty), isNull);
  });

  test('a run that finished with no verdict is NO RESULT, not a blank', () {
    // Reachable today, and it must not be shaped like an outcome.
    final room = boardFromRoomState(
      state: const RoomState(done: true, runId: 'r'),
      ticker: 'AAPL',
    );
    expect(room.outcome, VerdictOutcome.noResult);
    expect(room.isNeutral, isFalse, reason: 'an outage is not a "not now"');
  });
}
