/// Riverpod provider for ticker tape quote data.
///
/// Fetches directly from Yahoo Finance every kTickerTapeRefreshSeconds.
/// Background refreshes are silent — no loading flash between cycles.
/// Falls back to last known quotes (marked stale) when the network fails.
library;

import 'dart:async';

import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// Named constant so tier-based speed is a one-line change later.
const int kTickerTapeRefreshSeconds = 120;

/// Active bourse — hardcoded to US at alpha.
/// Wire to the user's mandate field in Phase 2 (Tadawul / Bursa landing).
final activeBourseProvider = Provider<Bourse>((_) => Bourse.us);

/// Projection of the watchlist down to a stable, content-comparable key.
/// Sorted + comma-joined so Riverpod's default `==` fires the listener only
/// when the set of watched tickers actually changes — not on every transient
/// loading/busy flag flip in the watchlist state.
final _watchlistTickersKeyProvider = Provider<String>((ref) {
  final items = ref.watch(watchlistNotifierProvider).items;
  final tickers = items.map((e) => e.ticker).toList()..sort();
  return tickers.join(',');
});

class TickerTapeData {
  const TickerTapeData({required this.quotes, this.isStale = false});

  final List<TickerQuote> quotes;
  final bool isStale;

  /// Convenience: market state from the first quote (all quotes share one bourse).
  String get marketState =>
      quotes.isEmpty ? 'CLOSED' : quotes.first.marketState;
}

class TickerTapeNotifier extends AsyncNotifier<TickerTapeData> {
  final _service = YahooFinanceService();
  Timer? _timer;
  bool _disposed = false;
  TickerTapeData? _lastGood;

  @override
  Future<TickerTapeData> build() async {
    _disposed = false;
    ref.onDispose(() {
      _disposed = true;
      _timer?.cancel();
    });
    _timer?.cancel();
    _timer = Timer.periodic(
      Duration(seconds: kTickerTapeRefreshSeconds),
      (_) => _silentRefresh(),
    );
    // Re-fetch immediately whenever the watchlist changes (add / remove
    // ticker), instead of waiting up to 120s for the next timer tick.
    // ref.listen survives across rebuilds — no loading flash, just a
    // silent state update once the new quotes land.
    ref.listen<String>(
      _watchlistTickersKeyProvider,
      (prev, next) {
        if (prev != next) _silentRefresh();
      },
    );
    return _fetch();
  }

  // Background refresh: updates state without flashing the tape to shimmer.
  Future<void> _silentRefresh() async {
    if (_disposed) return;
    final result = await _fetch();
    if (!_disposed) state = AsyncData(result);
  }

  Future<TickerTapeData> _fetch() async {
    final bourse = ref.read(activeBourseProvider);
    final watchlistTickers = ref
        .read(watchlistNotifierProvider)
        .items
        .map((e) => e.ticker)
        .toList();
    final symbols =
        YahooFinanceService.buildTickerList(watchlistTickers, bourse);

    // Try direct Yahoo Finance first.
    var quotes = await _service.fetchQuotes(symbols, bourse);

    // Fall back to AMI backend batch endpoint when direct Yahoo fails.
    // The backend uses a server-side yfinance call with a proper User-Agent
    // that works reliably even when the keyless direct call is rate-limited.
    if (quotes.isEmpty) {
      try {
        final api = ref.read(apiClientProvider);
        quotes = await api.fetchTapeQuotes(symbols);
      } catch (_) {
        quotes = [];
      }
    }

    if (quotes.isEmpty) {
      if (_lastGood != null) {
        return TickerTapeData(quotes: _lastGood!.quotes, isStale: true);
      }
      return const TickerTapeData(quotes: []);
    }

    final result = TickerTapeData(quotes: quotes);
    _lastGood = result;
    return result;
  }
}

final tickerTapeProvider =
    AsyncNotifierProvider<TickerTapeNotifier, TickerTapeData>(
  TickerTapeNotifier.new,
);
