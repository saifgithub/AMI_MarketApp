/// CR170 — one row of the resting-order book, client side.
///
/// A near-copy of `GameQueuedOrder` (`models/games.dart:393`) by design: CR170
/// §1 says to steal the games lane's vocabulary wherever the meaning is the
/// same, so a later convergence is mechanical rather than a translation.
///
/// **The one invariant the copy must carry across is `cancelReason`.** A
/// non-null reason always means *the system refused*; a user cancel leaves it
/// null. That is how this screen distinguishes "you cancelled this" from "this
/// was taken away from you", and the games lane learned it from a defect whose
/// own docstring records the cost — *"from the player's side the order simply
/// VANISHED overnight."*
///
/// Seven states against the games lane's three, for the same reason: two of the
/// extras are ones games retro-fitted behind `cancel_reason IS NOT NULL`.
library;

import 'package:ami_trade/features/sim/order_pricing.dart';

enum RestingOrderState {
  /// Resting, not triggered.
  working,

  /// A stop-limit whose trigger fired; now evaluating as a limit.
  triggered,

  /// Claimed by a sweep, fill in flight. Deliberately visible: a crash between
  /// the fill and the stamp leaves the order here rather than back in
  /// `working`, where it would be filled a second time.
  filling,

  /// Done. `filledTradeId`, `fillPrice`, `filledAt` set.
  filled,

  /// **The user** did it. `cancelReason` stays null.
  cancelled,

  /// Time in force elapsed untriggered.
  expired,

  /// Triggered, then the fill or the fill-time compliance re-check refused it.
  rejected,

  /// A state this build does not know. Rendered as its own thing, never folded
  /// into `working` — an order shown as live when the server has retired it is
  /// the one error the user cannot recover from (DEF210).
  unknown,
}

RestingOrderState _stateFromWire(String? s) => switch (s) {
      'working' => RestingOrderState.working,
      'triggered' => RestingOrderState.triggered,
      'filling' => RestingOrderState.filling,
      'filled' => RestingOrderState.filled,
      'cancelled' => RestingOrderState.cancelled,
      'expired' => RestingOrderState.expired,
      'rejected' => RestingOrderState.rejected,
      _ => RestingOrderState.unknown,
    };

class SimRestingOrder {
  const SimRestingOrder({
    required this.id,
    required this.ticker,
    required this.side,
    required this.quantity,
    required this.orderType,
    required this.state,
    required this.tif,
    this.triggerPrice,
    this.limitPrice,
    this.stop,
    this.target,
    this.expiresAt,
    this.placedAt,
    this.filledAt,
    this.fillPrice,
    this.filledTradeId,
    this.cancelReason,
    this.lastSeenPrice,
    this.lastCheckedAt,
    this.distancePct,
    this.retiredAt,
  });

  final String id;
  final String ticker;

  /// `buy` | `sell`.
  final String side;
  final double quantity;
  final SimOrderType orderType;
  final RestingOrderState state;
  final SimOrderTif tif;

  final double? triggerPrice;
  final double? limitPrice;
  final double? stop;
  final double? target;

  final DateTime? expiresAt;
  final DateTime? placedAt;
  final DateTime? filledAt;
  final double? fillPrice;
  final String? filledTradeId;

  /// Non-null ⇒ **the system** refused or retired this order, and this sentence
  /// is why. Null on a user cancel.
  final String? cancelReason;

  /// The mark the last sweep saw. Null before the first sweep, which renders as
  /// "waiting for the first check" rather than as a zero.
  final double? lastSeenPrice;
  final DateTime? lastCheckedAt;
  final double? distancePct;

  /// DEF309 — when the order LEFT the book, for any of its four exits. Null on
  /// a live order, and null from a server that predates the column, which the
  /// card renders as no date rather than as a wrong one.
  final DateTime? retiredAt;

  /// Still in the book — the user can cancel it, and it can still cost money.
  bool get isLive =>
      state == RestingOrderState.working ||
      state == RestingOrderState.triggered ||
      state == RestingOrderState.filling;

  /// A live order the user is still allowed to pull. `filling` is excluded:
  /// the sweep has claimed it and a cancel would race a money-moving operation
  /// whose outcome is already unknown.
  bool get isCancellable =>
      state == RestingOrderState.working ||
      state == RestingOrderState.triggered;

  /// The price this order is named by — what the user typed.
  double? get namedPrice => namedPriceFor(orderType,
      triggerPrice: triggerPrice, limitPrice: limitPrice);

  static DateTime? _dt(Object? v) =>
      v is String ? DateTime.tryParse(v)?.toLocal() : null;

  factory SimRestingOrder.fromJson(Map<String, dynamic> j) {
    return SimRestingOrder(
      id: (j['id'] ?? '').toString(),
      ticker: (j['ticker'] as String? ?? '').toUpperCase(),
      side: (j['side'] as String? ?? 'buy').toLowerCase(),
      quantity: (j['quantity'] as num?)?.toDouble() ?? 0,
      orderType: simOrderTypeFromWire(j['order_type'] as String?),
      state: _stateFromWire(j['state'] as String?),
      tif: simOrderTifFromWire(j['tif'] as String?),
      triggerPrice: (j['trigger_price'] as num?)?.toDouble(),
      limitPrice: (j['limit_price'] as num?)?.toDouble(),
      stop: (j['stop'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      expiresAt: _dt(j['expires_at']),
      placedAt: _dt(j['placed_at']),
      filledAt: _dt(j['filled_at']),
      fillPrice: (j['fill_price'] as num?)?.toDouble(),
      filledTradeId: j['filled_trade_id']?.toString(),
      cancelReason: j['cancel_reason'] as String?,
      lastSeenPrice: (j['last_seen_price'] as num?)?.toDouble(),
      lastCheckedAt: _dt(j['last_checked_at']),
      distancePct: (j['distance_pct'] as num?)?.toDouble(),
      retiredAt: _dt(j['retired_at']),
    );
  }
}

/// The server's verdict on a cancel.
///
/// Carries `cancelled` **and** the resulting state, because a cancel can lose a
/// race with the sweep. The games lane shipped `status ?? 'filled'` in build 74
/// and had to fix it; this one is explicit from the start.
class RestingOrderCancelResult {
  const RestingOrderCancelResult({required this.cancelled, required this.state});

  final bool cancelled;
  final RestingOrderState state;

  factory RestingOrderCancelResult.fromJson(Map<String, dynamic> j) =>
      RestingOrderCancelResult(
        cancelled: (j['cancelled'] as bool?) ?? false,
        state: _stateFromWire(j['state'] as String?),
      );
}
