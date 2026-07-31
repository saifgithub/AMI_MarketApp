/// Riverpod state for price alerts (CR027 §4) — per-ticker family provider
/// (mirrors `tickerLotsProvider`) plus a create/cancel controller (mirrors
/// `PurchaseController`'s busy/error shape). There's no cross-ticker "all
/// my alerts" screen — alerts are only ever viewed/managed inline on
/// TickerDetail, so a per-ticker cache is all this needs.
library;

import 'package:ami_trade/models/price_alert.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Active alerts for one ticker. Fetches every active alert for the user
/// and filters client-side — the backend doesn't filter by ticker, and at
/// the 10-active-alert-per-user cap this is a non-issue.
final priceAlertsForTickerProvider =
    FutureProvider.autoDispose.family<List<PriceAlert>, String>((ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  final all = await api.priceAlerts(userId, status: 'active');
  final upper = ticker.toUpperCase();
  return all.where((a) => a.ticker == upper).toList();
});

@immutable
class PriceAlertControllerState {
  const PriceAlertControllerState({this.busy = false, this.error});

  final bool busy;
  final String? error;

  PriceAlertControllerState copyWith({
    bool? busy,
    String? error,
    bool clearError = false,
  }) {
    return PriceAlertControllerState(
      busy: busy ?? this.busy,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class PriceAlertController extends StateNotifier<PriceAlertControllerState> {
  PriceAlertController(this._ref) : super(const PriceAlertControllerState());

  final Ref _ref;

  Future<bool> create({
    required String ticker,
    required String thresholdType,
    required double thresholdPrice,
  }) async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.createPriceAlert(
        userId,
        ticker: ticker,
        thresholdType: thresholdType,
        thresholdPrice: thresholdPrice,
      );
      _ref.invalidate(priceAlertsForTickerProvider(ticker.toUpperCase()));
      state = state.copyWith(busy: false);
      return true;
    } catch (e) {
      state = state.copyWith(
        error: friendlyError(e, action: 'create that price alert'),
        busy: false,
      );
      return false;
    }
  }

  Future<void> cancel(String ticker, String alertId) async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.cancelPriceAlert(userId, alertId);
      _ref.invalidate(priceAlertsForTickerProvider(ticker.toUpperCase()));
      state = state.copyWith(busy: false);
    } catch (e) {
      state = state.copyWith(
        error: friendlyError(e, action: 'cancel that price alert'),
        busy: false,
      );
    }
  }
}

final priceAlertControllerProvider =
    StateNotifierProvider<PriceAlertController, PriceAlertControllerState>((ref) {
  return PriceAlertController(ref);
});
