/// Ticker existence validation — client-side models (CR128).
/// Mirrors backend/app/schemas/tickers.py.
library;

class TickerSuggestion {
  const TickerSuggestion({
    required this.ticker,
    required this.companyName,
    required this.exchange,
  });

  final String ticker;
  final String companyName;
  final String exchange;

  factory TickerSuggestion.fromJson(Map<String, dynamic> j) {
    return TickerSuggestion(
      ticker: j['ticker'] as String,
      companyName: j['company_name'] as String,
      exchange: j['exchange'] as String,
    );
  }
}

class TickerValidation {
  const TickerValidation({
    required this.ticker,
    required this.exists,
    this.companyName,
    this.exchange,
    this.suggestion,
  });

  final String ticker;
  final bool exists;
  final String? companyName;
  final String? exchange;
  final TickerSuggestion? suggestion;

  factory TickerValidation.fromJson(Map<String, dynamic> j) {
    return TickerValidation(
      ticker: j['ticker'] as String,
      exists: j['exists'] as bool,
      companyName: j['company_name'] as String?,
      exchange: j['exchange'] as String?,
      suggestion: j['suggestion'] == null
          ? null
          : TickerSuggestion.fromJson(j['suggestion'] as Map<String, dynamic>),
    );
  }
}

/// CR283 — one hit from `GET /v1/tickers/resolve` (company name -> ticker).
/// Mirrors backend `TickerCandidate`; [market] is the wire code `US` | `MY`.
class ResolvedTicker {
  const ResolvedTicker({
    required this.ticker,
    required this.market,
    required this.shortName,
    required this.longName,
  });

  final String ticker;
  final String market;
  final String shortName;
  final String longName;

  factory ResolvedTicker.fromJson(Map<String, dynamic> j) {
    return ResolvedTicker(
      ticker: j['ticker'] as String,
      market: j['market'] as String,
      shortName: j['short_name'] as String,
      longName: j['long_name'] as String,
    );
  }
}
