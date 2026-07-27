/// Riverpod state for the TickerDetail chart (Bundle 2, AT:R41).
///
/// Family-keyed by (ticker, period) so the chart can switch periods
/// by swapping providers — Riverpod gives us the per-key cache for
/// free. The backend already caches each response for 60s, so we
/// don't layer a TTL on top.
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TickerHistoryKey {
  const TickerHistoryKey(this.ticker, this.period);
  final String ticker;
  final String period;

  @override
  bool operator ==(Object other) =>
      other is TickerHistoryKey &&
      other.ticker == ticker &&
      other.period == period;

  @override
  int get hashCode => Object.hash(ticker, period);
}

final tickerHistoryProvider =
    FutureProvider.autoDispose.family<SimHistory, TickerHistoryKey>(
        (ref, key) async {
  final api = ref.watch(apiClientProvider);
  return api.simHistory(key.ticker, key.period);
});

final tickerNewsProvider =
    FutureProvider.autoDispose.family<SimNews, String>((ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  return api.simNews(ticker);
});

final tickerEarningsProvider =
    FutureProvider.autoDispose.family<SimEarnings, String>((ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  return api.simEarnings(ticker);
});

/// CR029 — per-lot cost-basis feed for one held ticker, entry point from
/// Ticker Detail's lots section.
final tickerLotsProvider =
    FutureProvider.autoDispose.family<HoldingLots, String>((ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.simHoldingLots(userId, ticker);
});
