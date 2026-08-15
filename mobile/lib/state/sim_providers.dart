/// Riverpod state for Sim Trading (portfolio + trades + ticker quotes).
library;

import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
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
    this.restingOrders = const [],
    this.restingOrdersSupported = false,
    this.loading = false,
    this.submitting = false,
    this.lastSubmit,
    this.error,
  });

  final SimPortfolio? portfolio;
  final List<SimTrade> trades;

  /// CR170 — the book. Folded into [SimState] rather than given its own
  /// `FutureProvider` (the way sector allocation and the equity curve are)
  /// because these and cash are **coupled**: a cancel changes `cash_available`,
  /// so one state object has to invalidate them together or the screen shows a
  /// committed balance against an order that is no longer there.
  final List<SimRestingOrder> restingOrders;

  /// Whether this backend has CR170's routes at all.
  ///
  /// Starts **false** and is only raised by a successful read. The asymmetry is
  /// the point: with the controls hidden a user simply does not have the
  /// feature, whereas showing an order-type picker against a pre-CR170 backend
  /// would send `order_type=limit` into `sim_engine`'s
  /// `fill_price = mark if MARKET else (limit_price or mark)` — which does not
  /// rest anything. It fills, instantly, at whatever price they typed. A
  /// control that quietly does something else with real money is the failure
  /// CR040 exists for.
  final bool restingOrdersSupported;

  final bool loading;
  final bool submitting;
  final SimSubmitResult? lastSubmit;
  final String? error;

  List<SimRestingOrder> get liveRestingOrders =>
      [for (final o in restingOrders) if (o.isLive) o];

  List<SimRestingOrder> get settledRestingOrders =>
      [for (final o in restingOrders) if (!o.isLive) o];

  SimState copyWith({
    SimPortfolio? portfolio,
    List<SimTrade>? trades,
    List<SimRestingOrder>? restingOrders,
    bool? restingOrdersSupported,
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
      restingOrders: restingOrders ?? this.restingOrders,
      restingOrdersSupported:
          restingOrdersSupported ?? this.restingOrdersSupported,
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
      final book = await _loadRestingOrders(api, userId);
      state = state.copyWith(
        portfolio: portfolio,
        trades: trades,
        restingOrders: book.orders,
        restingOrdersSupported: book.supported,
        loading: false,
      );
    } catch (e) {
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'load your portfolio'));
    }
  }

  /// The capability probe. A failure here never fails the refresh — the
  /// portfolio, the holdings and the trades are the screen, and losing all of
  /// them because an optional book is unreachable would be a worse outcome than
  /// not showing the book.
  ///
  /// **Any failure resolves to "unsupported", not just a 404.** The two states
  /// are genuinely different — one backend has no route, another has one and is
  /// unwell — but the consequence of guessing wrong in the *permissive*
  /// direction is a live order-type control talking to a `/submit` that fills
  /// instantly at the typed price. There is no reading of that trade-off where
  /// the optimistic default wins, so the pessimistic one is not a fallback, it
  /// is the rule.
  Future<({List<SimRestingOrder> orders, bool supported})> _loadRestingOrders(
      ApiClient api, String userId) async {
    try {
      return (orders: await api.simRestingOrders(userId), supported: true);
    } catch (_) {
      return (orders: const <SimRestingOrder>[], supported: false);
    }
  }

  Future<SimSubmitResult?> submit({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
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
        // CR170 §9 — `ApiClient.simSubmit` has serialised `order_type` and
        // `limit_price` since it was written, and this method silently dropped
        // both. A parameter that exists at one layer and evaporates at the next
        // is the reason nothing above could ever have placed a limit order.
        orderType: orderType.wire,
        limitPrice: limitPrice,
        triggerPrice: triggerPrice,
        tif: orderType.canRest ? tif.wire : null,
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
      state = state.copyWith(
          submitting: false,
          error: friendlyError(e, action: 'place that trade'));
      return null;
    }
  }

  // CR188 slice 2 — `closeTrade` removed. It wrapped
  // `POST /v1/sim/trades/{user}/close`, the market-only exit behind CLOSE
  // POSITION and the `x` on a trade row, and both of those are gone: selling is
  // one control on the position, through the ticket, reaching every order type.
  // The route still exists server-side; nothing in this app calls it, and a
  // dormant wrapper here is a second exit one line away from returning.

  /// CR170 — pull a resting order, and report **the server's** verdict.
  ///
  /// Returns null when the call itself failed; otherwise the result may well be
  /// `cancelled: false` with a terminal state, because a cancel can lose a race
  /// with the sweep. Reporting a success we did not get is how the games lane's
  /// `status ?? 'filled'` defect shipped.
  Future<RestingOrderCancelResult?> cancelRestingOrder(String orderId) async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final result = await api.simCancelRestingOrder(userId, orderId);
      await refresh();
      return result;
    } catch (e) {
      state = state.copyWith(
          error: friendlyError(e, action: 'cancel that order'));
      return null;
    }
  }

  Future<void> reset() async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.simResetPortfolio(userId);
      await refresh();
    } catch (e) {
      state = state.copyWith(
          error: friendlyError(e, action: 'reset your portfolio'));
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

/// CR026 — sector-allocation donut + concentration-compliance feed for the
/// Portfolio screen. Own provider (not folded into SimState) since it's a
/// distinct read-only endpoint the holdings list doesn't otherwise need.
final sectorAllocationProvider =
    FutureProvider.autoDispose<SectorAllocation>((ref) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.sectorAllocation(userId);
});

/// CR109 slice 1 — equity-curve feed for the Portfolio screen's training
/// portfolio. Own provider (not folded into SimState) for the same reason as
/// [sectorAllocationProvider]: a distinct read-only endpoint the holdings
/// list doesn't otherwise need.
final portfolioHistoryProvider =
    FutureProvider.autoDispose<SimPortfolioHistory>((ref) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.simPortfolioHistory(userId);
});
