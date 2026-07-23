/// Sim Trading — client-side models.
/// Mirrors backend/app/api/sim.py + schemas/trade.py.
library;

import 'package:ami_trade/models/sharia.dart';

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

/// One OHLCV bar from `GET /v1/sim/history`. `t` is Unix epoch seconds (UTC).
class SimCandle {
  const SimCandle({
    required this.t,
    required this.o,
    required this.h,
    required this.l,
    required this.c,
    required this.v,
  });

  final int t;
  final double o;
  final double h;
  final double l;
  final double c;
  final double v;

  DateTime get dateTime => DateTime.fromMillisecondsSinceEpoch(t * 1000, isUtc: true);

  factory SimCandle.fromJson(Map<String, dynamic> j) => SimCandle(
        t: (j['t'] as num).toInt(),
        o: (j['o'] as num).toDouble(),
        h: (j['h'] as num).toDouble(),
        l: (j['l'] as num).toDouble(),
        c: (j['c'] as num).toDouble(),
        v: (j['v'] as num).toDouble(),
      );
}

/// Chart-history payload: a ticker's OHLCV bars for a given period.
/// `source` mirrors Quote.source — drives a LIVE / MOCK badge on the chart.
class SimHistory {
  const SimHistory({
    required this.ticker,
    required this.period,
    required this.source,
    required this.candles,
  });

  final String ticker;
  final String period;
  final String source;
  final List<SimCandle> candles;

  bool get isLivePrice => source != 'mock_walk' && source != 'unavailable';

  factory SimHistory.fromJson(Map<String, dynamic> j) => SimHistory(
        ticker: j['ticker'] as String,
        period: j['period'] as String,
        source: j['source'] as String? ?? 'unknown',
        candles: ((j['candles'] as List?) ?? const [])
            .map((c) => SimCandle.fromJson(c as Map<String, dynamic>))
            .toList(),
      );
}

class SimSubmitResult {
  const SimSubmitResult({
    required this.ok,
    this.trade,
    this.violations = const [],
    this.blockedBy,
    this.shariaVerdict,
  });

  final bool ok;
  final SimTrade? trade;
  final List<String> violations;
  final String? blockedBy;

  /// CR069: the sourced Sharia verdict with its provenance, when the halal
  /// flag is on. Read on BOTH branches — a permitted PASS/UNKNOWN trade carries
  /// it too, because a permitted unknown that says nothing is a silent pass on
  /// an observance decision (G3). Null when the flag is off, and null against a
  /// backend that does not yet serialize the field.
  final ShariaVerdict? shariaVerdict;

  factory SimSubmitResult.fromJson(Map<String, dynamic> j) {
    // Present on both branches: /submit returns {ok, trade} on success and
    // {ok, compliance} on rejection, and the verdict may ride on either.
    final compliance =
        (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {};
    final verdict = ShariaVerdict.fromJson(
        (compliance['sharia_verdict'] as Map?)?.cast<String, dynamic>());
    if ((j['ok'] as bool?) == true) {
      return SimSubmitResult(
        ok: true,
        trade: SimTrade.fromJson(j['trade'] as Map<String, dynamic>),
        shariaVerdict: verdict,
      );
    }
    return SimSubmitResult(
      ok: false,
      violations: ((compliance['violations'] as List?) ?? const []).cast<String>(),
      blockedBy: compliance['blocked_by'] as String?,
      shariaVerdict: verdict,
    );
  }
}

/// One news article for a ticker. Returned by GET /v1/sim/news/{ticker}.
class SimNewsArticle {
  const SimNewsArticle({
    required this.title,
    required this.link,
    required this.publisher,
    required this.publishedAt,
  });

  final String title;
  final String link;
  final String publisher;
  final int publishedAt; // Unix epoch seconds

  factory SimNewsArticle.fromJson(Map<String, dynamic> j) => SimNewsArticle(
        title: j['title'] as String? ?? '',
        link: j['link'] as String? ?? '',
        publisher: j['publisher'] as String? ?? '',
        publishedAt: j['published_at'] as int? ?? 0,
      );
}

/// News payload returned by GET /v1/sim/news/{ticker}.
class SimNews {
  const SimNews({
    required this.ticker,
    required this.source,
    required this.articles,
  });

  final String ticker;
  final String source;
  final List<SimNewsArticle> articles;

  factory SimNews.fromJson(Map<String, dynamic> j) => SimNews(
        ticker: j['ticker'] as String,
        source: j['source'] as String? ?? 'unknown',
        articles: ((j['articles'] as List?) ?? const [])
            .map((a) => SimNewsArticle.fromJson(a as Map<String, dynamic>))
            .toList(),
      );
}

/// Upcoming earnings window within 90 days. Returned by GET /v1/sim/earnings/{ticker}.
/// All fields are null when no earnings date is announced within the window.
class SimEarnings {
  const SimEarnings({
    required this.ticker,
    required this.source,
    this.earningsDate,
    this.quarter,
    this.epsEstimate,
  });

  final String ticker;
  final String source;
  final String? earningsDate; // "YYYY-MM-DD"
  final String? quarter;      // "Q1"–"Q4"
  final double? epsEstimate;

  bool get hasData => earningsDate != null;

  factory SimEarnings.fromJson(Map<String, dynamic> j) => SimEarnings(
        ticker: j['ticker'] as String,
        source: j['source'] as String? ?? 'unknown',
        earningsDate: j['earnings_date'] as String?,
        quarter: j['quarter'] as String?,
        epsEstimate: (j['eps_estimate'] as num?)?.toDouble(),
      );
}
