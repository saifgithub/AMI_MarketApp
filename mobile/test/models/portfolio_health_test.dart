// CR136 M09 — envelope parsing: both nestings, gate keys, refusal shape.

import 'package:ami_trade/models/portfolio_health.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/portfolio_health_fixtures.dart';

void main() {
  group('envelope nesting', () {
    test('the nested and flat shapes parse identically', () {
      final nested = PortfolioHealth.fromJson(healthJson());
      final flat = PortfolioHealth.fromJson(healthJson(nested: false));

      for (final h in [nested, flat]) {
        expect(h.status, 'ok');
        expect(h.asOf, '2026-08-02');
        expect(h.engineVersion, 'cr136.v1');
        expect(h.holdingsCount, 6);
        expect(h.riskyHoldingsCount, 6);
        expect(h.investedValue, 100000);
        expect(h.coveredInvestedValue, 100000);
        expect(h.cashFraction, closeTo(0.1667, 1e-9));
        expect(h.benchmarkVolAnn, closeTo(0.1510, 1e-9));
        expect(h.blocks.keys, contains('portfolio_volatility'));
      }
    });

    test('the flat variant really has no wrapper to fall back on', () {
      // M09 §7 pins this seam deliberately: if M07 ever stops wrapping the
      // engine payload under `metrics`, the card keeps working and the fix is
      // one `fromJson`, not a dead surface. The fixture has to actually drop
      // the wrapper or this proves nothing.
      final flat = healthJson(nested: false);
      expect(flat.containsKey('metrics'), isFalse);
      final parsed = PortfolioHealth.fromJson(flat);
      expect(parsed.holdingsCount, 6);
      expect(parsed.blocks.length, 5);
      expect(parsed.benchmarkVolAnn, closeTo(0.1510, 1e-9));
    });
  });

  group('gate', () {
    test('all eight keys survive the trip', () {
      final h = PortfolioHealth.fromJson(healthJson(
        gate: gateJson(
          mode: 'trial',
          trialActive: true,
          trialFindingsUsed: 2,
          trialFindingsBudget: 7,
          trialDaysLeft: 9,
          dailyUsed: 1,
          dailyCap: 2,
          planHasAccess: false,
        ),
      ));
      expect(h.gate.mode, 'trial');
      expect(h.gate.trialActive, isTrue);
      expect(h.gate.trialFindingsUsed, 2);
      expect(h.gate.trialFindingsBudget, 7);
      expect(h.gate.trialDaysLeft, 9);
      expect(h.gate.dailyUsed, 1);
      expect(h.gate.dailyCap, 2);
      expect(h.gate.planHasAccess, isFalse);
    });

    test('a missing gate reads as closed, never as access', () {
      final json = healthJson()..remove('gate');
      final h = PortfolioHealth.fromJson(json);
      expect(h.gate.planHasAccess, isFalse);
      expect(h.gate.mode, 'plan',
          reason: 'the client may not invent an entitlement the server has '
              'not granted; the tiles are free and still render');
    });
  });

  group('non-ok statuses', () {
    test('the refusal shape carries no as_of and no blocks', () {
      final h = PortfolioHealth.fromJson(refusalJson());
      expect(h.status, 'refused_mock_data');
      expect(h.asOf, isNull);
      expect(h.blocks, isEmpty);
      expect(h.isOk, isFalse);
      // Accounting is absent from the wire, so it reads as zero rather than as
      // a stale number from the last successful evaluation.
      expect(h.totalValue, 0);
      expect(h.holdingsCount, 0);
    });

    test('the empty-book shape parses without blocks', () {
      final h = PortfolioHealth.fromJson(noHoldingsJson());
      expect(h.status, 'no_holdings');
      expect(h.asOf, '2026-08-02');
      expect(h.blocks, isEmpty);
    });
  });

  group('metric blocks', () {
    test('an insufficient block carries null value AND null standard error',
        () {
      final h = PortfolioHealth.fromJson(
        healthJson(blocks: insufficientBlocks()),
      );
      final vol = h.block('portfolio_volatility')!;
      expect(vol.sufficient, isFalse);
      expect(vol.value, isNull);
      expect(vol.standardError, isNull,
          reason: '0.0 would read as "we measured zero risk"');
      expect(vol.tEff, isNull);
      expect(vol.insufficientCause, 'short_window');
      expect(vol.nObservations, 47,
          reason: 'the shortfall count is still real and is what the copy '
              'shows the user');
    });

    test('extensions pass through untouched', () {
      final h = PortfolioHealth.fromJson(healthJson());
      final risk = h.block('risk_contribution')!;
      expect(risk.extensions['per_holding'], isA<List>());
      expect((risk.extensions['per_holding'] as List).length, 4);
      expect(h.block('beta')!.extensions['r_squared'], closeTo(0.61, 1e-9));
      expect(
        h.block('weight_concentration')!.extensions['effective_n'],
        closeTo(3.8, 1e-9),
      );
    });

    test('dropped holdings survive as ticker/reason rows', () {
      final h = PortfolioHealth.fromJson(healthJson(
        partial: true,
        droppedHoldings: const [
          {'ticker': 'RIVN', 'reason': 'short_history'},
        ],
      ));
      expect(h.partial, isTrue);
      expect(h.droppedHoldings.single['ticker'], 'RIVN');
      expect(h.droppedHoldings.single['reason'], 'short_history');
    });
  });

  group('units — the pin that stops a 19.69% drawdown printing as 1969%', () {
    test('a Tier-1 fraction scales by 100', () {
      final block = HealthMetricBlock.fromJson(
        blockJson('portfolio_volatility', value: 0.1898),
      );
      expect(block.unit, HealthMetricUnit.fraction);
      expect(block.valuePercent, closeTo(18.98, 1e-9));
    });

    test('a Tier-2 realised value is already percent and is not scaled', () {
      final block = HealthMetricBlock.fromJson(
        blockJson('realised_max_drawdown', value: 19.69),
      );
      expect(block.unit, HealthMetricUnit.percent);
      expect(block.valuePercent, closeTo(19.69, 1e-9),
          reason: 'this is the exact double-scaling M06 shipped and its audit '
              'caught: 1969.00% for a 19.69% drawdown');
    });

    test('a ratio has no percent reading at all', () {
      final beta = HealthMetricBlock.fromJson(blockJson('beta', value: 1.07));
      expect(beta.unit, HealthMetricUnit.ratio);
      expect(() => beta.valuePercent, throwsStateError);
    });

    test('an unpinned metric throws rather than guessing a scale', () {
      final unknown =
          HealthMetricBlock.fromJson(blockJson('sortino_ratio', value: 1.2));
      expect(() => unknown.unit, throwsStateError);
      expect(() => unknown.valuePercent, throwsStateError);
    });

    test('valuePercent is null when the block carries no value', () {
      final block = HealthMetricBlock.fromJson(blockJson(
        'portfolio_volatility',
        sufficient: false,
        insufficientCause: 'short_window',
      ));
      expect(block.valuePercent, isNull);
    });

    test('every metric the engine emits has a pinned unit', () {
      // The engine's block ids, from `compute_health` in
      // `backend/app/services/portfolio_health.py`. A metric added there
      // without a unit here reaches the screen with a guessed scale.
      const emitted = [
        'portfolio_volatility',
        'beta',
        'tracking_error',
        'effective_bets',
        'risk_contribution',
        'mcr',
        'weight_concentration',
        'typical_bad_month',
        'scenario_panel',
      ];
      for (final metric in emitted) {
        expect(kMetricValueUnit.containsKey(metric), isTrue,
            reason: '$metric has no pinned unit');
      }
    });
  });

  group('the Finding envelope', () {
    test('sections and gate parse; created distinguishes write from replay',
        () {
      final fresh = HealthFinding.fromJson(findingJson());
      expect(fresh.journalEntryId, 'je-1');
      expect(fresh.created, isTrue);
      expect(fresh.asOf, '2026-08-02');
      expect(fresh.sections.keys,
          containsAll(['head', 'f1', 'f2', 'f3', 'f4', 'f5']));
      expect(fresh.gate.dailyUsed, 1);

      final replay = HealthFinding.fromJson(findingJson(created: false));
      expect(replay.created, isFalse,
          reason: 'a same-day repeat spends no budget and must be '
              'distinguishable from a fresh write');
    });

    test('a non-string section value is dropped rather than coerced', () {
      final json = findingJson();
      json['sections'] = <String, dynamic>{
        ...(json['sections'] as Map).cast<String, dynamic>(),
        'f2': 42,
      };
      final finding = HealthFinding.fromJson(json);
      expect(finding.sections.containsKey('f2'), isFalse,
          reason: 'rendering "42" as a section would put a number in the '
              'report that no validator ever saw');
    });
  });
}
