/// CR172 + DEF363 — the Room verdict's structure, parsed the way the wire sends it.
///
/// **Every payload in this file is the SERVER's key set, not a convenient one.**
/// That is the entire point. DEF363 was a client reading `greeks_reason`, a key
/// no backend surface has ever emitted at the structure level, and it survived
/// because both existing tests supplied that key themselves — proving the
/// parser against a fixture instead of against the wire. A test that invents
/// the input it is checking proves the test.
///
/// The keys below are `CostedStructure` in `backend/app/schemas/options.py`,
/// which is the one class `/propose`, `/reprice` and `Verdict.structure` all
/// serialise. If that class grows a field, this fixture is where the client
/// notices.
library;

import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:flutter_test/flutter_test.dart';

/// `CostedStructure`, key for key, as FastAPI serialises it.
Map<String, dynamic> _structure({
  List<String> greeksNotEvaluated = const [],
  Map<String, dynamic>? greeks,
  double? spot = 195.42,
  String? pricedAt = '2026-08-23T02:14:07.123456Z',
}) {
  return {
    'strategy_name': 'bull_call_spread',
    'contracts': 2,
    'expiry': '2026-10-07',
    'days_to_expiry': 45,
    'underlying': 'AAPL',
    'legs': [
      {
        'right': 'call',
        'strike': 195.0,
        'quantity': 2.0,
        'premium': 8.4,
        'multiplier': 100.0,
        'expiry': '2026-10-07',
        'occ_symbol': null,
      },
      {
        'right': 'call',
        'strike': 205.0,
        'quantity': -2.0,
        'premium': 3.9,
        'multiplier': 100.0,
        'expiry': '2026-10-07',
        'occ_symbol': null,
      },
    ],
    'metrics': {
      'net_cost': 900.0,
      'max_loss': 900.0,
      'max_gain': 1100.0,
      'unbounded_loss': false,
      'unbounded_gain': false,
      'break_evens': [199.5],
      'collateral_required': null,
      'has_uncovered_short_call': false,
      'shares_locked': 0.0,
      'covered_by_shares': false,
    },
    'net_greeks': greeks,
    'greeks_not_evaluated': greeksNotEvaluated,
    'compliance': {
      'passed': true,
      'violations': <String>[],
      'advisories': <String>[],
      'not_evaluated': <String>[],
      'blocked_by': null,
    },
    'not_evaluated': <String>[],
    'rationale': 'Defined risk, financed by the short strike.',
    'spot': spot,
    'priced_at': pricedAt,
  };
}

Map<String, dynamic> _verdict({Map<String, dynamic>? structure}) => {
      'action': 'APPROVE',
      'size_pct': 3.0,
      'entry': 195.0,
      'target': 215.0,
      'stop': 183.0,
      'time_horizon_days': 42,
      'reason': 'CIO: APPROVE.',
      'violations': <String>[],
      'overridden_from_llm': false,
      'opinions_not_included': <String>[],
      'level_provenance': {'entry': 'pm', 'stop': 'pm', 'target': 'pm'},
      'structure': structure,
    };

void main() {
  group('RoomVerdict.structure', () {
    test('an equity verdict carries no structure', () {
      final v = RoomVerdict.fromJson(_verdict());
      expect(v.structure, isNull);
      expect(v.isOptionApprove, isFalse);
      expect(v.isApprove, isTrue);
    });

    test('an option verdict carries the whole costed structure', () {
      final v = RoomVerdict.fromJson(_verdict(structure: _structure()));
      expect(v.isOptionApprove, isTrue);

      final s = v.structure!;
      expect(s.strategyName, 'bull_call_spread');
      expect(s.contracts, 2);
      expect(s.legs, hasLength(2));
      expect(s.legs[1].quantity, -2.0); // the short leg keeps its sign

      // The figures the user consents to — all present, none derived here.
      expect(s.metrics!.maxLoss, 900.0);
      expect(s.metrics!.maxGain, 1100.0);
      expect(s.metrics!.breakEvens, [199.5]);
      expect(s.compliance.passed, isTrue);
      expect(s.canAccept, isTrue);
    });

    test('the price the Room saw travels with the structure', () {
      // Without these the re-price at consent has no baseline to drift from,
      // and "what moved" becomes unanswerable rather than zero.
      final s = RoomVerdict.fromJson(_verdict(structure: _structure())).structure!;
      expect(s.spot, 195.42);
      expect(s.pricedAt, isNotNull);
      expect(s.pricedAt!.isUtc, isTrue,
          reason: 'a naive stamp would be read as device-local and the age of '
              'the price would be wrong by the device offset');
      expect(s.pricedAt!.year, 2026);
      expect(s.pricedAt!.month, 8);
      expect(s.pricedAt!.hour, 2);
    });

    test('a structure with no stamps says so rather than assuming now', () {
      final s = RoomVerdict.fromJson(
        _verdict(structure: _structure(spot: null, pricedAt: null)),
      ).structure!;
      expect(s.spot, isNull);
      expect(s.pricedAt, isNull);
    });
  });

  group('DEF363 — the greeks reason comes off the key the server sends', () {
    test('greeks_not_evaluated is read, and joined into one sentence', () {
      final s = OptionProposal.fromJson(_structure(
        greeksNotEvaluated: const [
          'call 195: no_risk_free_rate',
          'call 205: no_usable_iv',
        ],
      ));
      expect(s.greeks, isNull);
      expect(s.greeksReason, 'call 195: no_risk_free_rate; call 205: no_usable_iv');
    });

    test('a single failing leg reads as one sentence, unpunctuated', () {
      final s = OptionProposal.fromJson(
        _structure(greeksNotEvaluated: const ['call 195: expired']),
      );
      expect(s.greeksReason, 'call 195: expired');
    });

    test('an empty list is null, not an empty reason', () {
      // The ticket has a distinct string for "not computed, and the server did
      // not say why". An empty-string reason would render the reason-carrying
      // variant with nothing in it, which reads as a rendering bug rather than
      // as an absence.
      final s = OptionProposal.fromJson(_structure());
      expect(s.greeksReason, isNull);
    });

    test('greeks_reason is NOT read — it is not a key the server sends', () {
      // The mutation guard for DEF363. If the parser is reverted to the old
      // key, this payload — which carries BOTH — would return the wrong one.
      final payload = _structure(
        greeksNotEvaluated: const ['call 195: no_usable_iv'],
      )..['greeks_reason'] = 'a key no backend has ever emitted';
      final s = OptionProposal.fromJson(payload);
      expect(s.greeksReason, 'call 195: no_usable_iv');
    });

    test('present greeks leave the reason empty', () {
      final s = OptionProposal.fromJson(_structure(greeks: const {
        'delta': 0.42,
        'gamma': 0.03,
        'theta_per_day': -0.11,
        'vega_per_point': 0.19,
        'rho_per_point': 0.07,
      }));
      expect(s.greeks, isNotNull);
      expect(s.greeks!.delta, 0.42);
      expect(s.greeksReason, isNull);
    });
  });
}
