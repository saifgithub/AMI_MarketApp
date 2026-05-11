/// User Mandate — client model (just the editable surface for Settings).
/// Mirrors backend/app/schemas/mandate.py.
library;

class ComplianceFlags {
  const ComplianceFlags({
    this.halal = false,
    this.esgLite = false,
    this.noTobaccoAlcoholGambling = false,
    this.noFossilFuels = false,
    this.longOnly = true,
    this.liquidOnly = true,
    this.tickerBlocklist = const [],
    this.tickerAllowlist,
    this.customConstraints = const [],
  });

  final bool halal;
  final bool esgLite;
  final bool noTobaccoAlcoholGambling;
  final bool noFossilFuels;
  final bool longOnly;
  final bool liquidOnly;
  final List<String> tickerBlocklist;
  final List<String>? tickerAllowlist;
  final List<String> customConstraints;

  ComplianceFlags copyWith({
    bool? halal,
    bool? esgLite,
    bool? noTobaccoAlcoholGambling,
    bool? noFossilFuels,
    bool? longOnly,
    bool? liquidOnly,
    List<String>? tickerBlocklist,
    List<String>? tickerAllowlist,
    bool clearAllowlist = false,
  }) {
    return ComplianceFlags(
      halal: halal ?? this.halal,
      esgLite: esgLite ?? this.esgLite,
      noTobaccoAlcoholGambling:
          noTobaccoAlcoholGambling ?? this.noTobaccoAlcoholGambling,
      noFossilFuels: noFossilFuels ?? this.noFossilFuels,
      longOnly: longOnly ?? this.longOnly,
      liquidOnly: liquidOnly ?? this.liquidOnly,
      tickerBlocklist: tickerBlocklist ?? this.tickerBlocklist,
      tickerAllowlist: clearAllowlist ? null : (tickerAllowlist ?? this.tickerAllowlist),
      customConstraints: customConstraints,
    );
  }

  Map<String, dynamic> toPatchJson() => {
        'halal': halal,
        'esg_lite': esgLite,
        'no_tobacco_alcohol_gambling': noTobaccoAlcoholGambling,
        'no_fossil_fuels': noFossilFuels,
        'long_only': longOnly,
        'liquid_only': liquidOnly,
        'ticker_blocklist': tickerBlocklist,
        if (tickerAllowlist != null) 'ticker_allowlist': tickerAllowlist,
      };

  factory ComplianceFlags.fromJson(Map<String, dynamic> j) {
    return ComplianceFlags(
      halal: (j['halal'] as bool?) ?? false,
      esgLite: (j['esg_lite'] as bool?) ?? false,
      noTobaccoAlcoholGambling: (j['no_tobacco_alcohol_gambling'] as bool?) ?? false,
      noFossilFuels: (j['no_fossil_fuels'] as bool?) ?? false,
      longOnly: (j['long_only'] as bool?) ?? true,
      liquidOnly: (j['liquid_only'] as bool?) ?? true,
      tickerBlocklist: ((j['ticker_blocklist'] as List?) ?? const []).cast<String>(),
      tickerAllowlist: (j['ticker_allowlist'] as List?)?.cast<String>(),
    );
  }
}

class UserMandate {
  const UserMandate({
    required this.userId,
    required this.version,
    required this.displayName,
    required this.locale,
    required this.timezone,
    required this.primaryGoal,
    required this.horizon,
    required this.path,
    required this.riskScore,
    required this.maxDrawdownPct,
    required this.learningStyle,
    required this.compliance,
    required this.plan,
    required this.creditBalance,
  });

  final String userId;
  final int version;
  final String displayName;
  final String locale;
  final String timezone;
  final String primaryGoal;
  final String horizon;
  final String path;
  final int riskScore;
  final int maxDrawdownPct;
  final String learningStyle;
  final ComplianceFlags compliance;
  final String plan;
  final int creditBalance;

  factory UserMandate.fromJson(Map<String, dynamic> j) {
    return UserMandate(
      userId: j['user_id'] as String,
      version: (j['version'] as num?)?.toInt() ?? 1,
      displayName: (j['display_name'] as String?) ?? 'Trader',
      locale: (j['locale'] as String?) ?? 'en',
      timezone: (j['timezone'] as String?) ?? 'UTC',
      primaryGoal: j['primary_goal'] as String? ?? 'long_term_wealth',
      horizon: j['horizon'] as String? ?? 'long',
      path: j['path'] as String? ?? 'long_horizon',
      riskScore: (j['risk_score'] as num?)?.toInt() ?? 3,
      maxDrawdownPct: (j['max_drawdown_pct'] as num?)?.toInt() ?? 30,
      learningStyle: j['learning_style'] as String? ?? 'quick',
      compliance: ComplianceFlags.fromJson(
        (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {},
      ),
      plan: j['plan'] as String? ?? 'trial_trader',
      creditBalance: (j['credit_balance'] as num?)?.toInt() ?? 75,
    );
  }
}
