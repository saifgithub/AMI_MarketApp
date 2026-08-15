/// Sim Trading — client-side models.
/// Mirrors backend/app/api/sim.py + schemas/trade.py.
library;

import 'package:ami_trade/models/sharia.dart';
import 'package:ami_trade/models/sim_resting_order.dart';

class SimHolding {
  const SimHolding({
    required this.ticker,
    required this.quantity,
    required this.avgCost,
    required this.mark,
    required this.value,
    required this.unrealisedPnl,
    required this.openedAt,
    this.stop,
    this.target,
  });

  final String ticker;
  final double quantity;
  final double avgCost;
  final double mark;
  final double value;
  final double unrealisedPnl;
  final DateTime openedAt;

  /// CR189 — the POSITION's blended stop/target, weighted by each live lot's
  /// open shares, not any one trade row's. Server-derived off the same
  /// `blended_bracket` the sweep fires on, deliberately: a chip showing a level
  /// nothing acts at is the defect CR189 exists to remove, so the client must
  /// not compute its own. Null means the position is unprotected on that side,
  /// which the tile shows by omitting the chip.
  final double? stop;
  final double? target;

  bool get isProtected => stop != null || target != null;

  /// Distance from the mark to the stop, as a fraction. Null when unprotected.
  double? get stopDistancePct =>
      (stop == null || mark <= 0) ? null : (mark - stop!) / mark;

  factory SimHolding.fromJson(Map<String, dynamic> j) {
    return SimHolding(
      ticker: j['ticker'] as String,
      quantity: (j['quantity'] as num).toDouble(),
      avgCost: (j['avg_cost'] as num).toDouble(),
      mark: (j['mark'] as num).toDouble(),
      value: (j['value'] as num).toDouble(),
      unrealisedPnl: (j['unrealised_pnl'] as num).toDouble(),
      openedAt: DateTime.parse(j['opened_at'] as String),
      stop: (j['stop'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
    );
  }
}

/// CR171 — one OPEN short in the training lane. Mirrors `ShortPositionOut`.
///
/// Deliberately NOT reusing `GameShort`: the two lanes post different
/// collateral (the game posts full notional, training posts 1.50× and is
/// margin-called), so a shared model would have to carry both cash models and
/// every reader would branch on which one applies. The backend keeps them in
/// two tables for exactly this reason.
class SimShort {
  const SimShort({
    required this.id,
    required this.ticker,
    required this.quantity,
    required this.entryPrice,
    required this.mark,
    required this.legValue,
    required this.unrealisedPnl,
    required this.cashPosted,
    required this.collateralPosted,
    required this.borrowRatePct,
    required this.borrowRateSource,
    required this.borrowAccruedTotal,
    required this.maintenanceMargin,
    this.marginRatio,
    this.stop,
    this.target,
    required this.openedAt,
  });

  final String id;
  final String ticker;
  final double quantity;
  final double entryPrice;
  final double mark;

  /// What the position contributes to portfolio value: the cash that left,
  /// plus the move. **Not** a market value — a short has none, and rendering
  /// `quantity × mark` here would show a number that GROWS as the position
  /// goes against the user. Sent by the server; never re-derived here.
  final double legValue;

  /// Positive when the mark is BELOW entry.
  final double unrealisedPnl;

  /// The cash that actually left the balance at open (0.5 × notional under a
  /// 1.50 initial margin) — not the collateral, which is [collateralPosted].
  final double cashPosted;
  final double collateralPosted;

  final double borrowRatePct;

  /// `alpaca` | `short_interest` | `default` — which layer sourced the rate.
  final String borrowRateSource;

  /// What holding this position has cost so far. Invisible in
  /// [unrealisedPnl]: the borrow comes out of cash, not out of the leg.
  final double borrowAccruedTotal;

  /// Null when the server could not compute it (a non-positive mark). A null
  /// renders nothing rather than a stand-in number a user would read as real.
  final double? marginRatio;

  /// The server's own force-close threshold, shipped alongside the ratio. The
  /// client must never carry a second copy of 1.30 — a threshold in two places
  /// drifts, and the drift shows up as the app calling a position safe on the
  /// sweep that closes it (DEF098).
  final double maintenanceMargin;

  /// INVERTED against a long: the stop is ABOVE entry, the target BELOW.
  final double? stop;
  final double? target;
  final DateTime openedAt;

  double get unrealisedPct =>
      cashPosted == 0 ? 0 : (unrealisedPnl / cashPosted) * 100;

  /// Within 15% of the force-close threshold. A warning band, not a second
  /// threshold: the decision itself is always the server's.
  bool get isNearMargin {
    final r = marginRatio;
    return r != null && r < maintenanceMargin * 1.15;
  }

  factory SimShort.fromJson(Map<String, dynamic> j) {
    final entry = (j['entry_price'] as num?)?.toDouble() ?? 0;
    final qty = (j['quantity'] as num?)?.toDouble() ?? 0;
    final mark = (j['mark'] as num?)?.toDouble() ?? entry;
    final cashPosted = (j['cash_posted'] as num?)?.toDouble() ?? 0;
    return SimShort(
      id: j['id'] as String? ?? '',
      ticker: j['ticker'] as String? ?? '',
      quantity: qty,
      entryPrice: entry,
      mark: mark,
      legValue: (j['leg_value'] as num?)?.toDouble() ??
          cashPosted + (entry - mark) * qty,
      unrealisedPnl:
          (j['unrealised_pnl'] as num?)?.toDouble() ?? (entry - mark) * qty,
      cashPosted: cashPosted,
      collateralPosted: (j['collateral_posted'] as num?)?.toDouble() ?? 0,
      borrowRatePct: (j['borrow_rate_pct'] as num?)?.toDouble() ?? 0,
      borrowRateSource: j['borrow_rate_source'] as String? ?? 'default',
      borrowAccruedTotal:
          (j['borrow_accrued_total'] as num?)?.toDouble() ?? 0,
      marginRatio: (j['margin_ratio'] as num?)?.toDouble(),
      maintenanceMargin: (j['maintenance_margin'] as num?)?.toDouble() ?? 1.3,
      stop: (j['stop'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      openedAt: DateTime.tryParse(j['opened_at'] as String? ?? '') ??
          DateTime.now().toUtc(),
    );
  }
}

/// CR171 §7 — a short that closed inside the server's reporting window.
///
/// [closeReason] is the load-bearing field. `margin` means the account took
/// the decision away, and a position that vanished with no such sentence is
/// indistinguishable from a bug — the games lane's *"the order simply
/// VANISHED"* defect, on a much bigger number.
class SimClosedShort {
  const SimClosedShort({
    required this.id,
    required this.ticker,
    required this.quantity,
    required this.entryPrice,
    this.closePrice,
    this.closeReason,
    this.realisedPnl,
    required this.borrowAccruedTotal,
    this.closedAt,
  });

  final String id;
  final String ticker;
  final double quantity;
  final double entryPrice;
  final double? closePrice;

  /// `user` | `margin` | `stop` | `target`
  final String? closeReason;
  final double? realisedPnl;
  final double borrowAccruedTotal;
  final DateTime? closedAt;

  /// The one case the user did not choose.
  bool get wasForced => closeReason == 'margin';

  factory SimClosedShort.fromJson(Map<String, dynamic> j) {
    return SimClosedShort(
      id: j['id'] as String? ?? '',
      ticker: j['ticker'] as String? ?? '',
      quantity: (j['quantity'] as num?)?.toDouble() ?? 0,
      entryPrice: (j['entry_price'] as num?)?.toDouble() ?? 0,
      closePrice: (j['close_price'] as num?)?.toDouble(),
      closeReason: j['close_reason'] as String?,
      realisedPnl: (j['realised_pnl'] as num?)?.toDouble(),
      borrowAccruedTotal:
          (j['borrow_accrued_total'] as num?)?.toDouble() ?? 0,
      closedAt: DateTime.tryParse(j['closed_at'] as String? ?? ''),
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
    this.cashCommitted = 0,
    double? cashAvailable,
    this.restingOrderCount = 0,
    this.sharesCommitted = const {},
    this.shorts = const [],
    this.closedShorts = const [],
  }) : _cashAvailable = cashAvailable;

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

  /// CR170 §6 — cash the live resting book has spoken for. Computed server-side
  /// at read time, never reserved: a reserved-cash debit is indistinguishable
  /// from a loss in the NAV series.
  final double cashCommitted;

  final double? _cashAvailable;

  /// What the ticket must size against.
  ///
  /// **Deliberately NOT clamped at zero**, and that is the one place this
  /// differs from the games lane's identically-named getter. A negative here
  /// is a real, reachable state — five resting buys against one balance, FIFO,
  /// the loser refused at fill — and it is precisely the condition the field
  /// exists to show. The game clamps because a stake cannot go negative; a
  /// training balance over-committed by its own book can.
  double get cashAvailable => _cashAvailable ?? (currentCash - cashCommitted);

  /// True when the book has committed more than the balance holds.
  bool get isOverCommitted => cashAvailable < 0;

  final int restingOrderCount;

  /// Shares per ticker that resting SELL orders have spoken for.
  final Map<String, double> sharesCommitted;

  /// CR171 — open shorts. Empty on every portfolio that has never shorted.
  final List<SimShort> shorts;

  /// CR171 §7 — shorts that closed inside the server's window, newest first.
  final List<SimClosedShort> closedShorts;

  /// Shares of [ticker] a resting sell has already spoken for.
  double sharesCommittedFor(String ticker) =>
      sharesCommitted[ticker.toUpperCase()] ?? 0;

  /// The open short on [ticker], or null. At most one can exist per name.
  SimShort? shortFor(String ticker) {
    final t = ticker.toUpperCase();
    for (final s in shorts) {
      if (s.ticker.toUpperCase() == t) return s;
    }
    return null;
  }

  /// What every open short has cost to hold so far.
  double get borrowAccruedTotal =>
      shorts.fold<double>(0, (a, s) => a + s.borrowAccruedTotal);

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
      cashCommitted: (j['cash_committed'] as num?)?.toDouble() ?? 0,
      // Read the server's own figure when present; the fallback exists only
      // for a backend that predates CR170 §6, where the book is empty anyway.
      cashAvailable: (j['cash_available'] as num?)?.toDouble(),
      restingOrderCount: (j['resting_order_count'] as num?)?.toInt() ?? 0,
      sharesCommitted: ((j['shares_committed'] as Map?) ?? const {}).map(
        (k, v) => MapEntry(
          (k as String).toUpperCase(),
          (v as num).toDouble(),
        ),
      ),
      shorts: ((j['shorts'] as List?) ?? const [])
          .map((s) => SimShort.fromJson(s as Map<String, dynamic>))
          .toList(),
      closedShorts: ((j['closed_shorts'] as List?) ?? const [])
          .map((s) => SimClosedShort.fromJson(s as Map<String, dynamic>))
          .toList(),
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

/// One daily NAV snapshot from `GET /v1/sim/portfolio/{user_id}/history`
/// (CR109 slice 1). `priceSource` rides per point — not just once for the
/// whole series — because a series can cross from live pricing into a mock
/// or stale day and back; CR040 requires the client be able to mark that
/// exact day, not the series as a whole.
class SimPortfolioHistoryPoint {
  const SimPortfolioHistoryPoint({
    required this.asOfDate,
    required this.nav,
    required this.cash,
    required this.priceSource,
    this.capitalEvent,
  });

  final DateTime asOfDate;
  final double nav;
  final double cash;
  /// 'live' | 'mock' | 'stale'. Only 'live' may be drawn as fact — anything
  /// else must be visibly marked on the curve (CR040 / CR134).
  final String priceSource;
  /// 'open' | 'restart' | 'topup' | null — a day capital moved outside of
  /// trading P&L (a fresh account, a reset, a top-up).
  final String? capitalEvent;

  /// True when the point needs no provenance caveat drawn on it.
  ///
  /// `cash` counts as exact, not estimated: a day with no holdings has a NAV
  /// of pure cash, which is known rather than priced. Dashing it would tell
  /// the user a real number was simulated. Only `mock`/`stale` are caveated.
  bool get isLive => priceSource == 'live' || priceSource == 'cash';

  factory SimPortfolioHistoryPoint.fromJson(Map<String, dynamic> j) =>
      SimPortfolioHistoryPoint(
        asOfDate: DateTime.parse(j['as_of_date'] as String),
        nav: (j['nav'] as num).toDouble(),
        cash: (j['cash'] as num).toDouble(),
        priceSource: j['price_source'] as String? ?? 'mock',
        capitalEvent: j['capital_event'] as String?,
      );
}

/// Portfolio equity-curve payload: `GET /v1/sim/portfolio/{user_id}/history`
/// (CR109 slice 1, `PortfolioHistoryResponse` in `backend/app/api/sim.py`).
/// `twrPct` is the time-weighted return over the whole window, chain-linked
/// across any capital events in [points] — computed server-side, never
/// re-derived client-side from raw NAV deltas. The backend sends `null` for
/// `twr_pct` only when `points` has fewer than two entries (nothing to
/// compound); the client never renders it in that case either, so the
/// `?? 0.0` fallback below is never reached with a value a user could read.
class SimPortfolioHistory {
  const SimPortfolioHistory({required this.points, required this.twrPct});

  final List<SimPortfolioHistoryPoint> points;
  final double twrPct;

  factory SimPortfolioHistory.fromJson(Map<String, dynamic> j) {
    return SimPortfolioHistory(
      points: ((j['points'] as List?) ?? const [])
          .map((p) =>
              SimPortfolioHistoryPoint.fromJson(p as Map<String, dynamic>))
          .toList(),
      twrPct: (j['twr_pct'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SimSubmitResult {
  const SimSubmitResult({
    required this.ok,
    this.trade,
    this.violations = const [],
    this.advisories = const [],
    this.blockedBy,
    this.shariaVerdict,
    this.resting = false,
    this.order,
    this.shortAction,
    this.shortTicker,
    this.shortQuantity,
    this.shortRealisedPnl,
  });

  final bool ok;
  final SimTrade? trade;
  final List<String> violations;

  /// CR171 §6 — notices on a trade that **proceeded**. A third state beside
  /// violations, and it is not decoration: Saiful's halal ruling is *"our job
  /// is only to inform… we will put a flag and notice to inform the user, but
  /// we let the trade through"*. An advisory that arrives on the wire and is
  /// never rendered informs nobody, which is CR040's failure exactly — so
  /// anything that reads [violations] must also read this.
  final List<String> advisories;

  final String? blockedBy;

  /// CR170 — the order rested instead of filling. Read from the response's own
  /// `resting` field on **every** branch, never inferred from which of
  /// `trade`/`order` is null: the games lane learned that twice, and an
  /// inference is a second source of truth for a fact the server already
  /// states. Defaults false, so a pre-CR170 backend reads exactly as it always
  /// did.
  final bool resting;

  /// The book row, when [resting].
  final SimRestingOrder? order;

  /// CR069: the sourced Sharia verdict with its provenance, when the halal
  /// flag is on. Read on BOTH branches — a permitted PASS/UNKNOWN trade carries
  /// it too, because a permitted unknown that says nothing is a silent pass on
  /// an observance decision (G3). Null when the flag is off, and null against a
  /// backend that does not yet serialize the field.
  final ShariaVerdict? shariaVerdict;

  /// CR171 — `short_open` | `short_cover`, when the submit moved a short leg.
  ///
  /// A short writes **no trade row** by design (§3: a SELL row would make
  /// every genuine phantom share look accounted for on `def110_backfill`), so
  /// `trade` is null on this branch and `resting` is false. Without this field
  /// the ticket's `resting = result.resting || trade == null` reads a
  /// successful short as a resting order and tells the user it is waiting at
  /// $0.00.
  final String? shortAction;
  final String? shortTicker;
  final double? shortQuantity;

  /// Set on a cover, null on an open.
  final double? shortRealisedPnl;

  bool get isShortOpen => shortAction == 'short_open';
  bool get isShortCover => shortAction == 'short_cover';

  static List<String> _advisories(Map<String, dynamic> compliance) =>
      ((compliance['advisories'] as List?) ?? const []).cast<String>();

  factory SimSubmitResult.fromJson(Map<String, dynamic> j) {
    // Present on both branches: /submit returns {ok, trade} on success and
    // {ok, compliance} on rejection, and the verdict may ride on either.
    final compliance =
        (j['compliance'] as Map?)?.cast<String, dynamic>() ?? const {};
    final verdict = ShariaVerdict.fromJson(
        (compliance['sharia_verdict'] as Map?)?.cast<String, dynamic>());
    if ((j['ok'] as bool?) == true) {
      // CR170 — `trade` is null on a resting response, and the cast below used
      // to be unconditional: `SimTrade.fromJson(j['trade'] as Map<…>)` throws
      // on null before the sheet's own `result.trade!` is ever reached. So the
      // crash the CR locates at `trade_ticket_sheet.dart:247` actually lands
      // one layer earlier, inside the parser, where it surfaces as a generic
      // "couldn't place that trade" over an order the server *did* accept.
      final tradeJson = (j['trade'] as Map?)?.cast<String, dynamic>();
      final orderJson = (j['order'] as Map?)?.cast<String, dynamic>();
      final shortJson = (j['short'] as Map?)?.cast<String, dynamic>();
      return SimSubmitResult(
        ok: true,
        trade: tradeJson == null ? null : SimTrade.fromJson(tradeJson),
        resting: (j['resting'] as bool?) ?? false,
        order: orderJson == null ? null : SimRestingOrder.fromJson(orderJson),
        shariaVerdict: verdict,
        // Read on the OK branch too, and that is the whole point: an advisory
        // only ever rides on a trade that went through.
        advisories: _advisories(compliance),
        shortAction: shortJson?['action'] as String?,
        shortTicker: shortJson?['ticker'] as String?,
        shortQuantity: (shortJson?['quantity'] as num?)?.toDouble(),
        shortRealisedPnl: (shortJson?['realised_pnl'] as num?)?.toDouble(),
      );
    }
    return SimSubmitResult(
      ok: false,
      violations: ((compliance['violations'] as List?) ?? const []).cast<String>(),
      advisories: _advisories(compliance),
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
    this.exDividendDate,
    this.dividendRate,
  });

  final String ticker;
  final String source;
  final String? earningsDate; // "YYYY-MM-DD"
  final String? quarter;      // "Q1"–"Q4"
  final double? epsEstimate;
  // CR030 — null on both means non-payer or outside the announced window.
  final String? exDividendDate; // "YYYY-MM-DD"
  final double? dividendRate;

  bool get hasData => earningsDate != null;

  /// CR030 — the dividend chip renders only when at least one of the two
  /// fields is present; both null means non-payer / no announced window.
  bool get hasDividendData => exDividendDate != null || dividendRate != null;

  factory SimEarnings.fromJson(Map<String, dynamic> j) => SimEarnings(
        ticker: j['ticker'] as String,
        source: j['source'] as String? ?? 'unknown',
        earningsDate: j['earnings_date'] as String?,
        quarter: j['quarter'] as String?,
        epsEstimate: (j['eps_estimate'] as num?)?.toDouble(),
        exDividendDate: j['ex_dividend_date'] as String?,
        dividendRate: (j['dividend_rate'] as num?)?.toDouble(),
      );
}

/// One buy lot's reconstructed FIFO cost-basis picture. Returned inside
/// GET /v1/sim/lots/{user_id}/{ticker} (CR029).
class Lot {
  const Lot({
    required this.entryTradeId,
    required this.entryDate,
    required this.entryPrice,
    required this.quantity,
    required this.quantityOpen,
    required this.quantityClosed,
    required this.realisedPnl,
    this.unrealisedPnl,
    required this.status,
  });

  final String entryTradeId;
  final String entryDate; // ISO 8601
  final double entryPrice;
  final double quantity; // original buy quantity
  final double quantityOpen;
  final double quantityClosed;
  final double realisedPnl;
  // Null when the current price is unknown. A closed lot's unrealised P&L
  // is absent, not zero — never coerce this to 0.0 when rendering.
  final double? unrealisedPnl;
  final String status; // "open" | "partially_closed" | "closed"

  factory Lot.fromJson(Map<String, dynamic> j) => Lot(
        entryTradeId: j['entry_trade_id'] as String,
        entryDate: j['entry_date'] as String,
        entryPrice: (j['entry_price'] as num).toDouble(),
        quantity: (j['quantity'] as num).toDouble(),
        quantityOpen: (j['quantity_open'] as num).toDouble(),
        quantityClosed: (j['quantity_closed'] as num).toDouble(),
        realisedPnl: (j['realised_pnl'] as num).toDouble(),
        unrealisedPnl: (j['unrealised_pnl'] as num?)?.toDouble(),
        status: j['status'] as String,
      );
}

/// Aggregate totals across all lots for a ticker. Unlike a single lot's
/// `unrealisedPnl`, this total is always present — the backend sums with a
/// 0.0 fallback per-lot before returning it.
class LotTotals {
  const LotTotals({
    required this.realisedPnl,
    required this.unrealisedPnl,
    required this.quantityOpen,
  });

  final double realisedPnl;
  final double unrealisedPnl;
  final double quantityOpen;

  factory LotTotals.fromJson(Map<String, dynamic> j) => LotTotals(
        realisedPnl: (j['realised_pnl'] as num).toDouble(),
        unrealisedPnl: (j['unrealised_pnl'] as num).toDouble(),
        quantityOpen: (j['quantity_open'] as num).toDouble(),
      );
}

/// Per-lot cost-basis feed for one held ticker. Returned by
/// GET /v1/sim/lots/{user_id}/{ticker} (CR029).
class HoldingLots {
  const HoldingLots({
    required this.ticker,
    required this.currentPrice,
    required this.priceSource,
    required this.lots,
    required this.totals,
  });

  final String ticker;
  final double currentPrice;
  final String priceSource;
  final List<Lot> lots;
  final LotTotals totals;

  factory HoldingLots.fromJson(Map<String, dynamic> j) => HoldingLots(
        ticker: j['ticker'] as String,
        currentPrice: (j['current_price'] as num).toDouble(),
        priceSource: j['price_source'] as String,
        lots: (j['lots'] as List)
            .map((l) => Lot.fromJson(l as Map<String, dynamic>))
            .toList(),
        totals: LotTotals.fromJson(j['totals'] as Map<String, dynamic>),
      );
}

/// Sector-concentration compliance judged over KNOWN sectors only — the
/// "Other" (unclassified) bucket is disclosed but never counts as a breach
/// (the DEF059 inversion guard). `maxAllowed` is read from the user's
/// mandate `concentration_tolerance`; never hard-code it client-side.
class SectorCompliance {
  const SectorCompliance({
    required this.maxSector,
    this.maxSectorName,
    required this.maxAllowed,
    required this.compliant,
  });

  final double maxSector;
  // Null when the portfolio holds only unclassified ("Other") tickers.
  final String? maxSectorName;
  final double maxAllowed;
  final bool compliant;

  factory SectorCompliance.fromJson(Map<String, dynamic> j) => SectorCompliance(
        maxSector: (j['max_sector'] as num).toDouble(),
        maxSectorName: j['max_sector_name'] as String?,
        maxAllowed: (j['max_allowed'] as num).toDouble(),
        compliant: j['compliant'] as bool,
      );
}

/// Sector-allocation donut feed + concentration-compliance. Returned by
/// GET /v1/portfolio/sector-allocation/{user_id} (CR026).
class SectorAllocation {
  const SectorAllocation({
    required this.allocation,
    required this.totalValue,
    required this.compliance,
  });

  // Sector name -> weight (normalised over invested market value, 4 dp).
  // May contain the "Other" (unclassified) bucket alongside known sectors.
  final Map<String, double> allocation;
  final double totalValue;
  final SectorCompliance compliance;

  factory SectorAllocation.fromJson(Map<String, dynamic> j) => SectorAllocation(
        allocation: Map<String, double>.fromEntries(
          (j['allocation'] as Map).entries.map(
                (e) => MapEntry(e.key as String, (e.value as num).toDouble()),
              ),
        ),
        totalValue: (j['total_value'] as num).toDouble(),
        compliance:
            SectorCompliance.fromJson(j['compliance'] as Map<String, dynamic>),
      );
}
