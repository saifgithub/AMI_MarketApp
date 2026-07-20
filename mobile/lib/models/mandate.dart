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

/// Specific dollar/year target. Optional — only set for the "specific_goal" path.
class TargetOutcome {
  const TargetOutcome({
    required this.amount,
    this.currency = 'USD',
    required this.byYear,
  });

  final double amount;
  final String currency;
  final int byYear;

  factory TargetOutcome.fromJson(Map<String, dynamic> j) => TargetOutcome(
        amount: (j['amount'] as num).toDouble(),
        currency: j['currency'] as String? ?? 'USD',
        byYear: (j['by_year'] as num).toInt(),
      );

  Map<String, dynamic> toJson() => {
        'amount': amount,
        'currency': currency,
        'by_year': byYear,
      };
}

/// Granular risk profile (1-5 / -1..1 scales). Derived from the risk-scenario
/// questions during onboarding. Used by safety floor + drift detection.
class RiskComponents {
  const RiskComponents({
    required this.drawdownResponse,
    required this.regretAsymmetry,
    required this.concentrationTolerance,
  });

  /// 1 (panic) → 5 (hold steady).
  final int drawdownResponse;

  /// -1 (regret losses more) → 0 (neutral) → 1 (regret missed gains more).
  final int regretAsymmetry;

  /// 1 (diversified always) → 5 (high-conviction concentration ok).
  final int concentrationTolerance;

  factory RiskComponents.fromJson(Map<String, dynamic> j) => RiskComponents(
        drawdownResponse: (j['drawdown_response'] as num?)?.toInt() ?? 3,
        regretAsymmetry: (j['regret_asymmetry'] as num?)?.toInt() ?? 0,
        concentrationTolerance:
            (j['concentration_tolerance'] as num?)?.toInt() ?? 3,
      );

  Map<String, dynamic> toJson() => {
        'drawdown_response': drawdownResponse,
        'regret_asymmetry': regretAsymmetry,
        'concentration_tolerance': concentrationTolerance,
      };
}

/// Daily briefing preferences — time, channels, TTS voice.
class DailyBriefing {
  const DailyBriefing({
    this.enabled = false,
    this.timeLocal = '07:00',
    this.timezone = 'UTC',
    this.voiceId,
    this.deliveryChannels = const ['in_app'],
    this.language = 'en',
  });

  final bool enabled;
  final String timeLocal;
  final String timezone;
  final String? voiceId;
  final List<String> deliveryChannels; // push / in_app / email
  final String language;

  factory DailyBriefing.fromJson(Map<String, dynamic> j) => DailyBriefing(
        enabled: (j['enabled'] as bool?) ?? false,
        timeLocal: j['time_local'] as String? ?? '07:00',
        timezone: j['timezone'] as String? ?? 'UTC',
        voiceId: j['voice_id'] as String?,
        deliveryChannels:
            ((j['delivery_channels'] as List?) ?? const ['in_app']).cast<String>(),
        language: j['language'] as String? ?? 'en',
      );

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        'time_local': timeLocal,
        'timezone': timezone,
        if (voiceId != null) 'voice_id': voiceId,
        'delivery_channels': deliveryChannels,
        'language': language,
      };
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
    this.targetOutcome,
    required this.path,
    required this.riskScore,
    required this.riskComponents,
    this.riskQuotes = const [],
    required this.maxDrawdownPct,
    required this.learningStyle,
    required this.compliance,
    required this.dailyBriefing,
    required this.plan,
    this.trialExpiresAt,
    required this.creditBalance,
    this.creditAllowance = 0,
    this.roomCost = 0,
    this.creditsResetAt,
    this.roomCooldownUntil,
    this.createdAt,
    this.updatedAt,
  });

  final String userId;
  final int version;
  final String displayName;
  final String locale;
  final String timezone;
  final String primaryGoal;
  final String horizon;
  final TargetOutcome? targetOutcome;
  final String path;
  final int riskScore;
  final RiskComponents riskComponents;
  final List<String> riskQuotes;
  final int maxDrawdownPct;
  final String learningStyle;
  final ComplianceFlags compliance;
  final DailyBriefing dailyBriefing;
  final String plan;
  final DateTime? trialExpiresAt;
  final int creditBalance;
  // CR039/CR047 credit state (stamped by the mandate API from `users`).
  final int creditAllowance;
  final int roomCost;
  final DateTime? creditsResetAt;
  // CR047 "The Winzip": when set and in the future, the next Room convene is in
  // cooldown — the UI can pre-empt with the countdown card. NULL/past = clear.
  final DateTime? roomCooldownUntil;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  /// True when a Winzip cooldown is currently blocking a convene.
  bool get roomCooldownActive =>
      roomCooldownUntil != null && roomCooldownUntil!.isAfter(DateTime.now());

  factory UserMandate.fromJson(Map<String, dynamic> j) {
    return UserMandate(
      userId: j['user_id'] as String,
      version: (j['version'] as num?)?.toInt() ?? 1,
      displayName: (j['display_name'] as String?) ?? 'Trader',
      locale: (j['locale'] as String?) ?? 'en',
      timezone: (j['timezone'] as String?) ?? 'UTC',
      primaryGoal: j['primary_goal'] as String? ?? 'long_term_wealth',
      horizon: j['horizon'] as String? ?? 'long',
      targetOutcome: j['target_outcome'] != null
          ? TargetOutcome.fromJson(
              (j['target_outcome'] as Map).cast<String, dynamic>(),
            )
          : null,
      path: j['path'] as String? ?? 'long_horizon',
      riskScore: (j['risk_score'] as num?)?.toInt() ?? 3,
      riskComponents: RiskComponents.fromJson(
        (j['risk_components'] as Map?)?.cast<String, dynamic>() ?? const {},
      ),
      riskQuotes:
          ((j['risk_quotes'] as List?) ?? const []).cast<String>(),
      maxDrawdownPct: (j['max_drawdown_pct'] as num?)?.toInt() ?? 30,
      learningStyle: j['learning_style'] as String? ?? 'quick',
      compliance: ComplianceFlags.fromJson(
        (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {},
      ),
      dailyBriefing: DailyBriefing.fromJson(
        (j['daily_briefing'] as Map?)?.cast<String, dynamic>() ?? const {},
      ),
      plan: j['plan'] as String? ?? 'trial_trader',
      trialExpiresAt: j['trial_expires_at'] != null
          ? DateTime.parse(j['trial_expires_at'] as String)
          : null,
      creditBalance: (j['credit_balance'] as num?)?.toInt() ?? 75,
      creditAllowance: (j['credit_allowance'] as num?)?.toInt() ?? 0,
      roomCost: (j['room_cost'] as num?)?.toInt() ?? 0,
      creditsResetAt: j['credits_reset_at'] != null
          ? DateTime.parse(j['credits_reset_at'] as String).toLocal()
          : null,
      roomCooldownUntil: j['room_cooldown_until'] != null
          ? DateTime.parse(j['room_cooldown_until'] as String).toLocal()
          : null,
      createdAt: j['created_at'] != null
          ? DateTime.parse(j['created_at'] as String)
          : null,
      updatedAt: j['updated_at'] != null
          ? DateTime.parse(j['updated_at'] as String)
          : null,
    );
  }
}
