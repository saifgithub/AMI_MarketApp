// CR282 lane F1 - market resolution and the one money formatter.
//
// The US half pins today's output: each expectation is the literal string the
// pre-CR282 call sites produced by gluing `$` onto `NumberFormat('#,##0.00')`,
// so a formatter change that moves a US string fails here before it ships.

import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/features/markets/money.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';

void main() {
  group('marketForTicker', () {
    test('.KL is Malaysia, case and whitespace tolerant', () {
      expect(marketForTicker('1155.KL'), AppMarket.my);
      expect(marketForTicker('1155.kl'), AppMarket.my);
      expect(marketForTicker(' 5099.KL '), AppMarket.my);
      expect(marketForTicker('0166.KL'), AppMarket.my);
    });

    test('everything else, including nulls and indices, is US', () {
      expect(marketForTicker('AAPL'), AppMarket.us);
      expect(marketForTicker('BRK.B'), AppMarket.us);
      expect(marketForTicker('^KLSE'), AppMarket.us);
      expect(marketForTicker('SPY'), AppMarket.us);
      expect(marketForTicker(''), AppMarket.us);
      expect(marketForTicker(null), AppMarket.us);
      expect(marketForTicker('KL'), AppMarket.us);
    });
  });

  group('AppMarket', () {
    test('mirrors the backend MarketSpec', () {
      expect(AppMarket.us.currencyCode, 'USD');
      expect(AppMarket.us.symbol, r'$');
      expect(AppMarket.us.boardLot, 1);
      expect(AppMarket.my.currencyCode, 'MYR');
      expect(AppMarket.my.symbol, 'RM');
      expect(AppMarket.my.boardLot, 100);
    });

    test('fromCurrencyCode: MYR is Malaysia, anything unknown is US', () {
      expect(AppMarket.fromCurrencyCode('MYR'), AppMarket.my);
      expect(AppMarket.fromCurrencyCode('myr'), AppMarket.my);
      expect(AppMarket.fromCurrencyCode('USD'), AppMarket.us);
      expect(AppMarket.fromCurrencyCode(null), AppMarket.us);
      expect(AppMarket.fromCurrencyCode(''), AppMarket.us);
      expect(AppMarket.fromCurrencyCode('EUR'), AppMarket.us);
    });
  });

  group('formatMoney - US is string-identical to the legacy glue', () {
    final legacy = NumberFormat('#,##0.00');
    const samples = <double>[
      0,
      0.5,
      9.995,
      12.5,
      90,
      118.2,
      287.82,
      1234.5,
      10000,
      362137.57,
      1234567.891,
    ];

    for (final v in samples) {
      test('$v', () {
        expect(
          formatMoney(v, market: AppMarket.us),
          '\$${legacy.format(v)}',
        );
        expect(
          formatMoney(v, market: AppMarket.us, signed: true),
          '+\$${legacy.format(v)}',
        );
      });
    }

    test('literal pins', () {
      expect(formatMoney(12.5, market: AppMarket.us), r'$12.50');
      expect(formatMoney(1234.5, market: AppMarket.us), r'$1,234.50');
      expect(formatMoney(10000, market: AppMarket.us), r'$10,000.00');
      expect(formatMoney(10000, market: AppMarket.us, decimals: 0), r'$10,000');
      expect(formatMoney(0, market: AppMarket.us, signed: true), r'+$0.00');
    });

    test('grouped:false matches the toStringAsFixed(2) glue', () {
      for (final v in samples) {
        expect(
          formatMoney(v, market: AppMarket.us, grouped: false),
          '\$${v.toStringAsFixed(2)}',
        );
      }
      expect(formatMoney(1234.5, market: AppMarket.my, grouped: false),
          'RM1234.50');
    });

    test('ints format like doubles', () {
      expect(formatMoney(5, market: AppMarket.us), r'$5.00');
    });
  });

  group('formatMoney - Malaysia', () {
    test('RM prefix, no space, same grouping', () {
      expect(formatMoney(12.5, market: AppMarket.my), 'RM12.50');
      expect(formatMoney(1234.5, market: AppMarket.my), 'RM1,234.50');
      expect(formatMoney(50000, market: AppMarket.my, decimals: 0), 'RM50,000');
      expect(formatMoney(0.005, market: AppMarket.my, decimals: 3), 'RM0.005');
    });

    test('signed', () {
      expect(formatMoney(12.5, market: AppMarket.my, signed: true), '+RM12.50');
      expect(formatMoney(-12.5, market: AppMarket.my, signed: true), '-RM12.50');
    });
  });

  group('formatMoney - negatives, compact', () {
    test('negative carries its own sign, symbol after it', () {
      expect(formatMoney(-12.5, market: AppMarket.us), r'-$12.50');
      expect(formatMoney(-12.5, market: AppMarket.us, signed: true), r'-$12.50');
      expect(formatMoney(-1234.5, market: AppMarket.my), '-RM1,234.50');
    });

    test('compact', () {
      expect(formatMoney(1234, market: AppMarket.us, compact: true), r'$1.2K');
      expect(formatMoney(1500000, market: AppMarket.us, compact: true), r'$1.5M');
      expect(formatMoney(1234, market: AppMarket.my, compact: true), 'RM1.2K');
      expect(formatMoney(-1234, market: AppMarket.us, compact: true), r'-$1.2K');
      expect(
        formatMoney(1234, market: AppMarket.us, compact: true, signed: true),
        r'+$1.2K',
      );
    });
  });
}
