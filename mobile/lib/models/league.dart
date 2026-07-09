/// CR010 (B2/B5) — league + streak models mirroring the untyped `/v1/league/*`
/// JSON. The backend serialises raw dicts (no response_model), so keys are
/// snake_case and there are no aliases. Nullable-tolerant parsing throughout.
library;

class StreakInfo {
  const StreakInfo({
    required this.current,
    required this.longest,
    this.nextMilestone,
  });

  final int current;
  final int longest;
  final int? nextMilestone;

  factory StreakInfo.fromJson(Map<String, dynamic> j) => StreakInfo(
        current: (j['current'] as num?)?.toInt() ?? 0,
        longest: (j['longest'] as num?)?.toInt() ?? 0,
        nextMilestone: (j['next_milestone'] as num?)?.toInt(),
      );
}

/// `GET /v1/league/me` — the caller's league standing + streak. The route
/// mints a pseudonymous handle on first call, so `handle` is always present.
class LeagueMe {
  const LeagueMe({
    required this.handle,
    required this.tier,
    required this.reputation,
    required this.pointsThisWeek,
    required this.rank,
    required this.showDisplayName,
    required this.streak,
  });

  final String handle;
  final String tier;
  final int reputation;
  final int pointsThisWeek;
  final int? rank; // null when unassigned this week
  final bool showDisplayName;
  final StreakInfo streak;

  factory LeagueMe.fromJson(Map<String, dynamic> j) => LeagueMe(
        handle: j['handle'] as String? ?? '—',
        tier: j['tier'] as String? ?? 'apprentice',
        reputation: (j['reputation'] as num?)?.toInt() ?? 0,
        pointsThisWeek: (j['points_this_week'] as num?)?.toInt() ?? 0,
        rank: (j['rank'] as num?)?.toInt(),
        showDisplayName: j['show_display_name'] as bool? ?? false,
        streak: StreakInfo.fromJson(
          (j['streak'] as Map<String, dynamic>?) ?? const {},
        ),
      );
}

class LeagueMemberRow {
  const LeagueMemberRow({
    required this.rank,
    required this.userId,
    required this.handle,
    required this.displayName,
    required this.points,
    required this.isMe,
  });

  final int rank;
  final String userId;
  final String handle;
  final String? displayName; // non-null only when that member opted in
  final int points;
  final bool isMe;

  factory LeagueMemberRow.fromJson(Map<String, dynamic> j) => LeagueMemberRow(
        rank: (j['rank'] as num?)?.toInt() ?? 0,
        userId: j['user_id'] as String? ?? '',
        handle: j['handle'] as String? ?? '—',
        displayName: j['display_name'] as String?,
        points: (j['points'] as num?)?.toInt() ?? 0,
        isMe: j['is_me'] as bool? ?? false,
      );
}

/// `GET /v1/league/standings` — the caller's current-week cohort board.
class LeagueStandings {
  const LeagueStandings({
    required this.leagueId,
    required this.week,
    required this.tier,
    required this.endsAt,
    required this.members,
  });

  final String leagueId;
  final String week;
  final String tier;
  final String endsAt; // ISO 8601
  final List<LeagueMemberRow> members;

  factory LeagueStandings.fromJson(Map<String, dynamic> j) => LeagueStandings(
        leagueId: j['league_id'] as String? ?? '',
        week: j['week'] as String? ?? '',
        tier: j['tier'] as String? ?? 'apprentice',
        endsAt: j['ends_at'] as String? ?? '',
        members: ((j['members'] as List<dynamic>?) ?? const [])
            .map((e) => LeagueMemberRow.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// `GET /v1/league/history` — one row per finalised past week.
class LeagueHistoryEntry {
  const LeagueHistoryEntry({
    required this.week,
    required this.tier,
    required this.rankFinal,
    required this.outcome,
    required this.points,
  });

  final String week;
  final String tier;
  final int rankFinal;
  final String? outcome; // "promoted" | "relegated" | "stay"
  final int points;

  factory LeagueHistoryEntry.fromJson(Map<String, dynamic> j) =>
      LeagueHistoryEntry(
        week: j['week'] as String? ?? '',
        tier: j['tier'] as String? ?? 'apprentice',
        rankFinal: (j['rank_final'] as num?)?.toInt() ?? 0,
        outcome: j['outcome'] as String?,
        points: (j['points'] as num?)?.toInt() ?? 0,
      );
}
