/// CR172 §10 — the option proposal wire model.
///
/// The payloads here are hand-built to the shapes the backend halves already
/// define at HEAD — `StrategyLeg`, `StrategyMetrics`, `Greeks` and
/// `ComplianceResult` as `check_option_open` returns it — because the route
/// that serialises them is slice 3 and does not exist yet. What these tests
/// pin is the half this lane owns: that a key which fails to arrive becomes an
/// absence the UI can render, never a number.
library;

import 'package:ami_trade/models/option_proposal.dart';
import 'package:flutter_test/flutter_test.dart';

/// Verbatim from `safety_floor.py::NAKED_CALL_REFUSAL`. Kept literal because
/// the point of the refusal path is that the SERVER's sentence is what the
/// user reads.
const nakedCallRefusal =
    'AMI will not open an uncovered short call. It is the one structure in '
    'this simulator whose loss has no ceiling — there is no strike, no width '
    'and no collateral figure that bounds it, because the stock above it has '
    'no bound. Containing it would need margin, and AMI runs no leverage of '
    'any kind. Covered calls, cash-secured puts and defined-risk spreads '
    'teach assignment without that tail.';

/// Verbatim from `safety_floor.py::_HALAL_OPTION_ADVISORY`.
const halalAdvisory =
    'Selling an option to open is widely held impermissible under Sharia: '
    'conventional options carry gharar (contractual uncertainty) and the '
    'premium is received for an obligation rather than an asset. AMI has no '
    'ruling of its own here and is not blocking the trade — this is for you '
    'to decide.';

Map<String, dynamic> bullCallSpreadPayload() => <String, dynamic>{
      'structure_id': 2,
      'strategy_name': 'bull_call_spread',
      'underlying': 'AAPL',
      'expiry': '2026-01-16',
      'days_to_expiry': 45,
      'narration': 'Defined risk on a move you already argued for.',
      'legs': <Map<String, dynamic>>[
        {
          'occ_symbol': 'AAPL  260116C00250000',
          'underlying': 'AAPL',
          'right': 'call',
          'strike': 250.0,
          'quantity': 1.0,
          'premium': 9.4,
          'multiplier': 100.0,
          'expiry': '2026-01-16',
        },
        {
          'occ_symbol': 'AAPL  260116C00260000',
          'underlying': 'AAPL',
          'right': 'call',
          'strike': 260.0,
          'quantity': -1.0,
          'premium': 4.0,
          'multiplier': 100.0,
          'expiry': '2026-01-16',
        },
      ],
      'metrics': <String, dynamic>{
        'net_cost': 540.0,
        'max_loss': 540.0,
        'max_gain': 460.0,
        'unbounded_loss': false,
        'unbounded_gain': false,
        'break_evens': <double>[255.4],
        'collateral_required': 0.0,
        'has_uncovered_short_call': false,
        'shares_locked': 0.0,
        'covered_by_shares': false,
      },
      'net_greeks': <String, dynamic>{
        'delta': 0.2143,
        'gamma': 0.0031,
        'theta_per_day': -0.0812,
        'vega_per_point': 0.1904,
        'rho_per_point': 0.0455,
      },
      'greeks_reason': null,
      'compliance': <String, dynamic>{
        'passed': true,
        'violations': <String>[],
        'blocked_by': null,
        'not_evaluated': <String>[],
        'advisories': <String>[],
      },
    };

void main() {
  group('OptionProposal.fromJson', () {
    test('reads a full structure off the wire without computing anything', () {
      final p = OptionProposal.fromJson(bullCallSpreadPayload());

      expect(p.structureId, 2);
      expect(p.strategyName, 'bull_call_spread');
      expect(p.strategyLabel, 'BULL CALL SPREAD');
      expect(p.underlying, 'AAPL');
      expect(p.daysToExpiry, 45);
      expect(p.legs, hasLength(2));
      expect(p.legs.first.isSellToOpen, isFalse);
      expect(p.legs.last.isSellToOpen, isTrue);
      expect(p.hasSellToOpen, isTrue);
      expect(p.metrics!.netCost, 540.0);
      expect(p.metrics!.maxLoss, 540.0);
      expect(p.metrics!.breakEvens, [255.4]);
      expect(p.greeks!.thetaPerDay, -0.0812);
      expect(p.canAccept, isTrue);
    });

    test('a missing figure is null, never zero', () {
      final j = bullCallSpreadPayload();
      (j['metrics'] as Map).remove('max_loss');
      (j['metrics'] as Map).remove('collateral_required');
      (j['legs'] as List).cast<Map>().first.remove('premium');
      j.remove('days_to_expiry');

      final p = OptionProposal.fromJson(j);
      expect(p.metrics!.maxLoss, isNull);
      expect(p.metrics!.collateralRequired, isNull);
      expect(p.legs.first.premium, isNull);
      expect(p.daysToExpiry, isNull);
    });

    test('no metrics block ⇒ no accept, whatever compliance said', () {
      final j = bullCallSpreadPayload()..remove('metrics');
      final p = OptionProposal.fromJson(j);
      expect(p.compliance.passed, isTrue);
      expect(p.metrics, isNull);
      expect(p.canAccept, isFalse);
    });

    test('a missing compliance block fails closed', () {
      final j = bullCallSpreadPayload()..remove('compliance');
      final p = OptionProposal.fromJson(j);
      expect(p.compliance.passed, isFalse);
      expect(p.isRefused, isTrue);
      expect(p.canAccept, isFalse);
    });

    test('a compliance block carrying no verdict also fails closed', () {
      // The block arrived; `passed` did not. A serializer that omits falsy
      // fields produces exactly this, and defaulting it to true would put a
      // YES button on a structure the floor never cleared.
      final j = bullCallSpreadPayload()
        ..['compliance'] = <String, dynamic>{'violations': <String>[]};
      final p = OptionProposal.fromJson(j);
      expect(p.compliance.passed, isFalse);
      expect(p.canAccept, isFalse);
    });

    test('the naked-call refusal carries the server sentence verbatim', () {
      final j = bullCallSpreadPayload();
      j['strategy_name'] = 'naked_call';
      (j['metrics'] as Map)
        ..['unbounded_loss'] = true
        ..['max_loss'] = null
        ..['collateral_required'] = null
        ..['has_uncovered_short_call'] = true;
      j['compliance'] = <String, dynamic>{
        'passed': false,
        'violations': <String>[nakedCallRefusal],
        'blocked_by': 'compliance',
        'not_evaluated': <String>[],
        'advisories': <String>[],
      };

      final p = OptionProposal.fromJson(j);
      expect(p.isRefused, isTrue);
      expect(p.canAccept, isFalse);
      expect(p.compliance.violations.single, nakedCallRefusal);
      expect(p.compliance.blockedBy, 'compliance');
      expect(p.metrics!.unboundedLoss, isTrue);
      expect(p.metrics!.maxLoss, isNull);
    });

    test('the disclosure gate reads advisories, not the sign of a quantity',
        () {
      final withAdvisory = OptionProposal.fromJson(
        bullCallSpreadPayload()
          ..['compliance'] = <String, dynamic>{
            'passed': true,
            'advisories': <String>[halalAdvisory],
          },
      );
      expect(withAdvisory.hasSellToOpen, isTrue);
      expect(withAdvisory.requiresDisclosure, isTrue);

      // The same short leg on a mandate the server raised nothing about.
      final none = OptionProposal.fromJson(bullCallSpreadPayload());
      expect(none.hasSellToOpen, isTrue);
      expect(none.requiresDisclosure, isFalse);
    });

    test('blank and non-string entries are dropped from the server lists', () {
      final j = bullCallSpreadPayload()
        ..['compliance'] = <String, dynamic>{
          'passed': false,
          'violations': <dynamic>['   ', 7, nakedCallRefusal],
          'not_evaluated': <dynamic>[''],
        };
      final p = OptionProposal.fromJson(j);
      expect(p.compliance.violations, [nakedCallRefusal]);
      expect(p.compliance.notEvaluated, isEmpty);
    });
  });
}
