/// Direct Yahoo Finance v7 quote service.
///
/// Bypasses the AMI backend — same JSON endpoint that yfinance wraps.
/// Returns an empty list on any network or parse error so callers degrade
/// gracefully (tape goes STALE rather than crashing).
library;

import 'package:dio/dio.dart';

enum Bourse { us, sa, my }

class TickerQuote {
  const TickerQuote({
    required this.symbol,
    required this.price,
    required this.changePercent,
    required this.marketState,
  });

  final String symbol;
  final double price;
  final double changePercent; // positive = up vs previous close
  final String marketState;   // 'REGULAR' | 'PRE' | 'POST' | 'CLOSED'
}

class YahooFinanceService {
  YahooFinanceService()
      : _dio = Dio(
          BaseOptions(
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 10),
          ),
        );

  final Dio _dio;

  static const int kMinTickers = 10;

  static const Map<Bourse, List<String>> defaultTickers = {
    Bourse.us: [
      'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
      'TSLA', 'META', 'JPM', 'NFLX', 'AMD',
    ],
    Bourse.sa: [
      '2222.SR', '1120.SR', '2010.SR', '7010.SR', '1180.SR',
      '4200.SR', '8010.SR', '1150.SR', '2350.SR', '2380.SR',
    ],
    Bourse.my: [
      '1155.KL', '1023.KL', '5347.KL', '4863.KL', '5296.KL',
      '1082.KL', '3816.KL', '5168.KL', '4197.KL', '5819.KL',
    ],
  };

  static const Map<Bourse, ({String lang, String region})> _locale = {
    Bourse.us: (lang: 'en-US', region: 'US'),
    Bourse.sa: (lang: 'ar-SA', region: 'SA'),
    Bourse.my: (lang: 'ms-MY', region: 'MY'),
  };

  /// Merges [watchlistTickers] with bourse defaults to reach [kMinTickers].
  /// User's tickers always lead; defaults fill the tail (no duplicates).
  static List<String> buildTickerList(
    List<String> watchlistTickers,
    Bourse bourse,
  ) {
    final result = [...watchlistTickers];
    for (final d in defaultTickers[bourse] ?? <String>[]) {
      if (result.length >= kMinTickers) break;
      if (!result.contains(d)) result.add(d);
    }
    return result;
  }

  Future<List<TickerQuote>> fetchQuotes(
    List<String> symbols,
    Bourse bourse,
  ) async {
    if (symbols.isEmpty) return [];
    final loc = _locale[bourse]!;
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        'https://query1.finance.yahoo.com/v7/finance/quote',
        queryParameters: {
          'symbols': symbols.join(','),
          'lang': loc.lang,
          'region': loc.region,
          'fields':
              'symbol,regularMarketPrice,regularMarketChangePercent,marketState',
        },
      );
      final result =
          (response.data?['quoteResponse']?['result'] as List?) ?? <dynamic>[];
      return result
          .whereType<Map<String, dynamic>>()
          .map(
            (m) => TickerQuote(
              symbol: (m['symbol'] as String?) ?? '',
              price: (m['regularMarketPrice'] as num?)?.toDouble() ?? 0,
              changePercent:
                  (m['regularMarketChangePercent'] as num?)?.toDouble() ?? 0,
              marketState: (m['marketState'] as String?) ?? 'CLOSED',
            ),
          )
          .where((q) => q.symbol.isNotEmpty && q.price > 0)
          .toList();
    } catch (_) {
      return [];
    }
  }
}
