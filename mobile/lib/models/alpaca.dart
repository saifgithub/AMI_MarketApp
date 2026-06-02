/// Alpaca paper trading data models (AT:R45).
///
/// AlpacaStatus — link status for the Settings row and portfolio visibility guard.
/// AlpacaPortfolio — paper account summary (cash, equity, buying power).
/// AlpacaPosition — one open paper position.
library;

class AlpacaStatus {
  const AlpacaStatus({required this.linked, this.linkedAt});

  final bool linked;
  final DateTime? linkedAt;

  factory AlpacaStatus.fromJson(Map<String, dynamic> j) => AlpacaStatus(
        linked: j['linked'] as bool,
        linkedAt: j['linked_at'] != null ? DateTime.parse(j['linked_at'] as String) : null,
      );
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
        cash: (j['cash'] as num).toDouble(),
        portfolioValue: (j['portfolio_value'] as num).toDouble(),
        equity: (j['equity'] as num).toDouble(),
        buyingPower: (j['buying_power'] as num).toDouble(),
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
        symbol: j['symbol'] as String,
        qty: (j['qty'] as num).toDouble(),
        marketValue: (j['market_value'] as num).toDouble(),
        unrealizedPl: (j['unrealized_pl'] as num).toDouble(),
      );
}
