/// Alpaca paper trading data models (AT:R45; reworked CR202).
///
/// CR202 moved the credential to the device, so these are now parsed from
/// **Alpaca's own JSON** rather than from an AMI backend response that had
/// already coerced the types. Alpaca reports every monetary field and quantity
/// as a *string* (`"cash": "12450.32"`), so parsing must accept both a string
/// and a number — the previous `as num` cast would have thrown on every real
/// response.
///
/// AlpacaPortfolio — paper account summary (cash, equity, buying power).
/// AlpacaPosition — one open paper position.
///
/// Link status is no longer a model: it is simply whether the device holds a
/// credential (see AlpacaCredentialStore.isLinked).
library;

/// Tolerant numeric parse: Alpaca sends strings, our own tests send numbers,
/// and a missing/garbage field reads as 0 rather than throwing — a malformed
/// single field should not blank the whole panel.
double alpacaNum(dynamic v) {
  if (v == null) return 0;
  if (v is num) return v.toDouble();
  return double.tryParse(v.toString()) ?? 0;
}

class AlpacaPortfolio {
  const AlpacaPortfolio({
    required this.cash,
    required this.portfolioValue,
    required this.equity,
    required this.buyingPower,
  });

  final double cash;
  final double portfolioValue;
  final double equity;
  final double buyingPower;

  factory AlpacaPortfolio.fromJson(Map<String, dynamic> j) => AlpacaPortfolio(
        cash: alpacaNum(j['cash']),
        portfolioValue: alpacaNum(j['portfolio_value']),
        equity: alpacaNum(j['equity']),
        buyingPower: alpacaNum(j['buying_power']),
      );
}

class AlpacaPosition {
  const AlpacaPosition({
    required this.symbol,
    required this.qty,
    required this.marketValue,
    required this.unrealizedPl,
  });

  final String symbol;
  final double qty;
  final double marketValue;
  final double unrealizedPl;

  factory AlpacaPosition.fromJson(Map<String, dynamic> j) => AlpacaPosition(
        symbol: (j['symbol'] ?? '') as String,
        qty: alpacaNum(j['qty']),
        marketValue: alpacaNum(j['market_value']),
        unrealizedPl: alpacaNum(j['unrealized_pl']),
      );

  /// The upload shape the backend accepts (`schemas/alpaca.AlpacaPositionIn`).
  Map<String, dynamic> toWireJson() => {
        'symbol': symbol,
        'qty': qty,
        'market_value': marketValue,
        'unrealized_pl': unrealizedPl,
      };
}

/// One Alpaca paper order, as placed by `AlpacaClient.submitOrder` (CR227).
///
/// Market orders only (v1) — see CR227's Non-goals. Parsed the same
/// tolerant way as the other models here: Alpaca returns `filled_qty` as a
/// string, and an order accepted-but-not-yet-filled reports a null fill
/// price, which should read as "not yet filled" rather than throw.
class AlpacaOrder {
  const AlpacaOrder({
    required this.id,
    required this.symbol,
    required this.side,
    required this.qty,
    required this.status,
    this.filledAvgPrice,
  });

  final String id;
  final String symbol;
  final String side;
  final double qty;
  final String status;
  final double? filledAvgPrice;

  factory AlpacaOrder.fromJson(Map<String, dynamic> j) => AlpacaOrder(
        id: (j['id'] ?? '') as String,
        symbol: (j['symbol'] ?? '') as String,
        side: (j['side'] ?? '') as String,
        qty: alpacaNum(j['qty']),
        status: (j['status'] ?? '') as String,
        filledAvgPrice:
            j['filled_avg_price'] == null ? null : alpacaNum(j['filled_avg_price']),
      );
}

/// What the device sends with a Room convene / 1-on-1 turn so the agents can
/// see the linked account. Values only — the backend owns the layout of the
/// block that reaches the prompt.
class AlpacaSnapshot {
  const AlpacaSnapshot({required this.portfolio, required this.positions});

  final AlpacaPortfolio portfolio;
  final List<AlpacaPosition> positions;

  /// Alpaca's position cap on our side mirrors the backend's MAX_POSITIONS —
  /// sending more would be rejected wholesale, losing the overlay entirely, so
  /// the largest positions are kept and the tail is dropped.
  static const int maxPositions = 100;

  Map<String, dynamic> toWireJson() {
    final sorted = [...positions]
      ..sort((a, b) => b.marketValue.abs().compareTo(a.marketValue.abs()));
    return {
      'cash': portfolio.cash,
      'portfolio_value': portfolio.portfolioValue,
      'buying_power': portfolio.buyingPower,
      'positions': sorted.take(maxPositions).map((p) => p.toWireJson()).toList(),
    };
  }

  /// DEF419 — the `AccountSnapshotIn` shape `POST /v1/sim/preview`'s `account`
  /// field expects (`backend/app/schemas/alpaca.py`): `kind`/`equity`/`cash`/
  /// `positions[{ticker, qty, market_value}]`. Deliberately NOT [toWireJson]
  /// above — that method serialises the Room-overlay `AlpacaSnapshotIn` shape
  /// (`portfolio_value`/`buying_power`, `symbol`/`unrealized_pl` on each
  /// position), a different wire contract for a different endpoint. Mixing
  /// the two up would 422 on the field names alone (`extra="forbid"` on both
  /// schemas), which is the loud failure CR040 asks for over a silent
  /// mismatch — but there is no reason to invite it when the two are this
  /// easy to keep apart by having one method per contract.
  ///
  /// A negative `qty` (a short Alpaca position) is dropped rather than sent
  /// negative: `AccountPositionIn.qty` is bounded `ge=0` server-side (DEF419's
  /// schema — shorts are out of scope for the account-snapshot path, same as
  /// the sim engine's own `shorts=None` on this branch), so sending one would
  /// 422 the whole preview over one position the mandate check does not model
  /// anyway.
  Map<String, dynamic> toMandateSnapshotJson() {
    final sorted = [...positions]
      ..sort((a, b) => b.marketValue.abs().compareTo(a.marketValue.abs()));
    return {
      'kind': 'alpaca_paper',
      'equity': portfolio.equity,
      'cash': portfolio.cash,
      'positions': sorted
          .take(maxPositions)
          .where((p) => p.qty >= 0)
          .map((p) => {
                'ticker': p.symbol,
                'qty': p.qty,
                'market_value': p.marketValue,
              })
          .toList(),
    };
  }
}
