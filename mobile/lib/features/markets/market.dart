/// CR282 lane F1 - which market a ticker or a book belongs to, and what that
/// market's money looks like.
///
/// Mirrors `backend/app/trading_math/markets.py`: `.KL` => Malaysia, everything
/// else (indices, OCC symbols, class shares) => US. US is the default for every
/// input the app cannot place, so a caller that never asks behaves exactly as it
/// did before CR282. Pure Dart: no flag read here - whether Bursa input is
/// *accepted* is `kBursaEnabled`'s job; whether a `.KL` amount is *labelled*
/// correctly must not depend on a build flag.
library;

enum AppMarket {
  us(currencyCode: 'USD', symbol: r'$', boardLot: 1),
  my(currencyCode: 'MYR', symbol: 'RM', boardLot: 100);

  const AppMarket({
    required this.currencyCode,
    required this.symbol,
    required this.boardLot,
  });

  /// ISO 4217 code, as the backend's `MarketSpec.currency` and as carried on
  /// API payloads' `currency` field.
  final String currencyCode;

  /// The prefix the app prints: `$12.50`, `RM12.50` (Malaysian convention, no
  /// space).
  final String symbol;

  /// Smallest tradable multiple. The server enforces it; the client uses it
  /// for quantity steppers and hints.
  final int boardLot;

  /// The `market` query-parameter value the sim routes take (`US` | `MY`).
  String get apiCode => this == AppMarket.my ? 'MY' : 'US';

  /// An API payload's `currency` -> its market. Null, empty, or any code the
  /// app has no market for resolves to US - the pre-CR282 behaviour, never a
  /// guess at a third currency.
  static AppMarket fromCurrencyCode(String? code) {
    final c = (code ?? '').trim().toUpperCase();
    for (final m in AppMarket.values) {
      if (m.currencyCode == c) return m;
    }
    return AppMarket.us;
  }
}

const String _bursaSuffix = '.KL';

/// `.KL` => Malaysia; everything else (including null, indices and OCC
/// symbols) => US. Same rule as the backend's `market_for`.
AppMarket marketForTicker(String? ticker) {
  final t = (ticker ?? '').trim().toUpperCase();
  return t.endsWith(_bursaSuffix) ? AppMarket.my : AppMarket.us;
}
