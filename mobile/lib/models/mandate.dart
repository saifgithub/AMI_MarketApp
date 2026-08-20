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

/// BL12 holdings-vs-mandate audit result. CR101-MOBILE calls this
/// immediately after a risk-limit PATCH to render the retro-tightening
/// disclosure — flag, never a forced sell (`GET /v1/mandate/{id}/audit`).
class HoldingsAuditResult {
  const HoldingsAuditResult({
    required this.passed,
    required this.mandateVersion,
    required this.maxOpenPositionsBreach,
    required this.maxOpenRiskPctBreach,
    required this.violationTickers,
  });

  final bool passed;
  final int mandateVersion;
  final bool maxOpenPositionsBreach;
  final bool maxOpenRiskPctBreach;
  final List<String> violationTickers;

  bool get anyRetroBreach => maxOpenPositionsBreach || maxOpenRiskPctBreach;

  factory HoldingsAuditResult.fromJson(Map<String, dynamic> j) {
    final violations = (j['violations'] as List? ?? const [])
        .cast<Map>()
        .map((v) => v['ticker'] as String? ?? '')
        .where((t) => t.isNotEmpty)
        .toList();
    return HoldingsAuditResult(
      passed: (j['passed'] as bool?) ?? true,
      mandateVersion: (j['mandate_version'] as num?)?.toInt() ?? 0,
      maxOpenPositionsBreach: (j['max_open_positions_breach'] as bool?) ?? false,
      maxOpenRiskPctBreach: (j['max_open_risk_pct_breach'] as bool?) ?? false,
      violationTickers: violations,
    );
  }
}

/// CR129 — the enforced value for each of the seven risk limits, resolved
/// server-side: the explicit override when one is set, else the risk-profile
/// preset. Stamped onto GET/PATCH /v1/mandate responses by the backend
/// (DEF193 + d1d4076d); never persisted, never computed client-side (CR046).
/// Every field is nullable because an installed build may talk to an older
/// backend: pre-DEF193 sends no `resolved` at all, and alpha-2026-08-19-2
/// carries only the two CR101-BE1 caps. A null field means UNKNOWN — the UI
/// falls back to no-number copy, it never fabricates a preset.
class ResolvedCaps {
  const ResolvedCaps({
    this.sectorCapPct,
    this.singleNameCapPct,
    this.maxOpenPositions,
    this.postLossCooldownHours,
    this.maxTradesPerDay,
    this.maxTradesPerWeek,
    this.maxOpenRiskPct,
  });

  final double? sectorCapPct;
  final double? singleNameCapPct;
  final int? maxOpenPositions;
  final double? postLossCooldownHours;
  final int? maxTradesPerDay;
  final int? maxTradesPerWeek;
  final double? maxOpenRiskPct;

  factory ResolvedCaps.fromJson(Map<String, dynamic> j) {
    return ResolvedCaps(
      sectorCapPct: (j['sector_cap_pct'] as num?)?.toDouble(),
      singleNameCapPct: (j['single_name_cap_pct'] as num?)?.toDouble(),
      maxOpenPositions: (j['max_open_positions'] as num?)?.toInt(),
      postLossCooldownHours:
          (j['post_loss_cooldown_hours'] as num?)?.toDouble(),
      maxTradesPerDay: (j['max_trades_per_day'] as num?)?.toInt(),
      maxTradesPerWeek: (j['max_trades_per_week'] as num?)?.toInt(),
      maxOpenRiskPct: (j['max_open_risk_pct'] as num?)?.toDouble(),
    );
  }

  /// The resolved value keyed by the backend PATCH field name — the Settings
  /// render path is key-driven (see `kRiskLimitFields`).
  num? valueFor(String key) {
    switch (key) {
      case 'sector_cap_pct':
        return sectorCapPct;
      case 'single_name_cap_pct':
        return singleNameCapPct;
      case 'max_open_positions':
        return maxOpenPositions;
      case 'post_loss_cooldown_hours':
        return postLossCooldownHours;
      case 'max_trades_per_day':
        return maxTradesPerDay;
      case 'max_trades_per_week':
        return maxTradesPerWeek;
      case 'max_open_risk_pct':
        return maxOpenRiskPct;
      default:
        return null;
    }
  }
}

/// CR129 items 2-3 — the Day Trader preset as the SERVER defines it, stamped
/// onto GET/PATCH /v1/mandate responses (568bd360). `overrides` is the exact
/// PATCH body that applies the preset — key = mandate field name, value = the
/// permissive setting. The picker PATCHes it back VERBATIM: the backend's
/// `is_day_trader_preset()` recognises that payload and journals the CR131
/// cohort marker, so the raw decoded nums are kept untouched — never rounded,
/// never re-typed, and never duplicated as client constants (the CR129-MOBILE
/// fence: "Do NOT hard-code any preset value or cap — server-sourced only").
/// `disclosure` is the selection-time dialog body, rendered verbatim.
class DayTraderPresetInfo {
  const DayTraderPresetInfo({required this.overrides, required this.disclosure});

  final Map<String, num> overrides;
  final String disclosure;

  factory DayTraderPresetInfo.fromJson(Map<String, dynamic> j) {
    return DayTraderPresetInfo(
      overrides: ((j['overrides'] as Map?) ?? const {})
          .map((k, v) => MapEntry(k as String, v as num)),
      disclosure: j['disclosure'] as String? ?? '',
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
    this.targetOutcome,
    required this.path,
    required this.riskScore,
    required this.riskComponents,
    this.riskQuotes = const [],
    required this.maxDrawdownPct,
    required this.learningStyle,
    required this.compliance,
    required this.plan,
    this.trialExpiresAt,
    required this.creditBalance,
    this.creditAllowance = 0,
    this.roomCost = 0,
    this.creditsResetAt,
    this.roomCooldownUntil,
    this.createdAt,
    this.updatedAt,
    this.sectorCapPct,
    this.singleNameCapPct,
    this.postLossCooldownHours,
    this.maxOpenPositions,
    this.maxTradesPerDay,
    this.maxTradesPerWeek,
    this.maxOpenRiskPct,
    this.resolved,
    this.dayTraderPreset,
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
  // The seven settable risk limits (CR101-BE1/BE2, semantics inverted by
  // CR129): `null` = no explicit override — the server enforces the
  // risk-profile preset for ALL seven, so `null` means "following your risk
  // profile", never "off". The number actually enforced arrives in
  // `resolved` below; it is never computed client-side (CR046).
  final double? sectorCapPct;
  final double? singleNameCapPct;
  final double? postLossCooldownHours;
  final int? maxOpenPositions;
  final int? maxTradesPerDay;
  final int? maxTradesPerWeek;
  final double? maxOpenRiskPct;

  // CR129: server-resolved enforced values for the seven limits above.
  // Null when the backend predates DEF193 — unknown, not "off".
  final ResolvedCaps? resolved;

  // CR129 items 2-3: the server-served Day Trader preset. Null when the
  // backend predates 568bd360 — UNKNOWN, so the Settings picker hides the
  // Day Trader entry entirely rather than approximating it client-side.
  final DayTraderPresetInfo? dayTraderPreset;
  final String learningStyle;
  final ComplianceFlags compliance;
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
      sectorCapPct: (j['sector_cap_pct'] as num?)?.toDouble(),
      singleNameCapPct: (j['single_name_cap_pct'] as num?)?.toDouble(),
      postLossCooldownHours: (j['post_loss_cooldown_hours'] as num?)?.toDouble(),
      maxOpenPositions: (j['max_open_positions'] as num?)?.toInt(),
      maxTradesPerDay: (j['max_trades_per_day'] as num?)?.toInt(),
      maxTradesPerWeek: (j['max_trades_per_week'] as num?)?.toInt(),
      maxOpenRiskPct: (j['max_open_risk_pct'] as num?)?.toDouble(),
      resolved: j['resolved'] != null
          ? ResolvedCaps.fromJson((j['resolved'] as Map).cast<String, dynamic>())
          : null,
      dayTraderPreset: j['day_trader_preset'] != null
          ? DayTraderPresetInfo.fromJson(
              (j['day_trader_preset'] as Map).cast<String, dynamic>(),
            )
          : null,
      learningStyle: j['learning_style'] as String? ?? 'quick',
      compliance: ComplianceFlags.fromJson(
        (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {},
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
