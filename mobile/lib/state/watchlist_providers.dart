/// Riverpod state for the user's watchlist (A18).
///
/// The watchlist refreshes whenever Portfolio is refreshed (the screen
/// pulls both), and after every add/remove. We deliberately don't poll —
/// quotes are cached server-side and the user manually pull-to-refreshes.
library;

import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class WatchlistState {
  const WatchlistState({
    this.items = const [],
    this.loading = false,
    this.busy = false,
    this.error,
  });

  final List<WatchlistEntry> items;
  final bool loading;
  final bool busy;
  final String? error;

  WatchlistState copyWith({
    List<WatchlistEntry>? items,
    bool? loading,
    bool? busy,
    String? error,
    bool clearError = false,
  }) {
    return WatchlistState(
      items: items ?? this.items,
      loading: loading ?? this.loading,
      busy: busy ?? this.busy,
      error: clearError ? null : (error ?? this.error),
    );
  }
}


class WatchlistNotifier extends StateNotifier<WatchlistState> {
  WatchlistNotifier(this._ref) : super(const WatchlistState());

  final Ref _ref;

  Future<void> refresh() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final items = await api.watchlistList(userId);
      state = state.copyWith(items: items, loading: false);
    } catch (e) {
      state = state.copyWith(error: '$e', loading: false);
    }
  }

  Future<void> add(String ticker, {String? notes}) async {
    final t = ticker.trim().toUpperCase();
    if (t.isEmpty) return;
    state = state.copyWith(busy: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.watchlistAdd(userId, t, notes: notes);
      final items = await api.watchlistList(userId);
      state = state.copyWith(items: items, busy: false);
    } catch (e) {
      state = state.copyWith(error: '$e', busy: false);
    }
  }

  Future<void> remove(String ticker) async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.watchlistRemove(userId, ticker);
      final items = await api.watchlistList(userId);
      state = state.copyWith(items: items, busy: false);
    } catch (e) {
      state = state.copyWith(error: '$e', busy: false);
    }
  }
}


final watchlistNotifierProvider =
    StateNotifierProvider<WatchlistNotifier, WatchlistState>((ref) {
  return WatchlistNotifier(ref);
});
