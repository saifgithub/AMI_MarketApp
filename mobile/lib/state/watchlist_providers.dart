/// Riverpod state for the user's watchlist (A18).
///
/// Loads once on provider creation (app start), then refreshes whenever
/// Portfolio is refreshed (the screen pulls both) and after every
/// add/remove. We deliberately don't poll — quotes are cached server-side
/// and the user manually pull-to-refreshes.
library;

import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
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
      // DEF332 — every write below this point happens after an `await`, so the
      // notifier may already be disposed: `SimNotifier.submit` fans out to the
      // journal and the watchlist with `unawaited(...)` on purpose (the sheet
      // closes and neither surface is on screen), which means that work
      // routinely outlives whatever tore the container down — a user leaving
      // the screen, or a test's tearDown. Writing `state` then throws
      // `Bad state: Tried to use <Notifier> after \`dispose\` was called`, which
      // is what riverpod means by "Consider checking `mounted`". Both the
      // success and the error path need it: a disposed notifier cannot report
      // an error either.
      if (!mounted) return;
      state = state.copyWith(items: items, loading: false);
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(
          error: friendlyError(e, action: 'load your watchlist'),
          loading: false);
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
      state = state.copyWith(
          error: friendlyError(e, action: 'add that ticker'),
          busy: false);
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
      state = state.copyWith(
          error: friendlyError(e, action: 'remove that ticker'),
          busy: false);
    }
  }
}


final watchlistNotifierProvider =
    StateNotifierProvider<WatchlistNotifier, WatchlistState>((ref) {
  final n = WatchlistNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});
