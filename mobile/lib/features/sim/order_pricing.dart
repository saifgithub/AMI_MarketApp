/// CR170 Rule 1 — whether an order rests or fills now, as pure client logic.
///
/// This mirrors the backend's `trading_math/order_pricing.py`, and mirroring is
/// a risk worth naming: two implementations of one rule is the DEF098 shape,
/// and the one that moves money is the server's. So the split of authority is
/// explicit and one-directional:
///
///  - **This module predicts.** It exists for the ticket's live hint — *"rests
///    until NVDA falls to $90.00"* versus *"fills now — already through the
///    market"* — which CR170 §9 calls the highest-value element in the feature,
///    because without it a resting order reads as a broken button.
///  - **The server decides.** `POST /v1/sim/submit` returns `resting` explicitly
///    on every branch (§8), and the sheet reports *that*, never this. If the two
///    ever disagree, the user is told the truth on the same tap — a wrong hint
///    costs a moment of surprise, not a wrong ledger.
///
/// Nothing here reads a quote, a provider or a clock. Rule 2 (fill price) is
/// deliberately **absent**: the client has no business predicting a price the
/// server books, and the CR is explicit that the pricing rule is internal and
/// never surfaced.
library;

/// Wire values match `OrderType` in `backend/app/schemas/sim.py`.
enum SimOrderType { market, limit, stop, stopLimit, unknown }

extension SimOrderTypeX on SimOrderType {
  String get wire => switch (this) {
        SimOrderType.market => 'market',
        SimOrderType.limit => 'limit',
        SimOrderType.stop => 'stop',
        SimOrderType.stopLimit => 'stop_limit',
        SimOrderType.unknown => 'unknown',
      };

  /// A market order never rests.
  bool get canRest => this != SimOrderType.market && this != SimOrderType.unknown;

  bool get needsTriggerPrice =>
      this == SimOrderType.stop || this == SimOrderType.stopLimit;

  bool get needsLimitPrice =>
      this == SimOrderType.limit || this == SimOrderType.stopLimit;
}

/// An order type this build does not recognise resolves to [SimOrderType
/// .unknown] rather than to `market` — the cheapest-looking fallback is the one
/// that would quietly turn somebody's resting order into an immediate fill in
/// the UI's account of it (DEF210).
SimOrderType simOrderTypeFromWire(String? s) => switch (s) {
      'market' => SimOrderType.market,
      'limit' => SimOrderType.limit,
      'stop' => SimOrderType.stop,
      'stop_limit' => SimOrderType.stopLimit,
      _ => SimOrderType.unknown,
    };

/// Time in force. `expires_at` is always a **session** close, never a local
/// calendar boundary — Saiful: *"our 'day' should be the trading day of the
/// market, not the local time day."* The client only names the choice; the
/// server computes the timestamp.
enum SimOrderTif { day, gtd30, gtd90, unknown }

extension SimOrderTifX on SimOrderTif {
  String get wire => switch (this) {
        SimOrderTif.day => 'day',
        SimOrderTif.gtd30 => 'gtd_30',
        SimOrderTif.gtd90 => 'gtd_90',
        SimOrderTif.unknown => 'unknown',
      };
}

SimOrderTif simOrderTifFromWire(String? s) => switch (s) {
      'day' => SimOrderTif.day,
      'gtd_30' => SimOrderTif.gtd30,
      'gtd_90' => SimOrderTif.gtd90,
      _ => SimOrderTif.unknown,
    };

/// Which side of the market the order waits on.
///
/// Note the diagonal: a buy limit and a sell stop are the **same comparison**,
/// as are a buy stop and a sell limit. Two predicates cover four orders, which
/// is why this returns a direction instead of switching on four cases.
///
/// |          | rests **below** | rests **above** |
/// |----------|-----------------|-----------------|
/// | **BUY**  | buy limit — buy the dip | buy stop — breakout entry |
/// | **SELL** | sell stop — stop-loss   | sell limit — take profit  |
bool restsBelow({required String side, required SimOrderType orderType}) {
  final buy = side.toLowerCase() == 'buy';
  if (buy) return orderType == SimOrderType.limit;
  return orderType == SimOrderType.stop || orderType == SimOrderType.stopLimit;
}

/// The price the order is named by: the limit for a LIMIT, the trigger for a
/// STOP or STOP_LIMIT. Null when the required field has not been typed yet.
double? namedPriceFor(
  SimOrderType orderType, {
  double? triggerPrice,
  double? limitPrice,
}) =>
    switch (orderType) {
      SimOrderType.limit => limitPrice,
      SimOrderType.stop || SimOrderType.stopLimit => triggerPrice,
      _ => null,
    };

/// **Inclusive at the boundary**, matching `evaluate_outcomes`' existing
/// `price <= stop` / `price >= target`. Consistency with the bracket evaluator
/// beats venue realism here: the two run in the same sweep, and a user
/// comparing them must not find them disagreeing at the exact touch.
bool isTriggered({
  required String side,
  required SimOrderType orderType,
  required double named,
  required double mark,
}) =>
    restsBelow(side: side, orderType: orderType) ? mark <= named : mark >= named;

/// What the ticket should tell the user this order will do.
///
/// `null` means "not enough typed yet to say anything" — which renders as no
/// hint at all rather than as a guess. A hint that fills itself in from
/// incomplete input is worse than a blank line, because the user reads it.
enum OrderIntent { fillsNow, rests }

OrderIntent? predictIntent({
  required String side,
  required SimOrderType orderType,
  required double? triggerPrice,
  required double? limitPrice,
  required double? mark,
}) {
  if (orderType == SimOrderType.market) return OrderIntent.fillsNow;
  if (orderType == SimOrderType.unknown) return null;
  final named =
      namedPriceFor(orderType, triggerPrice: triggerPrice, limitPrice: limitPrice);
  if (named == null || named <= 0) return null;
  if (mark == null || mark <= 0) return null;
  // A marketable order — a buy limit at or above the market, a sell limit at or
  // below it — is already through the market and fills exactly like a market
  // order: same path, same price, same compliance ruling.
  return isTriggered(side: side, orderType: orderType, named: named, mark: mark)
      ? OrderIntent.fillsNow
      : OrderIntent.rests;
}
