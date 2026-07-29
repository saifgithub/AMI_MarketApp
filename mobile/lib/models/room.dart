/// Convene the Room — client-side models.
/// Mirrors backend/app/schemas/room.py.
library;

/// CR106 B1 — where one price on a verdict came from.
///
/// `unknown` is a value the wire sent that this build does not recognise, kept
/// distinct from `null` (the field was absent, i.e. the run predates B1). Both
/// suppress the risk/reward ribbon; only the second suppresses the whole
/// provenance treatment, because a level we cannot attribute is not the same
/// thing as a run that recorded no attributions.
enum LevelSource { pm, trader, amiDefault, unknown }

LevelSource _levelSourceFrom(Object? raw) {
  switch (raw) {
    case 'pm':
      return LevelSource.pm;
    case 'trader':
      return LevelSource.trader;
    case 'ami_default':
      return LevelSource.amiDefault;
    default:
      return LevelSource.unknown;
  }
}

class RoomVerdict {
  const RoomVerdict({
    required this.action,
    required this.reason,
    required this.violations,
    required this.overriddenFromLlm,
    this.sizePct,
    this.entry,
    this.target,
    this.stop,
    this.timeHorizonDays,
    this.opinionsNotIncluded = const [],
    this.levelProvenance,
  });

  /// 'APPROVE' | 'REJECT' | 'MODIFY' | 'PASS' | 'NO_VERDICT'.
  ///
  /// The enum grows — `NO_VERDICT` (CR098 Amendment 2) is the proof. Treat any
  /// value you do not recognise as a non-approval and render it neutrally
  /// rather than switching on an exhaustive list that a backend release can
  /// invalidate.
  final String action;
  final double? sizePct;
  final double? entry;
  final double? target;
  final double? stop;
  final int? timeHorizonDays;
  final String reason;
  final List<String> violations;
  final bool overriddenFromLlm;

  /// `AgentId` values that were NOT in the room for this run (CR098 D3).
  /// Always present on the wire, empty on an ordinary full-roster run — so
  /// empty must render nothing at all, never an empty header (D4).
  final List<String> opinionsNotIncluded;

  /// CR106 B1 — `entry` / `stop` / `target` → where each price came from.
  ///
  /// `null` means the run predates the field, NOT that everything came from the
  /// PM. The board never infers it: an entry with no provenance renders in the
  /// plain metric list with no ribbon and no ratio (T-PROV / T-BACKFILL).
  final Map<String, LevelSource>? levelProvenance;

  bool get isApprove => action == 'APPROVE';
  bool get isReject => action == 'REJECT';
  bool get isPass => action == 'PASS';

  /// CR098 Amendment 2 — the PM declined to call a trade because the session
  /// ran without a market read. Every level field is null in this state, and
  /// it is a professional refusal, NOT a rejection: rendering it in the
  /// reject treatment tells the user their thesis was turned down.
  bool get isNoVerdict => action == 'NO_VERDICT';

  factory RoomVerdict.fromJson(Map<String, dynamic> j) {
    return RoomVerdict(
      action: j['action'] as String? ?? 'PASS',
      sizePct: (j['size_pct'] as num?)?.toDouble(),
      entry: (j['entry'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      stop: (j['stop'] as num?)?.toDouble(),
      timeHorizonDays: (j['time_horizon_days'] as num?)?.toInt(),
      reason: j['reason'] as String? ?? '',
      violations: ((j['violations'] as List?) ?? const [])
          .whereType<String>()
          .toList(),
      overriddenFromLlm: (j['overridden_from_llm'] as bool?) ?? false,
      // `whereType`, not `cast`: `cast` defers the type error to first read, so
      // one non-String on the wire would throw inside build() rather than here.
      opinionsNotIncluded: ((j['opinions_not_included'] as List?) ?? const [])
          .whereType<String>()
          .toList(),
      levelProvenance: parseLevelProvenance(j['level_provenance']),
    );
  }
}

/// Shared by [RoomVerdict.fromJson] and the Journal's payload mapper so the
/// two surfaces cannot disagree about what a provenance map means (T-TWICE).
/// An absent or non-map value stays `null` — "not recorded", never inferred.
Map<String, LevelSource>? parseLevelProvenance(Object? raw) {
  if (raw is! Map) return null;
  final out = <String, LevelSource>{};
  for (final key in const ['entry', 'stop', 'target']) {
    final v = raw[key];
    if (v != null) out[key] = _levelSourceFrom(v);
  }
  return out.isEmpty ? null : out;
}

class RoomTranscriptLine {
  const RoomTranscriptLine({
    required this.agentId,
    required this.content,
    this.stance,
    this.conviction,
    this.headline,
    this.stanceRecorded = false,
  });

  final String agentId;
  final String content;

  /// CR106 B2 — the agent's own stated position: `for` / `against` / `neutral`,
  /// or null when it stated none. Null NEVER means neutral; the comb puts it in
  /// a separate gutter and counts bands over non-null stances only (T-SUM11).
  final String? stance;

  /// `low` / `medium` / `high`, quantised server-side. Null renders no bar and
  /// no track at all — absence must not look like "low".
  final String? conviction;

  /// The agent's own headline number, already length-capped server-side.
  final String? headline;

  /// Whether the payload carried the stance field at all. Distinguishes "this
  /// agent took no side" (recorded, null) from "this run predates B2" (not
  /// recorded) — the comb shows a gutter for the first and one honest sentence
  /// for the second, and never reconstructs either (T-BACKFILL).
  final bool stanceRecorded;
}

class RoomRunSnapshot {
  const RoomRunSnapshot({
    required this.id,
    required this.userId,
    required this.ticker,
    required this.status,
    required this.modelTier,
    required this.transcript,
    this.verdict,
    this.creditCost,
    this.durationMs,
  });

  final String id;
  final String userId;
  final String ticker;
  final String status;
  final String modelTier;
  final List<RoomTranscriptLine> transcript;
  final RoomVerdict? verdict;
  final int? creditCost;
  final int? durationMs;

  factory RoomRunSnapshot.fromJson(Map<String, dynamic> j) {
    return RoomRunSnapshot(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      ticker: j['ticker'] as String,
      status: j['status'] as String? ?? 'completed',
      modelTier: j['model_tier'] as String? ?? 'mid',
      transcript: ((j['transcript'] as List?) ?? const [])
          .map((m) => RoomTranscriptLine(
                agentId: (m['agent_id'] as String?) ?? '',
                content: (m['content'] as String?) ?? '',
                stance: m['stance'] as String?,
                conviction: m['conviction'] as String?,
                headline: m['headline'] as String?,
                // Key PRESENCE, not value: a server that predates B2 sends no
                // key at all, and "this run recorded no stances" is a
                // different fact from "this agent stated none" (T-BACKFILL).
                stanceRecorded: m is Map && m.containsKey('stance'),
              ))
          .toList(),
      verdict: j['verdict'] == null
          ? null
          : RoomVerdict.fromJson(j['verdict'] as Map<String, dynamic>),
      creditCost: (j['credit_cost'] as num?)?.toInt(),
      durationMs: (j['duration_ms'] as num?)?.toInt(),
    );
  }
}
