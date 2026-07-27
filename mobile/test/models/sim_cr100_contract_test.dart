/// CR100 contract guard — the defect class this CR exists to close is a
/// fixture mirrored off the Dart model instead of the real backend response:
/// such a fixture only ever contains the keys the model already reads, so it
/// reproduces a silently-dropped-field bug instead of catching it (see
/// `mobile/lib/models/sim.dart` SimEarnings pre-CR100, which read
/// earnings_date/quarter/eps_estimate and silently discarded
/// ex_dividend_date/dividend_rate that backend/app/api/sim.py had been
/// sending since CR030).
///
/// The three fixtures below are transcribed directly from the endpoints'
/// return dicts, not from this file's own models:
///   - backend/app/api/portfolio.py:76-85 (sector_allocation)
///   - backend/app/api/sim.py:441-473, backend/app/services/cost_basis_lots.py
///     Lot NamedTuple (get_holding_lots)
///   - backend/app/api/sim.py:581-601 (earnings, CR030 dividend fields)
/// read from source 2026-07-27 (same date as the CR100 acceptance doc).
library;

import 'package:ami_trade/models/sim.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CR026 — sector allocation', () {
    // Transcribed from backend/app/api/portfolio.py sector_allocation().
    final full = {
      'allocation': {'Technology': 0.4212, 'Healthcare': 0.2, 'Other': 0.1},
      'total_value': 12345.67,
      'compliance': {
        'max_sector': 0.4212,
        'max_sector_name': 'Technology',
        'max_allowed': 0.40,
        'compliant': false,
      },
    };

    test('parses every field, including the Other bucket', () {
      final a = SectorAllocation.fromJson(full);
      expect(a.allocation['Technology'], 0.4212);
      expect(a.allocation['Other'], 0.1);
      expect(a.totalValue, 12345.67);
      expect(a.compliance.maxSector, 0.4212);
      expect(a.compliance.maxSectorName, 'Technology');
      expect(a.compliance.compliant, false);
    });

    test('max_allowed is read from the wire, never hard-coded 0.40', () {
      final custom = {
        ...full,
        'compliance': {
          'max_sector': 0.55,
          'max_sector_name': 'Technology',
          'max_allowed': 0.60, // a mandate with a non-default tolerance
          'compliant': true,
        },
      };
      final a = SectorAllocation.fromJson(custom);
      expect(a.compliance.maxAllowed, 0.60);
      expect(a.compliance.compliant, true);
    });

    test(
        'max_sector_name null (entirely-unclassified portfolio) stays null, '
        'never becomes "Other"', () {
      final unclassified = {
        'allocation': {'Other': 1.0},
        'total_value': 500.0,
        'compliance': {
          'max_sector': 0.0,
          'max_sector_name': null,
          'max_allowed': 0.40,
          'compliant': true,
        },
      };
      final a = SectorAllocation.fromJson(unclassified);
      expect(a.compliance.maxSectorName, isNull);
      // The DEF059 inversion guard: the backend excludes "Other" from the
      // compliance judgement, so a wire response can never name "Other" as
      // the breaching sector. Assert the model doesn't invent that either.
      expect(a.compliance.maxSectorName, isNot('Other'));
    });

    test('a renamed/missing required key throws, not silently defaults', () {
      final renamed = {
        'allocation': {'Technology': 0.4},
        'total_value': 100.0,
        'compliance': {
          'max_sector': 0.4,
          'max_sector_name': 'Technology',
          // 'max_allowed' renamed away — must throw, not default to 0.40.
          'concentration_cap': 0.40,
          'compliant': true,
        },
      };
      expect(() => SectorAllocation.fromJson(renamed), throwsA(anything));
    });
  });

  group('CR029 — per-lot cost basis', () {
    // Transcribed from backend/app/api/sim.py get_holding_lots() +
    // backend/app/services/cost_basis_lots.py Lot._asdict().
    final full = {
      'ticker': 'AAPL',
      'current_price': 231.4,
      'price_source': 'yfinance_live',
      'lots': [
        {
          'entry_trade_id': 'a1b2c3',
          'entry_date': '2026-05-02T13:00:00Z',
          'entry_price': 180.0,
          'quantity': 10.0,
          'quantity_open': 4.0,
          'quantity_closed': 6.0,
          'realised_pnl': 300.0,
          'unrealised_pnl': 205.6,
          'status': 'partially_closed',
        },
        {
          // A fully-closed lot: unrealised_pnl is absent, not 0.0.
          'entry_trade_id': 'd4e5f6',
          'entry_date': '2026-04-01T09:30:00Z',
          'entry_price': 150.0,
          'quantity': 5.0,
          'quantity_open': 0.0,
          'quantity_closed': 5.0,
          'realised_pnl': 90.0,
          'unrealised_pnl': null,
          'status': 'closed',
        },
      ],
      'totals': {
        'realised_pnl': 390.0,
        'unrealised_pnl': 205.6,
        'quantity_open': 4.0,
      },
    };

    test('parses ticker + price + every lot', () {
      final h = HoldingLots.fromJson(full);
      expect(h.ticker, 'AAPL');
      expect(h.currentPrice, 231.4);
      expect(h.priceSource, 'yfinance_live');
      expect(h.lots, hasLength(2));
      expect(h.lots[0].status, 'partially_closed');
      expect(h.lots[0].unrealisedPnl, 205.6);
      expect(h.totals.realisedPnl, 390.0);
    });

    test(
        "a closed lot's unrealised_pnl is null, and stays null — "
        'never coerced to 0.0', () {
      final h = HoldingLots.fromJson(full);
      final closed = h.lots[1];
      expect(closed.status, 'closed');
      expect(closed.unrealisedPnl, isNull);
      expect(closed.unrealisedPnl, isNot(0.0));
    });

    test('totals.unrealised_pnl is a required, always-present field', () {
      final h = HoldingLots.fromJson(full);
      expect(h.totals.unrealisedPnl, 205.6);
    });

    test('a missing required lot field throws', () {
      final malformed = {
        ...full,
        'lots': [
          {
            'entry_trade_id': 'a1b2c3',
            'entry_date': '2026-05-02T13:00:00Z',
            'entry_price': 180.0,
            'quantity': 10.0,
            'quantity_open': 4.0,
            'quantity_closed': 6.0,
            // 'realised_pnl' missing — must throw.
            'unrealised_pnl': 205.6,
            'status': 'partially_closed',
          },
        ],
      };
      expect(() => HoldingLots.fromJson(malformed), throwsA(anything));
    });
  });

  group('CR030 — dividend fields on the earnings response', () {
    // Transcribed from backend/app/api/sim.py earnings().
    Map<String, dynamic> earningsJson({Object? exDiv, Object? divRate}) => {
          'ticker': 'MSFT',
          'source': 'yfinance',
          'earnings_date': '2026-07-25',
          'quarter': 'Q4',
          'eps_estimate': 3.12,
          'ex_dividend_date': exDiv,
          'dividend_rate': divRate,
        };

    test('both dividend fields present are parsed', () {
      final e = SimEarnings.fromJson(
          earningsJson(exDiv: '2026-08-15', divRate: 0.83));
      expect(e.exDividendDate, '2026-08-15');
      expect(e.dividendRate, 0.83);
      expect(e.hasDividendData, isTrue);
    });

    test('both null (non-payer / no window) -> chip hidden', () {
      final e = SimEarnings.fromJson(earningsJson());
      expect(e.exDividendDate, isNull);
      expect(e.dividendRate, isNull);
      expect(e.hasDividendData, isFalse);
    });

    test('either field alone still surfaces the chip', () {
      final onlyDate = SimEarnings.fromJson(earningsJson(exDiv: '2026-08-15'));
      expect(onlyDate.hasDividendData, isTrue);

      final onlyRate = SimEarnings.fromJson(earningsJson(divRate: 0.5));
      expect(onlyRate.hasDividendData, isTrue);
    });

    test('a missing ticker (required) throws', () {
      final malformed = {
        'source': 'yfinance',
        'earnings_date': '2026-07-25',
        'quarter': 'Q4',
        'eps_estimate': 3.12,
        'ex_dividend_date': null,
        'dividend_rate': null,
      };
      expect(() => SimEarnings.fromJson(malformed), throwsA(anything));
    });
  });
}
