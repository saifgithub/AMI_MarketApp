/// Sim Trading — client-side models.
/// Mirrors backend/app/api/sim.py + schemas/trade.py.
library;

class SimHolding {
  const SimHolding({
    required this.ticker,
    required this.quantity,
    required this.avgCost,
    required this.mark,
    required this.value,
    required this.unrealisedPnl,
    required this.openedAt,
  });

  final String ticker;
  final double quantity;
  final double avgCost;
  final double mark;
  final double value;
  final double unrealisedPnl;
  final DateTime openedAt;

  factory SimHolding.fromJson(Map<String, dynamic> j) {
    return SimHolding(
      ticker: j['ticker'] as String,
      quantity: (j['quantity'] as num).toDouble(),
      avgCost: (j['avg_cost'] as num).toDouble(),
      mark: (j['mark'] as num).toDouble(),
      value: (j['value'] as num).toDouble(),
      unrealisedPnl: (j['unrealised_pnl'] as num).toDouble(),
      openedAt: DateTime.parse(j['opened_at'] as String),
    );
  }
}

class SimPortfolio {
  const SimPortfolio({
    required this.userId,
    required this.portfolioId,
    required this.startingCapital,
    required this.currentCash,
    required this.holdings,
    required this.totalValue,
    required this.drawdownPct,
    this.priceSource = 'mock_walk',
  });

  final String userId;
  final String portfolioId;
  final double startingCapital;
  final double currentCash;
  final List<SimHolding> holdings;
  final double totalValue;
  final double drawdownPct;
  // Truthful leaf provider name from the backend — what actually
  // served the most recent quote, not a stack name. Possible values:
  // "yfinance" / "yahoo" (live), "mock_walk" (deterministic walk),
  // "unavailable" (defensive floor when every provider failed).
  final String priceSource;

  double get totalPnl => totalValue - startingCapital;
  double get pnlPct =>
      startingCapital == 0 ? 0 : (totalPnl / startingCapital) * 100;

  /// True when the backend served real prices (vs the mock walk or
  /// the unavailable floor). Negative check so adding a new live
  /// provider (e.g. a paid market-data vendor at Beta) doesn't
  /// require a Flutter rebuild to flip the pill.
  bool get isLivePrice =>
      priceSource != 'mock_walk' && priceSource != 'unavailable';

  factory SimPortfolio.fromJson(Map<String, dynamic> j) {
    return SimPortfolio(
      userId: j['user_id'] as String,
      portfolioId: j['portfolio_id'] as String,
      startingCapital: (j['starting_capital'] as num).toDouble(),
      currentCash: (j['current_cash'] as num).toDouble(),
      holdings: ((j['holdings'] as List?) ?? const [])
          .map((h) => SimHolding.fromJson(h as Map<String, dynamic>))
          .toList(),
      totalValue: (j['total_value'] as num).toDouble(),
      drawdownPct: (j['drawdown_pct'] as num).toDouble(),
      priceSource: (j['price_source'] as String?) ?? 'mock_walk',
    );
  }
}

class SimTrade {
  const SimTrade({
    required this.id,
    required this.userId,
    required this.ticker,
    required this.side,
    required this.quantity,
    required this.entryPrice,
    required this.openedAt,
    required this.status,
    required this.realisedPnl,
    this.stop,
    this.target,
    this.horizonDays,
    this.closedAt,
    this.closedPrice,
    this.verdictRef,
  });

  final String id;
  final String userId;
  final String ticker;
  final String side; // 'buy' | 'sell'
  final double quantity;
  final double entryPrice;
  final double? stop;
  final double? target;
  final int? horizonDays;
  final DateTime openedAt;
  final DateTime? closedAt;
  final double? closedPrice;
  /// 'open' | 'won' | 'lost' | 'closed'
  final String status;
  final String? verdictRef;
  final double realisedPnl;

  bool get isOpen => status == 'open';

  factory SimTrade.fromJson(Map<String, dynamic> j) {
    return SimTrade(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      ticker: j['ticker'] as String,
      side: j['side'] as String,
      quantity: (j['quantity'] as num).toDouble(),
      entryPrice: (j['entry_price'] as num).toDouble(),
      stop: (j['stop'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      horizonDays: (j['horizon_days'] as num?)?.toInt(),
      openedAt: DateTime.parse(j['opened_at'] as String),
      closedAt: j['closed_at'] == null ? null : DateTime.parse(j['closed_at'] as String),
      closedPrice: (j['closed_price'] as num?)?.toDouble(),
      status: j['status'] as String? ?? 'open',
      verdictRef: j['verdict_ref'] as String?,
      realisedPnl: (j['realised_pnl'] as num? ?? 0).toDouble(),
    );
  }
}

class SimSubmitResult {
  const SimSubmitResult({
    required this.ok,
    this.trade,
    this.violations = const [],
    this.blockedBy,
  });

  final bool ok;
  final SimTrade? trade;
  final List<String> violations;
  final String? blockedBy;

  factory SimSubmitResult.fromJson(Map<String, dynamic> j) {
    if ((j['ok'] as bool?) == true) {
      return SimSubmitResult(
        ok: true,
        trade: SimTrade.fromJson(j['trade'] as Map<String, dynamic>),
      );
    }
    final compliance = (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {};
    return SimSubmitResult(
      ok: false,
      violations: ((compliance['violations'] as List?) ?? const []).cast<String>(),
      blockedBy: compliance['blocked_by'] as String?,
    );
  }
}
