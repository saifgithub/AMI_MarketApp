/// CR106 — the two mappers into [RoomBoardData], side by side in one file.
///
/// They are here together on purpose. The bug this CR fixes is that the Room
/// and the Journal rendered the same run through two code paths that shared no
/// widget and no test, and the Journal's fell a whole CR behind without
/// anything failing (`DEF143`: `NO_VERDICT` shown as a rejection, the raw enum
/// on screen, CR098's withheld-analyst disclosure missing, no markdown). That
/// is DEF098's named class — two renderers, neither a superset of the other.
///
/// One widget and two mappers only helps if the mappers stay honest about the
/// same fields, so they live in the same file, where a change to one is read
/// next to the other, and `test/widgets/room_board_parity_test.dart` asserts a
/// live run and the journal entry built from it produce the same board
/// (acceptance #10).
///
/// Where the two surfaces genuinely differ, they differ in exactly three
/// declared ways, and nowhere else:
///   - the sub-header strip (`41s · 3 CREDITS` vs `MID TIER · MANDATE v7`) —
///     the snapshot never serialised duration or credit cost;
///   - `isRecord` / `recordedAt`, which suppress the trade ticket and date the
///     geometry (T-STALE);
///   - `runId`, which only a live run has.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/state/room_providers.dart';

/// Live Room → board.
///
/// `state.order` is arrival order and includes the locked chairs; the comb
/// wants the fixed eleven in roster order so it does not reshuffle as agents
/// finish. Both are honoured: the voices come from [kCombVoices], each filled
/// in from whatever the stream has so far.
RoomBoardData boardFromRoomState({
  required RoomState state,
  required String ticker,
}) {
  final verdict = state.verdict;
  final withheldIds = state.withheldAgents.keys.toSet();
  return RoomBoardData(
    ticker: ticker,
    // A finished run with no verdict is NO RESULT, not a missing board. An
    // outage must never be shaped like an outcome.
    outcome: verdict == null
        ? VerdictOutcome.noResult
        : outcomeFromAction(verdict.action),
    actionToken: verdict?.action ?? '',
    reason: verdict?.reason ?? '',
    sizePct: verdict?.sizePct,
    entry: verdict?.entry,
    stop: verdict?.stop,
    target: verdict?.target,
    horizonDays: verdict?.timeHorizonDays,
    violations: verdict?.violations ?? const [],
    overriddenFromLlm: verdict?.overriddenFromLlm ?? false,
    opinionsNotIncluded: verdict?.opinionsNotIncluded ?? const [],
    levelProvenance: verdict?.levelProvenance,
    runId: state.runId,
    voices: [
      for (final agent in kCombVoices)
        RoomVoice(
          agentId: agent.id,
          content: state.transcript[agent.id] ?? '',
          stance: state.agentStances[agent.id]?.stance,
          conviction: state.agentStances[agent.id]?.conviction,
          headline: state.agentStances[agent.id]?.headline,
          stanceRecorded: state.agentStances[agent.id]?.recorded ?? false,
          withheld: withheldIds.contains(agent.id),
        ),
    ],
  );
}

/// The transcript rows show all TWELVE agents, PM included — the comb shows
/// eleven. That inconsistency is deliberate, and it beats a graphic that
/// implies democracy. CR127: what reconciles the two counts for the reader is
/// the `PORTFOLIO MANAGER` card that follows the comb (`_ReasonBlock`) — the
/// PM is visibly the twelfth, given its own card after the eleven rather than
/// missing from them. It used to be a caption under the comb.
List<RoomVoice> transcriptVoicesFromRoomState(RoomState state) {
  final withheldIds = state.withheldAgents.keys.toSet();
  return [
    for (final agent in kAllAgents)
      if (kAgentPhase.containsKey(agent.id))
        RoomVoice(
          agentId: agent.id,
          content: state.transcript[agent.id] ?? '',
          stance: state.agentStances[agent.id]?.stance,
          conviction: state.agentStances[agent.id]?.conviction,
          headline: state.agentStances[agent.id]?.headline,
          stanceRecorded: state.agentStances[agent.id]?.recorded ?? false,
          withheld: withheldIds.contains(agent.id),
        ),
  ];
}

/// Journal entry → board.
///
/// The payload is a **snapshot taken at write time** and is not a `RoomRun`.
/// An entry written before a field existed will never have it, and re-fetching
/// `GET /v1/room/{reference_id}` does not fix that — `RoomRunRow.verdict` is
/// the same JSONB, written in the same moment. So the board degrades **per
/// entry**, and nothing here reconstructs a missing value (T-BACKFILL).
RoomBoardData? boardFromJournalEntry(JournalEntry entry) {
  final payload = entry.payload;
  final rawVerdict = (payload['verdict'] as Map?)?.cast<String, dynamic>();
  final rawTranscript = (payload['transcript'] as List?) ?? const [];

  final rows = <String, Map<String, dynamic>>{};
  for (final m in rawTranscript) {
    if (m is! Map) continue;
    final row = m.cast<String, dynamic>();
    final id = row['agent_id'] as String?;
    if (id != null && id.isNotEmpty) rows[id] = row;
  }

  // A room entry with neither a verdict nor a transcript has no board to draw.
  if (rawVerdict == null && rows.isEmpty) return null;

  final action = rawVerdict?['action'] as String?;
  return RoomBoardData(
    ticker: entry.ticker ?? '',
    outcome: rawVerdict == null
        ? VerdictOutcome.noResult
        : outcomeFromAction(action),
    actionToken: action ?? '',
    reason: rawVerdict?['reason'] as String? ?? '',
    sizePct: (rawVerdict?['size_pct'] as num?)?.toDouble(),
    entry: (rawVerdict?['entry'] as num?)?.toDouble(),
    stop: (rawVerdict?['stop'] as num?)?.toDouble(),
    target: (rawVerdict?['target'] as num?)?.toDouble(),
    horizonDays: (rawVerdict?['time_horizon_days'] as num?)?.toInt(),
    violations: ((rawVerdict?['violations'] as List?) ?? const [])
        .whereType<String>()
        .toList(),
    overriddenFromLlm: (rawVerdict?['overridden_from_llm'] as bool?) ?? false,
    // The CR098 disclosure the Journal used to drop entirely (`DEF143`): a
    // replay of a partial-roster run silently asserted a full roster, which
    // inverts the whole point of CR098.
    opinionsNotIncluded:
        ((rawVerdict?['opinions_not_included'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
    levelProvenance: parseLevelProvenance(rawVerdict?['level_provenance']),
    isRecord: true,
    recordedAt: entry.createdAt,
    voices: [
      for (final agent in kCombVoices)
        _voiceFromRow(agent.id, rows[agent.id]),
    ],
  );
}

/// Twelve rows for the Journal's transcript, same as the Room's.
List<RoomVoice> transcriptVoicesFromJournalEntry(JournalEntry entry) {
  final rows = <String, Map<String, dynamic>>{};
  for (final m in (entry.payload['transcript'] as List?) ?? const []) {
    if (m is! Map) continue;
    final row = m.cast<String, dynamic>();
    final id = row['agent_id'] as String?;
    if (id != null && id.isNotEmpty) rows[id] = row;
  }
  return [
    for (final agent in kAllAgents)
      if (kAgentPhase.containsKey(agent.id)) _voiceFromRow(agent.id, rows[agent.id]),
  ];
}

RoomVoice _voiceFromRow(String agentId, Map<String, dynamic>? row) {
  return RoomVoice(
    agentId: agentId,
    content: row?['content'] as String? ?? '',
    stance: row?['stance'] as String?,
    conviction: row?['conviction'] as String?,
    headline: row?['headline'] as String?,
    // Key presence, not value — a pre-B2 entry has no key at all and the comb
    // must say "not recorded" rather than "nobody had a view".
    stanceRecorded: row?.containsKey('stance') ?? false,
  );
}
