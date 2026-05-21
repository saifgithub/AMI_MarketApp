/// Brief Your Agent — client-side models (was Coach — renamed AT:R27).
/// Mirrors backend/app/schemas/brief.py.
library;

enum BriefMode { fromScratch, fromPastCalls, raw }

extension BriefModeJson on BriefMode {
  String get wire {
    switch (this) {
      case BriefMode.fromScratch:
        return 'from_scratch';
      case BriefMode.fromPastCalls:
        return 'from_past_calls';
      case BriefMode.raw:
        return 'raw';
    }
  }
}

class UserOverlay {
  const UserOverlay({
    required this.id,
    required this.userId,
    required this.agentId,
    required this.version,
    required this.content,
    required this.plainEnglish,
    required this.createdAt,
    this.basedOnSession,
  });

  final String id;
  final String userId;
  final String agentId;
  final int version;
  final String content;
  final String plainEnglish;
  final DateTime createdAt;
  final String? basedOnSession;

  factory UserOverlay.fromJson(Map<String, dynamic> j) {
    return UserOverlay(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      agentId: j['agent_id'] as String,
      version: (j['version'] as num).toInt(),
      content: j['content'] as String,
      plainEnglish: j['plain_english'] as String,
      createdAt: DateTime.parse(j['created_at'] as String),
      basedOnSession: j['based_on_session'] as String?,
    );
  }
}

class BriefProposal {
  const BriefProposal({
    required this.id,
    required this.sessionId,
    required this.plainEnglish,
    required this.overlayAddition,
    required this.fullOverlayPreview,
    required this.refused,
    this.refusalReason,
    this.proposedAt,
  });

  final String id;
  final String sessionId;
  final String plainEnglish;
  final String overlayAddition;
  final String fullOverlayPreview;
  final bool refused;
  final String? refusalReason;
  // Backend default-factories this on creation. Nullable on the wire only
  // because old payloads pre-AT:R32 didn't ship it. Once all clients are
  // current, mark non-null. (BL14, AT:R32.)
  final DateTime? proposedAt;

  factory BriefProposal.fromJson(Map<String, dynamic> j) {
    return BriefProposal(
      id: j['id'] as String,
      sessionId: j['session_id'] as String,
      plainEnglish: j['plain_english'] as String? ?? '',
      overlayAddition: j['overlay_addition'] as String? ?? '',
      fullOverlayPreview: j['full_overlay_preview'] as String? ?? '',
      refused: (j['refused'] as bool?) ?? false,
      refusalReason: j['refusal_reason'] as String?,
      proposedAt: j['proposed_at'] != null
          ? DateTime.parse(j['proposed_at'] as String)
          : null,
    );
  }
}

class BriefSession {
  const BriefSession({
    required this.id,
    required this.userId,
    required this.agentId,
    required this.mode,
    required this.locale,
    required this.baseOverlayVersion,
    this.mandateUsed = const {},
    this.pendingProposal,
    this.startedAt,
  });

  final String id;
  final String userId;
  final String agentId;
  final String mode;
  final String locale;
  final int baseOverlayVersion;

  /// Full snapshot of the mandate at session start. Kept on the client for
  /// post-hoc safety-floor audit + offline replay. Opaque map — same shape
  /// as the backend `Mandate.model_dump()`.
  final Map<String, dynamic> mandateUsed;

  /// The proposal currently awaiting accept/reject, if any. Cleared when the
  /// user accepts or rejects.
  final BriefProposal? pendingProposal;

  /// Backend default-factories this when the session is created. Nullable
  /// only for old payloads pre-AT:R32. (BL14, AT:R32.)
  final DateTime? startedAt;

  factory BriefSession.fromJson(Map<String, dynamic> j) {
    return BriefSession(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      agentId: j['agent_id'] as String,
      mode: j['mode'] as String,
      locale: j['locale'] as String? ?? 'en',
      baseOverlayVersion: ((j['base_overlay_version'] as num?) ?? 0).toInt(),
      mandateUsed:
          (j['mandate_used'] as Map?)?.cast<String, dynamic>() ?? const {},
      pendingProposal: j['pending_proposal'] != null
          ? BriefProposal.fromJson(
              (j['pending_proposal'] as Map).cast<String, dynamic>(),
            )
          : null,
      startedAt: j['started_at'] != null
          ? DateTime.parse(j['started_at'] as String)
          : null,
    );
  }
}

class BriefStartResponse {
  const BriefStartResponse({
    required this.session,
    required this.openingMessage,
    this.currentOverlay,
  });

  final BriefSession session;
  final UserOverlay? currentOverlay;
  final String openingMessage;

  factory BriefStartResponse.fromJson(Map<String, dynamic> j) {
    final overlayJson = j['current_overlay'];
    return BriefStartResponse(
      session: BriefSession.fromJson(j['session'] as Map<String, dynamic>),
      currentOverlay: overlayJson == null
          ? null
          : UserOverlay.fromJson(overlayJson as Map<String, dynamic>),
      openingMessage: j['opening_message'] as String? ?? '',
    );
  }
}

class BriefHistory {
  const BriefHistory({
    required this.agentId,
    required this.userId,
    required this.versions,
    required this.activeVersion,
    required this.editCount,
    this.editsRemaining,
  });

  final String agentId;
  final String userId;
  final List<UserOverlay> versions;
  final int activeVersion;
  final int editCount;
  final int? editsRemaining;

  factory BriefHistory.fromJson(Map<String, dynamic> j) {
    final list = (j['versions'] as List<dynamic>?) ?? const [];
    return BriefHistory(
      agentId: j['agent_id'] as String,
      userId: j['user_id'] as String,
      versions: list
          .map((e) => UserOverlay.fromJson(e as Map<String, dynamic>))
          .toList(),
      activeVersion: ((j['active_version'] as num?) ?? 0).toInt(),
      editCount: ((j['edit_count'] as num?) ?? 0).toInt(),
      editsRemaining: j['edits_remaining'] == null
          ? null
          : ((j['edits_remaining'] as num).toInt()),
    );
  }
}
