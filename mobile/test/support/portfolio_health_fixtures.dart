// CR136 M09 — one place that spells the GET/POST envelopes for tests.
//
// Shared rather than per-file because CR120's Positions-tab scroll budget also
// has to pump this card, and two hand-written copies of the envelope would
// drift apart exactly when a wire change made it matter. The shapes here mirror
// `_health_envelope` / `_finding_envelope` in `backend/app/api/portfolio.py`
// and `_block` in `portfolio_health.py`.

import 'package:ami_trade/models/portfolio_health.dart';

Map<String, dynamic> gateJson({
  String mode = 'plan',
  bool trialActive = false,
  int trialFindingsUsed = 0,
  int trialFindingsBudget = 7,
  int trialDaysLeft = 0,
  int dailyUsed = 0,
  int dailyCap = 2,
  bool planHasAccess = true,
}) =>
    {
      'mode': mode,
      'trial_active': trialActive,
      'trial_findings_used': trialFindingsUsed,
      'trial_findings_budget': trialFindingsBudget,
      'trial_days_left': trialDaysLeft,
      'daily_used': dailyUsed,
      'daily_cap': dailyCap,
      'plan_has_access': planHasAccess,
    };

Map<String, dynamic> blockJson(
  String metric, {
  double? value,
  double? standardError,
  bool sufficient = true,
  String? insufficientCause,
  int nObservations = 200,
  int windowDays = 288,
  double? tEff,
  String basis = 'total_value',
  bool partial = false,
  bool containsEtfs = false,
  bool backcast = true,
  bool? lowExplanatoryPower,
  List<Map<String, dynamic>> droppedHoldings = const [],
  Map<String, dynamic> extensions = const {},
}) =>
    {
      'metric': metric,
      // The engine forces these to null when insufficient; the fixture does the
      // same so a test can never assert on a value the wire cannot carry.
      'value': sufficient ? value : null,
      'standard_error': sufficient ? standardError : null,
      't_eff': sufficient ? (tEff ?? 66.0) : null,
      'n_observations': nObservations,
      'window_days': windowDays,
      'sufficient': sufficient,
      'partial': partial,
      'dropped_holdings': droppedHoldings,
      'low_explanatory_power': lowExplanatoryPower,
      'contains_etfs': containsEtfs,
      'backcast': backcast,
      'basis': basis,
      'engine_version': 'cr136.v1',
      'insufficient_cause': sufficient ? null : insufficientCause,
      ...extensions,
    };

/// The four blocks a populated card needs, plus the always-present accounting
/// block. Override any of them through [blocks].
Map<String, dynamic> healthJson({
  String status = 'ok',
  String? asOf = '2026-08-02',
  Map<String, dynamic>? blocks,
  Map<String, dynamic>? gate,
  bool partial = false,
  List<Map<String, dynamic>> droppedHoldings = const [],
  int holdingsCount = 6,
  int riskyHoldingsCount = 6,
  double totalValue = 120000,
  double investedValue = 100000,
  double coveredInvestedValue = 100000,
  double cashFraction = 0.1667,
  double? benchmarkVolAnn = 0.1510,
  bool nested = true,
}) {
  final metrics = <String, dynamic>{
    'status': status,
    'as_of': asOf,
    'generated_at': '2026-08-02T09:00:00+00:00',
    'engine_version': 'cr136.v1',
    'benchmark': 'SPY',
    'contains_etfs': false,
    'partial': partial,
    'dropped_holdings': droppedHoldings,
    'holdings_count': holdingsCount,
    'risky_holdings_count': riskyHoldingsCount,
    'total_value': totalValue,
    'invested_value': investedValue,
    'covered_invested_value': coveredInvestedValue,
    'cash_fraction': cashFraction,
    'context': {
      'benchmark_vol_ann': benchmarkVolAnn,
      'correlation_pairs': const [],
    },
    'blocks': blocks ?? defaultBlocks(),
  };
  final envelope = <String, dynamic>{
    'status': status,
    'as_of': asOf,
    'generated_at': metrics['generated_at'],
    'engine_version': 'cr136.v1',
    'gate': gate ?? gateJson(),
    if (nested) 'metrics': metrics,
  };
  return nested ? envelope : {...metrics, ...envelope};
}

Map<String, dynamic> defaultBlocks() => {
      'portfolio_volatility': blockJson(
        'portfolio_volatility',
        value: 0.1898,
        standardError: 0.0165,
      ),
      'beta': blockJson(
        'beta',
        value: 1.07,
        standardError: 0.09,
        lowExplanatoryPower: false,
        extensions: {'r_squared': 0.61},
      ),
      'effective_bets': blockJson(
        'effective_bets',
        value: 2.4,
        basis: 'invested_sleeve',
      ),
      'risk_contribution': blockJson(
        'risk_contribution',
        value: 0.412,
        basis: 'invested_sleeve',
        extensions: {
          'per_holding': [
            {'ticker': 'NVDA', 'invested_weight': 0.30, 'risk_share': 0.412},
            {'ticker': 'AAPL', 'invested_weight': 0.25, 'risk_share': 0.281},
            {'ticker': 'MSFT', 'invested_weight': 0.20, 'risk_share': 0.190},
            {'ticker': 'KO', 'invested_weight': 0.25, 'risk_share': 0.117},
          ],
          'top': {
            'ticker': 'NVDA',
            'risk_share': 0.412,
            'invested_weight': 0.30,
          },
        },
      ),
      'weight_concentration': blockJson(
        'weight_concentration',
        value: 0.2650,
        basis: 'weights',
        backcast: false,
        extensions: {'effective_n': 3.8, 'holdings_count': 6},
      ),
    };

/// Every core block insufficient — the card's "not enough history" state.
Map<String, dynamic> insufficientBlocks({
  String cause = 'short_window',
  int nObservations = 47,
  int windowDays = 288,
}) =>
    {
      for (final m in const [
        'portfolio_volatility',
        'beta',
        'effective_bets',
        'risk_contribution',
      ])
        m: blockJson(
          m,
          sufficient: false,
          insufficientCause: cause,
          nObservations: nObservations,
          windowDays: windowDays,
        ),
      'weight_concentration': blockJson(
        'weight_concentration',
        value: 0.2650,
        basis: 'weights',
        backcast: false,
        nObservations: nObservations,
        windowDays: windowDays,
        extensions: {'effective_n': 3.8, 'holdings_count': 6},
      ),
    };

PortfolioHealth healthFixture({
  String status = 'ok',
  String? asOf = '2026-08-02',
  Map<String, dynamic>? blocks,
  Map<String, dynamic>? gate,
  bool partial = false,
  List<Map<String, dynamic>> droppedHoldings = const [],
  int holdingsCount = 6,
  int riskyHoldingsCount = 6,
  double totalValue = 120000,
  double investedValue = 100000,
  double coveredInvestedValue = 100000,
  double cashFraction = 0.1667,
  double? benchmarkVolAnn = 0.1510,
}) =>
    PortfolioHealth.fromJson(healthJson(
      status: status,
      asOf: asOf,
      blocks: blocks,
      gate: gate,
      partial: partial,
      droppedHoldings: droppedHoldings,
      holdingsCount: holdingsCount,
      riskyHoldingsCount: riskyHoldingsCount,
      totalValue: totalValue,
      investedValue: investedValue,
      coveredInvestedValue: coveredInvestedValue,
      cashFraction: cashFraction,
      benchmarkVolAnn: benchmarkVolAnn,
    ));

/// The refusal shape: no `as_of`, no blocks, no accounting (M04
/// `_refusal_payload`).
Map<String, dynamic> refusalJson({Map<String, dynamic>? gate}) => {
      'status': 'refused_mock_data',
      'as_of': null,
      'generated_at': '2026-08-02T09:00:00+00:00',
      'engine_version': 'cr136.v1',
      'gate': gate ?? gateJson(),
      'metrics': {
        'status': 'refused_mock_data',
        'reason': 'use_real_market_data=false',
        'engine_version': 'cr136.v1',
        'generated_at': '2026-08-02T09:00:00+00:00',
      },
    };

Map<String, dynamic> noHoldingsJson({Map<String, dynamic>? gate}) => {
      'status': 'no_holdings',
      'as_of': '2026-08-02',
      'generated_at': '2026-08-02T09:00:00+00:00',
      'engine_version': 'cr136.v1',
      'gate': gate ?? gateJson(),
      'metrics': {
        'status': 'no_holdings',
        'as_of': '2026-08-02',
        'generated_at': '2026-08-02T09:00:00+00:00',
        'engine_version': 'cr136.v1',
      },
    };

Map<String, dynamic> findingJson({
  bool created = true,
  Map<String, String>? sections,
  Map<String, dynamic>? gate,
}) =>
    {
      'journal_entry_id': 'je-1',
      'created': created,
      'as_of': '2026-08-02',
      'sections': sections ??
          const {
            'head': '> **Educational simulation. Not investment advice.** HEAD-MARK',
            'f1': 'F1-MARK',
            'f2': 'F2-MARK',
            'f3': 'F3-MARK',
            'f4': 'F4-MARK',
            'f5': 'F5-MARK',
          },
      'gate': gate ?? gateJson(dailyUsed: 1),
    };
