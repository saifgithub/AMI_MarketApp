/// Decision Journal — client models. Mirrors backend/app/schemas/journal.py.
library;

enum JournalEntryType {
  roomRun,
  oneOnOne,
  simTrade,
  mandateEdit,
  agentCoach,
  driftAlert,
  lessonComplete,
  agentUnlock,
}

extension JournalEntryTypeJson on JournalEntryType {
  String get wire {
    switch (this) {
      case JournalEntryType.roomRun:
        return 'room_run';
      case JournalEntryType.oneOnOne:
        return 'one_on_one';
      case JournalEntryType.simTrade:
        return 'sim_trade';
      case JournalEntryType.mandateEdit:
        return 'mandate_edit';
      case JournalEntryType.agentCoach:
        return 'agent_coach';
      case JournalEntryType.driftAlert:
        return 'drift_alert';
      case JournalEntryType.lessonComplete:
        return 'lesson_complete';
      case JournalEntryType.agentUnlock:
        return 'agent_unlock';
    }
  }

  static JournalEntryType? fromWire(String? s) {
    switch (s) {
      case 'room_run':
        return JournalEntryType.roomRun;
      case 'one_on_one':
        return JournalEntryType.oneOnOne;
      case 'sim_trade':
        return JournalEntryType.simTrade;
      case 'mandate_edit':
        return JournalEntryType.mandateEdit;
      case 'agent_coach':
        return JournalEntryType.agentCoach;
      case 'drift_alert':
        return JournalEntryType.driftAlert;
      case 'lesson_complete':
        return JournalEntryType.lessonComplete;
      case 'agent_unlock':
        return JournalEntryType.agentUnlock;
    }
    return null;
  }
}

class JournalEntry {
  const JournalEntry({
    required this.id,
    required this.userId,
    required this.entryType,
    required this.title,
    required this.createdAt,
    required this.agentsInvolved,
    required this.tags,
    this.summary,
    this.ticker,
    this.userNote,
    this.outcome,
    this.referenceId,
    this.mandateVersion = 1,
    this.payload = const {},
    this.deletedAt,
  });

  final String id;
  final String userId;
  final JournalEntryType entryType;
  final String? referenceId;
  final String title;
  final String? summary;
  final String? ticker;
  final List<String> agentsInvolved;
  final List<String> tags;
  final String? userNote;
  final String? outcome;
  /// Mandate version active when this entry was captured. Used to replay past
  /// decisions against the mandate they were made under (audit trail).
  final int mandateVersion;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  // Set only for entries returned from /v1/journal/{u}/trash; null on
  // the regular list since live entries always have deleted_at IS NULL.
  final DateTime? deletedAt;

  factory JournalEntry.fromJson(Map<String, dynamic> j) {
    return JournalEntry(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      entryType: JournalEntryTypeJson.fromWire(j['entry_type'] as String?) ??
          JournalEntryType.oneOnOne,
      referenceId: j['reference_id'] as String?,
      title: j['title'] as String,
      summary: j['summary'] as String?,
      ticker: j['ticker'] as String?,
      agentsInvolved:
          ((j['agents_involved'] as List?) ?? const []).cast<String>(),
      tags: ((j['tags'] as List?) ?? const []).cast<String>(),
      userNote: j['user_note'] as String?,
      outcome: j['outcome'] as String?,
      mandateVersion: (j['mandate_version'] as num?)?.toInt() ?? 1,
      payload: (j['payload'] as Map?)?.cast<String, dynamic>() ?? const {},
      createdAt: DateTime.parse(j['created_at'] as String),
      deletedAt: j['deleted_at'] != null
          ? DateTime.parse(j['deleted_at'] as String)
          : null,
    );
  }
}

class JournalListResponse {
  const JournalListResponse({
    required this.entries,
    required this.total,
    this.retentionDays,
  });

  final List<JournalEntry> entries;
  final int total;
  final int? retentionDays;

  factory JournalListResponse.fromJson(Map<String, dynamic> j) {
    return JournalListResponse(
      entries: ((j['entries'] as List?) ?? const [])
          .map((e) => JournalEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: ((j['total'] as num?) ?? 0).toInt(),
      retentionDays: j['retention_days'] == null
          ? null
          : (j['retention_days'] as num).toInt(),
    );
  }
}
