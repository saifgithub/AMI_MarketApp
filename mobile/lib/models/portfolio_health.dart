/// CR136 M09 — wire models for GET /v1/portfolio/health (M04 envelope + M07 gate) and POST .../finding. Parses; never computes a metric.
///
/// Every number here was computed, bounded and unit-pinned by the backend
/// engine. The client's whole job is to read the block, scale it by the unit
/// the backend declared, and print it. It derives exactly two things — bar
/// geometry fractions and the CTA enum — and neither is a metric.
///
/// The unit map below mirrors the backend's `METRIC_VALUE_UNIT`
/// (`app/services/portfolio_health_constants.py`) rather than guessing from a
/// metric's name. That guess is what M06's audit caught printing "1969.00%"
/// for a 19.69% drawdown: Tier-1 values are decimal fractions and want ×100,
/// Tier-2 `realised_*` values are already percent and must never be scaled,
/// and a ratio like beta takes no percent sign at all. An unpinned metric id
/// throws rather than picking a scale.
library;

/// How a block's `value`/`standard_error` are already expressed on the wire.
enum HealthMetricUnit {
  /// Decimal fraction — multiply by 100 to show a percentage (Tier 1).
  fraction,

  /// Already a percentage (Tier 2 `realised_*`, M03 §3.5).
  percent,

  /// Dimensionless — beta, effective bets, HHI. Never carries a percent sign.
  ratio,
}

/// Stamped when the payload carries no `metrics` object at all. Not a backend
/// status — it exists so an unrecognised envelope lands in the card's
/// unknown-status branch rather than the populated one (M09 audit m1).
const String kUnrecognisedEnvelopeStatus = 'unrecognised_envelope';

/// Mirrors backend `METRIC_VALUE_UNIT`. Keep the two in step; a metric present
/// there and absent here throws at render time rather than being scaled wrong.
/// Drift in the other direction — a metric pinned to the WRONG unit — throws
/// nothing here and is caught by `backend/tests/unit/test_cr136_dart_parity.py`.
const Map<String, HealthMetricUnit> kMetricValueUnit = {
  'portfolio_volatility': HealthMetricUnit.fraction,
  'beta': HealthMetricUnit.ratio,
  'tracking_error': HealthMetricUnit.fraction,
  'effective_bets': HealthMetricUnit.ratio,
  'risk_contribution': HealthMetricUnit.fraction,
  'mcr': HealthMetricUnit.fraction,
  'weight_concentration': HealthMetricUnit.ratio,
  'typical_bad_month': HealthMetricUnit.fraction,
  'scenario_panel': HealthMetricUnit.fraction,
  'realised_max_drawdown': HealthMetricUnit.percent,
  'realised_return': HealthMetricUnit.percent,
};

/// Mirrors the backend's `INSUFFICIENT_*` constants
/// (`app/services/portfolio_health_constants.py`). Every branch in the card
/// that names a cause names it through one of these rather than through a bare
/// literal, so a backend rename fails `test_cr136_dart_parity.py` instead of
/// silently deleting the note that cause was supposed to carry.
const String kCauseShortWindow = 'short_window';
const String kCauseTOverN = 't_over_n';
const String kCauseBenchmarkMisaligned = 'benchmark_misaligned';
const String kCauseDroppedWeight = 'dropped_weight_exceeded';
const String kCauseFeedUnavailable = 'feed_unavailable';
const String kCauseZeroVariance = 'zero_variance';
const String kCauseSparseGrid = 'sparse_grid';

/// The closed set, compared as a SET against the backend's own `INSUFFICIENT_*`
/// constants. This is the DEF210 shape's second occurrence: the enum widened
/// 4 → 6 during CR136 with nothing holding the two sides together. Widening it
/// again now fails on the backend side the day it happens, rather than the day
/// a reader notices a tile is missing (M04 audit r1, MAJOR M1). It did: DEF213's
/// guard minted `sparse_grid` as the seventh cause and this test failed on that
/// commit, before the card had ever seen the value.
const Set<String> kInsufficientCauses = {
  kCauseShortWindow,
  kCauseTOverN,
  kCauseBenchmarkMisaligned,
  kCauseDroppedWeight,
  kCauseFeedUnavailable,
  kCauseZeroVariance,
  kCauseSparseGrid,
};

/// M07 §3.2's gate status — exactly the eight keys `GateStatus.as_dict()` ships.
class HealthGateStatus {
  const HealthGateStatus({
    required this.mode,
    required this.trialActive,
    required this.trialFindingsUsed,
    required this.trialFindingsBudget,
    required this.trialDaysLeft,
    required this.dailyUsed,
    required this.dailyCap,
    required this.planHasAccess,
  });

  /// "open" | "trial" | "plan".
  final String mode;
  final bool trialActive;
  final int trialFindingsUsed;
  final int trialFindingsBudget;
  final int trialDaysLeft;
  final int dailyUsed;
  final int dailyCap;
  final bool planHasAccess;

  /// The shape the client falls back to when the envelope carries no `gate` at
  /// all — a wire divergence, not a normal state. Deliberately the most
  /// closed reading (`plan` mode, no access), because the alternative invents
  /// an entitlement the server has not granted. The tiles are free and still
  /// render; the POST remains the authority and answers 402/429 on its own.
  static const closed = HealthGateStatus(
    mode: 'plan',
    trialActive: false,
    trialFindingsUsed: 0,
    trialFindingsBudget: 0,
    trialDaysLeft: 0,
    dailyUsed: 0,
    dailyCap: 0,
    planHasAccess: false,
  );

  factory HealthGateStatus.fromJson(Map<String, dynamic> j) => HealthGateStatus(
        mode: j['mode'] as String? ?? 'plan',
        trialActive: j['trial_active'] as bool? ?? false,
        trialFindingsUsed: (j['trial_findings_used'] as num?)?.toInt() ?? 0,
        trialFindingsBudget: (j['trial_findings_budget'] as num?)?.toInt() ?? 0,
        trialDaysLeft: (j['trial_days_left'] as num?)?.toInt() ?? 0,
        dailyUsed: (j['daily_used'] as num?)?.toInt() ?? 0,
        dailyCap: (j['daily_cap'] as num?)?.toInt() ?? 0,
        planHasAccess: j['plan_has_access'] as bool? ?? false,
      );
}

/// One metric block in Rev 4's uncertainty contract (README contract 1).
///
/// `sufficient: false` arrives with `value` and `standardError` null — never
/// 0.0 — so "we could not measure this" and "we measured zero" stay different
/// answers all the way to the screen.
class HealthMetricBlock {
  const HealthMetricBlock({
    required this.metric,
    required this.basis,
    required this.engineVersion,
    required this.value,
    required this.standardError,
    required this.tEff,
    required this.nObservations,
    required this.windowDays,
    required this.sufficient,
    required this.partial,
    required this.containsEtfs,
    required this.backcast,
    required this.droppedHoldings,
    required this.lowExplanatoryPower,
    required this.insufficientCause,
    required this.extensions,
  });

  final String metric;
  final String basis;
  final String engineVersion;

  /// Null ⇔ insufficient, or null by engine decision (SEs on derived blocks).
  final double? value;
  final double? standardError;
  final double? tEff;

  final int nObservations;
  final int windowDays;
  final bool sufficient;
  final bool partial;
  final bool containsEtfs;
  final bool backcast;

  /// `[{ticker, reason}]`.
  final List<Map<String, dynamic>> droppedHoldings;

  /// Non-null on `beta` only.
  final bool? lowExplanatoryPower;

  /// short_window | t_over_n | benchmark_misaligned | dropped_weight_exceeded
  /// | zero_variance | feed_unavailable. Null when sufficient.
  final String? insufficientCause;

  /// Per-metric extras the engine attaches: `r_squared`, `per_holding`, `top`,
  /// `per_sector`, `effective_n`, `holdings_count`, `episodes`.
  final Map<String, dynamic> extensions;

  static const _known = {
    'metric',
    'value',
    'standard_error',
    'n_observations',
    't_eff',
    'window_days',
    'sufficient',
    'partial',
    'dropped_holdings',
    'low_explanatory_power',
    'contains_etfs',
    'backcast',
    'basis',
    'engine_version',
    'insufficient_cause',
  };

  /// The block's declared unit. Throws on a metric absent from
  /// [kMetricValueUnit] — the wrong scale is a silently wrong number on
  /// screen, and this is the one place the client can still refuse to guess.
  HealthMetricUnit get unit {
    final u = kMetricValueUnit[metric];
    if (u == null) {
      throw StateError(
        'CR136: no pinned unit for metric "$metric" — kMetricValueUnit must '
        'mirror the backend METRIC_VALUE_UNIT map before this can render',
      );
    }
    return u;
  }

  /// [value] as a percentage, honouring the pinned unit. Null when the block
  /// carries no value. Throws for a `ratio` metric, which has no percent
  /// reading at all.
  double? get valuePercent {
    if (value == null) return null;
    switch (unit) {
      case HealthMetricUnit.fraction:
        return value! * 100.0;
      case HealthMetricUnit.percent:
        return value!;
      case HealthMetricUnit.ratio:
        throw StateError('CR136: "$metric" is a ratio — it has no percent form');
    }
  }

  factory HealthMetricBlock.fromJson(Map<String, dynamic> j) {
    final extensions = <String, dynamic>{
      for (final e in j.entries)
        if (!_known.contains(e.key)) e.key: e.value,
    };
    return HealthMetricBlock(
      metric: j['metric'] as String? ?? '',
      basis: j['basis'] as String? ?? '',
      engineVersion: j['engine_version'] as String? ?? '',
      value: (j['value'] as num?)?.toDouble(),
      standardError: (j['standard_error'] as num?)?.toDouble(),
      tEff: (j['t_eff'] as num?)?.toDouble(),
      nObservations: (j['n_observations'] as num?)?.toInt() ?? 0,
      windowDays: (j['window_days'] as num?)?.toInt() ?? 0,
      sufficient: j['sufficient'] as bool? ?? false,
      partial: j['partial'] as bool? ?? false,
      containsEtfs: j['contains_etfs'] as bool? ?? false,
      backcast: j['backcast'] as bool? ?? false,
      droppedHoldings: _mapList(j['dropped_holdings']),
      lowExplanatoryPower: j['low_explanatory_power'] as bool?,
      insufficientCause: j['insufficient_cause'] as String?,
      extensions: extensions,
    );
  }
}

List<Map<String, dynamic>> _mapList(Object? raw) => raw is List
    ? raw
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList(growable: false)
    : const [];

/// The GET envelope: M07 §3.4 wrapping M04 §3.5's engine payload.
class PortfolioHealth {
  const PortfolioHealth({
    required this.status,
    required this.asOf,
    required this.generatedAt,
    required this.engineVersion,
    required this.containsEtfs,
    required this.partial,
    required this.droppedHoldings,
    required this.holdingsCount,
    required this.riskyHoldingsCount,
    required this.totalValue,
    required this.investedValue,
    required this.coveredInvestedValue,
    required this.cashFraction,
    required this.benchmarkVolAnn,
    required this.blocks,
    required this.gate,
  });

  /// "ok" | "refused_mock_data" | "no_holdings".
  final String status;

  /// Null on the refusal shape, which never reached a trading day.
  final String? asOf;
  final String generatedAt;
  final String engineVersion;

  final bool containsEtfs;
  final bool partial;
  final List<Map<String, dynamic>> droppedHoldings;
  final int holdingsCount;
  final int riskyHoldingsCount;
  final double totalValue;
  final double investedValue;
  final double coveredInvestedValue;

  /// Cash as a fraction of the TOTAL book (LEVEL basis).
  final double cashFraction;

  /// `context.benchmark_vol_ann`, a decimal fraction. Null ⇒ no comparison line.
  final double? benchmarkVolAnn;

  final Map<String, HealthMetricBlock> blocks;
  final HealthGateStatus gate;

  bool get isOk => status == 'ok';

  HealthMetricBlock? block(String metric) => blocks[metric];

  factory PortfolioHealth.fromJson(Map<String, dynamic> json) {
    // M07 nests the engine payload under `metrics` and hoists status/as_of/
    // generated_at/engine_version to the root.
    //
    // AT:R66 — CR136-M09 audit round 1, MINOR m1. This used to read the ROOT as
    // a fallback, justified as forward-compatibility. There is no second shape
    // to be compatible with: M07 returns through one path, `_health_envelope`,
    // which always nests under `metrics`. Worse, it defended by GUESSING — on a
    // `metrics`-less payload `status` still hoisted to `ok` from the root, so
    // the card took the POPULATED branch with zero blocks and routed around the
    // unknown-status guard this model added for precisely that class. An
    // envelope we do not recognise now surfaces as one.
    final metricsRaw = json['metrics'];
    final m = (metricsRaw as Map?)?.cast<String, dynamic>()
        ?? const <String, dynamic>{};
    final context = (m['context'] as Map?)?.cast<String, dynamic>() ?? const {};
    final rawBlocks = (m['blocks'] as Map?)?.cast<String, dynamic>() ?? const {};
    final gateJson =
        (json['gate'] as Map?)?.cast<String, dynamic>() ??
            (m['gate'] as Map?)?.cast<String, dynamic>();

    return PortfolioHealth(
      status: metricsRaw is Map
          ? ((json['status'] ?? m['status']) as String? ?? '')
          : kUnrecognisedEnvelopeStatus,
      asOf: (json['as_of'] ?? m['as_of']) as String?,
      generatedAt: (json['generated_at'] ?? m['generated_at']) as String? ?? '',
      engineVersion:
          (json['engine_version'] ?? m['engine_version']) as String? ?? '',
      containsEtfs: m['contains_etfs'] as bool? ?? false,
      partial: m['partial'] as bool? ?? false,
      droppedHoldings: _mapList(m['dropped_holdings']),
      holdingsCount: (m['holdings_count'] as num?)?.toInt() ?? 0,
      riskyHoldingsCount: (m['risky_holdings_count'] as num?)?.toInt() ?? 0,
      totalValue: (m['total_value'] as num?)?.toDouble() ?? 0.0,
      investedValue: (m['invested_value'] as num?)?.toDouble() ?? 0.0,
      coveredInvestedValue:
          (m['covered_invested_value'] as num?)?.toDouble() ?? 0.0,
      cashFraction: (m['cash_fraction'] as num?)?.toDouble() ?? 0.0,
      benchmarkVolAnn: (context['benchmark_vol_ann'] as num?)?.toDouble(),
      blocks: {
        for (final e in rawBlocks.entries)
          if (e.value is Map)
            e.key: HealthMetricBlock.fromJson(
              Map<String, dynamic>.from(e.value as Map),
            ),
      },
      gate: gateJson == null
          ? HealthGateStatus.closed
          : HealthGateStatus.fromJson(gateJson),
    );
  }
}

/// The POST envelope: M07 §3.5. `sections` is the STORED report — the client
/// renders it verbatim and regenerates nothing (README contract 5).
class HealthFinding {
  const HealthFinding({
    required this.journalEntryId,
    required this.created,
    required this.asOf,
    required this.sections,
    required this.gate,
  });

  final String journalEntryId;

  /// False when today's Finding already existed — the idempotent replay, which
  /// costs no budget.
  final bool created;
  final String asOf;

  /// `head`, `f1`…`f5`.
  final Map<String, String> sections;
  final HealthGateStatus gate;

  factory HealthFinding.fromJson(Map<String, dynamic> j) {
    final raw = (j['sections'] as Map?)?.cast<String, dynamic>() ?? const {};
    return HealthFinding(
      journalEntryId: j['journal_entry_id'] as String? ?? '',
      created: j['created'] as bool? ?? false,
      asOf: j['as_of'] as String? ?? '',
      sections: {
        for (final e in raw.entries)
          if (e.value is String) e.key: e.value as String,
      },
      gate: HealthGateStatus.fromJson(
        (j['gate'] as Map?)?.cast<String, dynamic>() ?? const {},
      ),
    );
  }
}
