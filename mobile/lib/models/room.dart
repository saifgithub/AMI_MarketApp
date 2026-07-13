/// Convene the Room — client-side models.
/// Mirrors backend/app/schemas/room.py.
library;

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
  });

  /// 'APPROVE' | 'REJECT' | 'MODIFY' | 'PASS'
  final String action;
  final double? sizePct;
  final double? entry;
  final double? target;
  final double? stop;
  final int? timeHorizonDays;
  final String reason;
  final List<String> violations;
  final bool overriddenFromLlm;

  bool get isApprove => action == 'APPROVE';
  bool get isReject => action == 'REJECT';
  bool get isPass => action == 'PASS';

  factory RoomVerdict.fromJson(Map<String, dynamic> j) {
    return RoomVerdict(
      action: j['action'] as String? ?? 'PASS',
      sizePct: (j['size_pct'] as num?)?.toDouble(),
      entry: (j['entry'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      stop: (j['stop'] as num?)?.toDouble(),
      timeHorizonDays: (j['time_horizon_days'] as num?)?.toInt(),
      reason: j['reason'] as String? ?? '',
      violations: ((j['violations'] as List?) ?? const []).cast<String>(),
      overriddenFromLlm: (j['overridden_from_llm'] as bool?) ?? false,
    );
  }
}

class RoomTranscriptLine {
  const RoomTranscriptLine({
    required this.agentId,
    required this.content,
  });

  final String agentId;
  final String content;
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
