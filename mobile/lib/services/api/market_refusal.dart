/// CR282 - a market's own order-rule refusal (board lot, tick grid, price
/// limit, shorts, market disabled), as the server states it.
///
/// `POST /v1/sim/submit` and `/preview` answer these with HTTP 422
/// `{detail: {code, message, market}}`, which Dio raises as an exception. The
/// generic path turns any 422 into "couldn't place that trade" and the rule
/// that actually refused the order is lost; this pulls the server's own
/// sentence back out so the ticket can show it verbatim. Any 422 that is not
/// shaped like a market rule (a bad ticker, a schema error) is NOT one of
/// these and returns null, so it keeps its existing handling.
library;

import 'package:dio/dio.dart';

class MarketRefusal {
  const MarketRefusal({
    required this.code,
    required this.message,
    required this.market,
  });

  /// Machine code: `board_lot`, `tick_size`, `price_limit`, `shorts_unsupported`,
  /// `market_disabled`, ...
  final String code;

  /// The server's user-facing sentence. Shown as-is.
  final String message;

  /// `MY` for Bursa.
  final String market;

  static MarketRefusal? fromError(Object error) {
    if (error is! DioException) return null;
    final r = error.response;
    if (r == null || r.statusCode != 422) return null;
    final data = r.data;
    if (data is! Map) return null;
    final detail = data['detail'];
    if (detail is! Map) return null;
    final code = detail['code'];
    final message = detail['message'];
    final market = detail['market'];
    if (code is! String || message is! String || market is! String) {
      return null;
    }
    if (message.trim().isEmpty) return null;
    return MarketRefusal(code: code, message: message, market: market);
  }
}
