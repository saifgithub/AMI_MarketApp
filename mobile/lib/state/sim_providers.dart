/// Riverpod state for Sim Trading (portfolio + trades + ticker quotes).
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class SimState {
  const SimState({
    this.portfolio,
    this.trades = const [],
    this.loading = false,
    this.submitting = false,
    this.lastSubmit,
    this.error,
  });

  final SimPortfolio? portfolio;
  final List<SimTrade> trades;
  final bool loading;
  final bool submitting;
  final SimSubmitResult? lastSubmit;
  final String? error;

  SimState copyWith({
    SimPortfolio? portfolio,
    List<SimTrade>? trades,
    bool? loading,
    bool? submitting,
    SimSubmitResult? lastSubmit,
    String? error,
    bool clearLastSubmit = false,
    bool clearError = false,
  }) {
    return SimState(
      portfolio: portfolio ?? this.portfolio,
      trades: trades ?? this.trades,
      loading: loading ?? this.loading,
      submitting: submitting ?? this.submitting,
      lastSubmit: clearLastSubmit ? null : (lastSubmit ?? this.lastSubmit),
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class SimNotifier extends StateNotifier<SimState> {
  SimNotifier(this._ref) : super(const SimState());

  final Ref _ref;

  Future<void> refresh() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      // Evaluate stops/targets every refresh so the user sees their fills
      // close as price walks against them.
      await api.simEvaluate(userId);
      final portfolio = await api.simPortfolio(userId);
      final trades = await api.simListTrades(userId);
      state = state.copyWith(portfolio: portfolio, trades: trades, loading: false);
    } catch (e) {
      state = state.copyWith(loading: false, error: 'Could not load sim: $e');
    }
  }

  Future<SimSubmitResult?> submit({
    required String ticker,
    required String side,
    required double quantity,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    state = state.copyWith(submitting: true, clearError: true, clearLastSubmit: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final result = await api.simSubmit(
        userId: userId,
        ticker: ticker,
        side: side,
        quantity: quantity,
        stop: stop,
        target: target,
        horizonDays: horizonDays,
        verdictRef: verdictRef,
      );
      state = state.copyWith(submitting: false, lastSubmit: result);
      await refresh();
      // refresh journal too — new sim_trade entry
      await _ref.read(journalNotifierProvider.notifier).refresh();
      // refresh watchlist — backend auto-added the traded ticker so the
      // ticker tape (which listens on watchlist contents) picks it up.
      await _ref.read(watchlistNotifierProvider.notifier).refresh();
      return result;
    } catch (e) {
      state = state.copyWith(submitting: false, error: 'Submit failed: $e');
      return null;
    }
  }

  Future<void> closeTrade(String tradeId) async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.simCloseTrade(userId, tradeId);
      await refresh();
      await _ref.read(journalNotifierProvider.notifier).refresh();
    } catch (e) {
      state = state.copyWith(error: 'Close failed: $e');
    }
  }

  Future<void> reset() async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.simResetPortfolio(userId);
      await refresh();
    } catch (e) {
      state = state.copyWith(error: 'Reset failed: $e');
    }
  }

  void clearLastSubmit() {
    state = state.copyWith(clearLastSubmit: true);
  }
}

final simNotifierProvider = StateNotifierProvider<SimNotifier, SimState>((ref) {
  final n = SimNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});
