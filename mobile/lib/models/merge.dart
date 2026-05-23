/// BL16 (AT:R38) account-merge data models — mirror app/schemas/auth.py
/// MergePreview + MergeResult shapes.
///
/// Drives the merge-sheet UX that fires after [SignInScreen] detects an
/// adoption (AuthVerifyResponse.adoptedFromUserId != null). The user sees
/// the preview counts, chooses [MERGE EVERYTHING] or [KEEP SEPARATE],
/// and on confirm the orphan rows get re-keyed server-side.
library;

class MergePreview {
  MergePreview({
    required this.fromUserId,
    required this.toUserId,
    required this.journalEntries,
    required this.simTrades,
    required this.simHoldings,
    required this.simWatchlists,
    required this.lessonsProgress,
    required this.agentActivations,
    required this.oneOnOneMessages,
    required this.roomRuns,
    required this.userOverlays,
    required this.bugReports,
    required this.mandateConflict,
  });

  final String fromUserId;
  final String toUserId;
  final int journalEntries;
  final int simTrades;
  final int simHoldings;
  final int simWatchlists;
  final int lessonsProgress;
  final int agentActivations;
  final int oneOnOneMessages;
  final int roomRuns;
  final int userOverlays;
  final int bugReports;
  final bool mandateConflict;

  /// True when the orphan side has nothing worth surfacing to the user.
  /// The sheet falls back to a tighter "keep separate / sign in anyway"
  /// flow in that case.
  bool get isEmpty =>
      journalEntries == 0 &&
      simTrades == 0 &&
      simWatchlists == 0 &&
      lessonsProgress == 0 &&
      agentActivations == 0 &&
      oneOnOneMessages == 0 &&
      roomRuns == 0 &&
      userOverlays == 0 &&
      bugReports == 0 &&
      !mandateConflict;

  factory MergePreview.fromJson(Map<String, dynamic> j) => MergePreview(
        fromUserId: j['from_user_id'] as String,
        toUserId: j['to_user_id'] as String,
        journalEntries: (j['journal_entries'] as num?)?.toInt() ?? 0,
        simTrades: (j['sim_trades'] as num?)?.toInt() ?? 0,
        simHoldings: (j['sim_holdings'] as num?)?.toInt() ?? 0,
        simWatchlists: (j['sim_watchlists'] as num?)?.toInt() ?? 0,
        lessonsProgress: (j['lessons_progress'] as num?)?.toInt() ?? 0,
        agentActivations: (j['agent_activations'] as num?)?.toInt() ?? 0,
        oneOnOneMessages: (j['one_on_one_messages'] as num?)?.toInt() ?? 0,
        roomRuns: (j['room_runs'] as num?)?.toInt() ?? 0,
        userOverlays: (j['user_overlays'] as num?)?.toInt() ?? 0,
        bugReports: (j['bug_reports'] as num?)?.toInt() ?? 0,
        mandateConflict: j['mandate_conflict'] as bool? ?? false,
      );
}

class MergeResult {
  MergeResult({
    required this.fromUserId,
    required this.toUserId,
    required this.counts,
    required this.mandateKept,
    required this.overlaysDeactivated,
  });

  final String fromUserId;
  final String toUserId;

  /// Per-category re-keyed row counts, keyed by backend table name
  /// (e.g. "journal_entries", "sim_trades", "lessons_progress").
  final Map<String, int> counts;

  /// Which side's mandate won when both had one: "target" / "source" /
  /// "neither".
  final String mandateKept;

  /// Source overlays that got re-keyed but flipped to is_active=false
  /// because the target already had an active overlay for the same agent.
  final int overlaysDeactivated;

  int get totalRowsMoved => counts.values.fold(0, (a, b) => a + b);

  factory MergeResult.fromJson(Map<String, dynamic> j) {
    final raw = (j['counts'] as Map?) ?? const {};
    final counts = <String, int>{};
    raw.forEach((k, v) {
      if (v is num) counts[k.toString()] = v.toInt();
    });
    return MergeResult(
      fromUserId: j['from_user_id'] as String,
      toUserId: j['to_user_id'] as String,
      counts: counts,
      mandateKept: j['mandate_kept'] as String? ?? 'neither',
      overlaysDeactivated:
          (j['overlays_deactivated'] as num?)?.toInt() ?? 0,
    );
  }
}
