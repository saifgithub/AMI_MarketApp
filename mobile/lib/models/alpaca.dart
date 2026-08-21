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
}
