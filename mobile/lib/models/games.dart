/// CR109 slice 2 (mobile) — data models for the dark-launched P&L game.
///
/// The game is a P&L competition played in AMI Cash, entirely separate from
/// the training simulator (`models/sim.dart`) — no Room, no mandate, scored
/// on time-weighted return. See
/// `docs/forward_planning/CR109_pnl_game_ami_cash/CR109.md` for the design
/// and `implementation_plan.md` §4/§6 for the schema and API surface this
/// file codes against.
///
/// Every model here is unreachable in a store build: `/games` only exists
/// behind `kGamesEnabled` (`features/games/games_gate.dart`). Wire shapes
/// follow the implementation plan's snake_case JSON as the working contract
/// with the parallel `coder.api` lane — every `fromJson` is defensive
/// (nullable reads, `??` fallbacks) because the backend lands in parallel;
/// a field-name mismatch at integration should surface as a wrong/default
/// value the UI can recover from, never a parse crash.
library;

DateTime? _parseDate(dynamic v) => v is String ? DateTime.tryParse(v) : null;

/// One cadence's current standing, from `GET /v1/games/cadences`
/// (implementation_plan.md §6). Slice 2's backend only rolls `week`
/// (implementation_plan.md §2), so the client only reads the `week` entry
/// today — the shape stays generic so a later cadence (slice 6) needs no
/// model change.
class GameCadenceInfo {
  const GameCadenceInfo({
    required this.cadence,
    this.nextField,
    this.entryState,
    this.queueCount = 0,
    this.queueDeadline,
    this.alreadyHolds = false,
  });

  /// 'week' | 'month' | 'quarter' | 'half' | 'year'.
  final String cadence;
  final GameFieldSummary? nextField;
  /// null | 'not_entered' | 'entered' | 'active' | 'finished' | 'forfeit' | 'void'.
  final String? entryState;
  final int queueCount;
  final DateTime? queueDeadline;
  final bool alreadyHolds;

  bool get isWeekly => cadence == 'week';

  /// The backend sends the next field's data FLAT on the cadence object
  /// (`field_id`, `state`, `starts_on`, `locks_at`, …) rather than nested
  /// under `next_field`, and names three keys differently: `state` (not
  /// `entry_state`), `deadline` (not `queue_deadline`) and `already_held`
  /// (not `already_holds`).
  ///
  /// Every read here is null-safe, so the original nested-only version did
  /// not throw — it silently produced a cadence with no field, no deadline
  /// and `alreadyHolds: false`, which renders as an entry card that cannot
  /// tell you when entry closes or that you are already in. A quiet wrong
  /// answer, which is worse than the parse error next door. Both shapes are
  /// accepted so neither side can drift again.
  factory GameCadenceInfo.fromJson(Map<String, dynamic> j) {
    final nested = j['next_field'];
    return GameCadenceInfo(
      cadence: j['cadence'] as String? ?? 'week',
      nextField: nested is Map<String, dynamic>
          ? GameFieldSummary.fromJson(nested)
          : (j['field_id'] != null ? GameFieldSummary.fromJson(j) : null),
      entryState: (j['entry_state'] ?? j['state']) as String?,
      queueCount: (j['queue_count'] as num?)?.toInt() ?? 0,
      queueDeadline: _parseDate(j['queue_deadline'] ?? j['deadline']),
      alreadyHolds:
          (j['already_holds'] ?? j['already_held']) as bool? ?? false,
    );
  }
}

/// The `game_fields` row a cadence's next field points at
/// (implementation_plan.md §4.3).
class GameFieldSummary {
  const GameFieldSummary({
    required this.fieldId,
    this.entryOpensAt,
    this.locksAt,
    this.startsOn,
    this.endsOn,
    this.entrantCount = 0,
  });

  final String fieldId;
  final DateTime? entryOpensAt;
  final DateTime? locksAt;
  final DateTime? startsOn;
  final DateTime? endsOn;
  final int entrantCount;

  factory GameFieldSummary.fromJson(Map<String, dynamic> j) => GameFieldSummary(
        fieldId: (j['field_id'] ?? j['id']) as String? ?? '',
        entryOpensAt: _parseDate(j['entry_opens_at']),
        locksAt: _parseDate(j['locks_at']),
        startsOn: _parseDate(j['starts_on']),
        endsOn: _parseDate(j['ends_on']),
        entrantCount: (j['entrant_count'] as num?)?.toInt() ?? 0,
      );
}

/// The created `game_entries` row from `POST /v1/games/enter` — 409 if the
/// caller already holds this cadence (§4.1's one-live-run-per-cadence
/// guard), surfaced by the API client as a normal `DioException` and turned
/// into copy by `friendlyError`, same as every other refused write in this
/// app.
class GameEntry {
  const GameEntry({
    required this.entryId,
    required this.fieldId,
    required this.runId,
    required this.cadence,
    required this.state,
  });

  final String entryId;
  final String fieldId;
  final String runId;
  final String cadence;
  final String state;

  factory GameEntry.fromJson(Map<String, dynamic> j) => GameEntry(
        entryId: (j['entry_id'] ?? j['id']) as String? ?? '',
        fieldId: j['field_id'] as String? ?? '',
        runId: j['run_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'entered',
      );
}

/// One live run from `GET /v1/games/runs` — the State-B landing card's data
/// (implementation_plan.md §8.2). No score, no board, no close this slice —
/// [twrPct] is layer-1/2 (Stake/Contest) NAV math, not a placement score.
class GameRunSummary {
  const GameRunSummary({
    required this.runId,
    required this.fieldId,
    required this.cadence,
    this.twrPct,
    this.daysLeft,
    this.endsOn,
    this.state = 'active',
    this.phase,
    this.locksAt,
  });

  final String runId;
  final String fieldId;
  final String cadence;
  final double? twrPct;
  final int? daysLeft;
  final DateTime? endsOn;
  /// 'entered' | 'active' | 'finished' | 'forfeit' | 'void'.
  final String state;

  /// CR109 slice 5 — which beat of the period arc (design §10) this run is
  /// in, so the home card can say "entries close in 2h" or "final stretch"
  /// without a second call. Null on a backend that predates the slice; the
  /// card falls back to the plain days-left line rather than guessing.
  final String? phase;

  /// When entries close for this run's field — the countdown target for
  /// [GameArcPhase.entryOpen].
  final DateTime? locksAt;

  /// Whether this run still belongs on the State-B landing card — a
  /// finished/forfeit/void entry has left the "live" set even though the
  /// backend may still list it for a beat.
  bool get isLive => state == 'entered' || state == 'active';

  factory GameRunSummary.fromJson(Map<String, dynamic> j) => GameRunSummary(
        runId: (j['run_id'] ?? j['id']) as String? ?? '',
        fieldId: j['field_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        twrPct: (j['twr_pct'] as num?)?.toDouble(),
        daysLeft: (j['days_left'] as num?)?.toInt(),
        endsOn: _parseDate(j['ends_on']),
        state: j['state'] as String? ?? 'active',
        phase: j['phase'] as String?,
        locksAt: _parseDate(j['locks_at']),
      );
}

/// One NAV snapshot inside a run detail's series — same provenance shape as
/// `SimPortfolioHistoryPoint` (CR109 slice 1, `models/sim.dart`), because
/// both ride the same `portfolio_nav_daily` table
/// (implementation_plan.md §4.1). `priceSource` rides per point for the
/// same CR040 reason: a series can cross from live into mock/stale pricing
/// and back, and only 'live' may ever be drawn as fact.
class GameNavPoint {
  const GameNavPoint({
    required this.asOfDate,
    required this.nav,
    required this.cash,
    required this.priceSource,
  });

  final DateTime asOfDate;
  final double nav;
  final double cash;
  /// 'live' | 'cash' | 'mock' | 'stale'.
  final String priceSource;

  /// True when the point needs no provenance caveat drawn on it.
  ///
  /// `cash` counts as exact, not estimated: a day with no holdings has a NAV
  /// of pure cash, which is known rather than priced. Dashing it would tell
  /// the user a real number was simulated. Only `mock`/`stale` are caveated.
  bool get isLive => priceSource == 'live' || priceSource == 'cash';

  factory GameNavPoint.fromJson(Map<String, dynamic> j) => GameNavPoint(
        asOfDate: DateTime.parse(j['as_of_date'] as String),
        nav: (j['nav'] as num).toDouble(),
        cash: (j['cash'] as num?)?.toDouble() ?? 0,
        priceSource: j['price_source'] as String? ?? 'mock',
      );
}

/// `GET /v1/games/runs/{run_id}` — detail + NAV series for the curve.
/// [cash] is the run's current uninvested AMI Cash, which the trade
/// ticket's size chips (§5.4) price themselves against locally.
class GameRunDetail {
  const GameRunDetail({
    required this.runId,
    required this.fieldId,
    required this.cadence,
    required this.state,
    required this.stake,
    required this.cash,
    this.cashCommitted = 0,
    double? cashAvailable,
    this.queuedOrderCount = 0,
    this.twrPct,
    int? daysLeft,
    this.startsOn,
    this.endsOn,
    this.navSeries = const [],
    this.holdings = const [],
    this.shorts = const [],
    this.duel,
    this.priceSource = 'live',
    this.feesPaid = 0,
    this.tradeCount = 0,
  })  : _cashAvailable = cashAvailable,
        _daysLeft = daysLeft;

  final String runId;
  final String fieldId;
  final String cadence;
  final String state;
  final double stake;
  final double cash;

  /// AMI Cash already spoken for by orders waiting on the next open —
  /// estimated at read time, never stored (see `_queued_orders_priced` in
  /// `games_service.py` for why that does not breach the stale-price fence).
  final double cashCommitted;

  final double? _cashAvailable;

  /// What the trade ticket must size against. Queued orders commit no cash
  /// until they fill, so [cash] alone told a player with two orders already
  /// queued that the whole stake was still theirs to spend — Saiful, on
  /// build 74: *"This was the second order placed. But it is still showing I
  /// have 10K."* Falls back to `cash − committed`, and never below zero.
  double get cashAvailable {
    final v = _cashAvailable ?? (cash - cashCommitted);
    return v < 0 ? 0 : v;
  }

  final int queuedOrderCount;
  final double? twrPct;
  final int? _daysLeft;

  /// Days remaining in the run.
  ///
  /// The run-detail payload does **not** carry `days_left` — only the run
  /// SUMMARY does. Reading it here returned null, which the empty-book copy
  /// rendered as "0 days to deploy it" on a run with five days to go: a
  /// wrong number, stated confidently, in the one place §13.3 says the clock
  /// must appear.
  ///
  /// Derived from `ends_on`, which the payload does send. That is arithmetic
  /// on what the server gave us, not an invention — and it is null, not
  /// zero, when there is nothing to derive from.
  int? get daysLeft {
    if (_daysLeft != null) return _daysLeft;
    final end = endsOn;
    if (end == null) return null;
    final now = DateTime.now();
    final days = DateTime(end.year, end.month, end.day)
        .difference(DateTime(now.year, now.month, now.day))
        .inDays;
    return days < 0 ? 0 : days;
  }

  final DateTime? startsOn;
  final DateTime? endsOn;
  final List<GameNavPoint> navSeries;
  final List<GameHolding> holdings;

  /// Open SHORT positions — CR109 Amendment G. A separate list, never a
  /// holding with a negative quantity: a short's P&L runs the other way and
  /// its loss is unbounded, so it is drawn as its own kind of row rather
  /// than as a long with a sign flip a reader can miss.
  final List<GameShort> shorts;

  /// The live head-to-head, or null when this run has no opponent this
  /// period — CR109 slice 3b. Null is an ORDINARY state, not a degraded one:
  /// an odd player out simply is not paired, and the screen shows the open
  /// field instead. It must never render as a duel against nobody.
  final GameDuel? duel;

  /// Provenance of the marks behind [stake] — 'live' | 'cash' | 'mock' |
  /// 'stale' | a raw provider name. Only [marksAreLive] may be drawn as fact.
  final String priceSource;
  final double feesPaid;
  final int tradeCount;

  /// The book is empty AND nothing is waiting to fill it — §13.3's
  /// "highest-anxiety moment in the product", which must not render as a
  /// blank list. A player with queued orders is NOT in this state: they have
  /// acted, and the queued-orders surface is what they need to see.
  bool get isEmptyBook =>
      holdings.isEmpty && shorts.isEmpty && queuedOrderCount == 0;

  /// `mock_walk` (the fallback provider) and `stale` are the two values that
  /// must carry a caveat. `cash` is exact, not estimated — a book with no
  /// holdings has a NAV of pure cash. Same rule as [GameNavPoint.isLive].
  ///
  /// An EMPTY book is live by definition: its value IS the cash balance, and
  /// no mark was consulted to arrive at it. The snapshot still reports
  /// whatever the price provider last said — live Alpha sends `mock_walk`
  /// here on a book with no holdings — and caveating a number that no price
  /// ever touched trains the player to ignore the caveat on the day it
  /// means something.
  bool get marksAreLive =>
      (holdings.isEmpty && shorts.isEmpty) ||
      (!priceSource.startsWith('mock') && priceSource != 'stale');

  /// The backend names these `current_cash` and `total_value`. Reading only
  /// `cash`/`stake` did not throw — `cash` fell back to 0.0, so the ticket
  /// sized every order as a percentage of ZERO: the confirm card showed
  /// "0.0000 shares", "0.0% of your book" and a $1.00 fee (the minimum-fee
  /// floor applied to a zero notional). It also meant the player could never
  /// see what they had. Both spellings accepted.
  factory GameRunDetail.fromJson(Map<String, dynamic> j) => GameRunDetail(
        runId: (j['run_id'] ?? j['id']) as String? ?? '',
        fieldId: j['field_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'active',
        stake: ((j['stake'] ?? j['total_value']) as num?)?.toDouble() ?? 10000.0,
        cash: ((j['cash'] ?? j['current_cash']) as num?)?.toDouble() ?? 0.0,
        cashCommitted: (j['cash_committed'] as num?)?.toDouble() ?? 0.0,
        cashAvailable: (j['cash_available'] as num?)?.toDouble(),
        queuedOrderCount: (j['queued_order_count'] as num?)?.toInt() ?? 0,
        twrPct: (j['twr_pct'] as num?)?.toDouble(),
        daysLeft: (j['days_left'] as num?)?.toInt(),
        startsOn: _parseDate(j['starts_on']),
        endsOn: _parseDate(j['ends_on']),
        navSeries: ((j['nav_series'] ?? j['points']) as List? ?? const [])
            .map((p) => GameNavPoint.fromJson(p as Map<String, dynamic>))
            .toList(),
        holdings: ((j['holdings'] ?? j['positions']) as List? ?? const [])
            .map((h) => GameHolding.fromJson(h as Map<String, dynamic>))
            .toList(),
        shorts: ((j['shorts'] as List?) ?? const [])
            .map((h) => GameShort.fromJson(h as Map<String, dynamic>))
            .toList(),
        duel: j['duel'] == null
            ? null
            : GameDuel.fromJson(j['duel'] as Map<String, dynamic>),
        priceSource: j['price_source'] as String? ?? 'live',
        feesPaid: (j['fees_paid'] as num?)?.toDouble() ?? 0.0,
        tradeCount: (j['trade_count'] as num?)?.toInt() ?? 0,
      );
}

/// One open position inside a run — `holdings[]` on the run-detail payload.
///
/// [mark] is the backend's current price for the name; on an empty or
/// unpriceable book `games_service` sends `avg_cost` back as the mark, which
/// shows a flat position rather than a fabricated move.
class GameHolding {
  const GameHolding({
    required this.ticker,
    required this.quantity,
    required this.avgCost,
    required this.mark,
  });

  final String ticker;
  final double quantity;
  final double avgCost;
  final double mark;

  double get marketValue => quantity * mark;
  double get costBasis => quantity * avgCost;
  double get unrealisedPnl => marketValue - costBasis;
  double get unrealisedPct =>
      costBasis == 0 ? 0 : (unrealisedPnl / costBasis) * 100;

  factory GameHolding.fromJson(Map<String, dynamic> j) {
    final avg = (j['avg_cost'] as num?)?.toDouble() ?? 0;
    return GameHolding(
      ticker: j['ticker'] as String? ?? '',
      quantity: (j['quantity'] as num?)?.toDouble() ?? 0,
      avgCost: avg,
      mark: (j['mark'] as num?)?.toDouble() ?? avg,
    );
  }
}

/// The live head-to-head — CR109 slice 3b, design §11.1.
///
/// A duel needs n=2, which is the only competitive format that works at
/// alpha field sizes: *"You vs VECTOR_11. 3 days left. They're 1.1% ahead"*
/// beats *"1st of 3, scored against the S&P"* by a wide margin.
///
/// [leadPct] arrives SIGNED from the server, from this player's side. Both
/// TWRs are on the wire so a client could subtract them — and one that got
/// the sign backwards would tell a losing player they were ahead. One
/// subtraction, one place. Null means the gap is not known yet (either side
/// unmeasured), which is not the same as level.
class GameDuel {
  const GameDuel({
    required this.kind,
    required this.cadence,
    required this.state,
    required this.opponentHandle,
    this.opponentIsDesk = false,
    this.opponentDeskRule,
    this.opponentTwrPct,
    this.myTwrPct,
    this.leadPct,
    this.outcome,
    this.pointsDelta = 0,
    this.pointsAtStake,
  });

  /// 'auto' | 'first_run'. A first run is always against the Index Desk —
  /// the one opponent that is guaranteed to exist and cannot embarrass a
  /// beginner, because it holds the benchmark.
  final String kind;
  final String cadence;

  /// 'live' | 'settled' | 'void'.
  final String state;

  final String opponentHandle;
  final bool opponentIsDesk;

  /// The desk's PUBLISHED rule. Shown, not hidden: the first-run duel is
  /// "beat the Index Desk", and a player who did not know their opponent was
  /// the benchmark would be reading a different result than the one they got.
  final String? opponentDeskRule;
  final double? opponentTwrPct;
  final double? myTwrPct;

  /// Positive when this player is ahead. Null while either side is
  /// unmeasured — a duel that has not started has an UNKNOWN gap, not a
  /// level one, and 0.0 would draw a dead heat that is not happening.
  final double? leadPct;

  /// 'won' | 'lost' | 'draw' | 'void', or null while live.
  final String? outcome;

  /// What the settled result was worth. 0 on a draw or a void.
  final int pointsDelta;

  /// What a live duel is playing for. Null once settled.
  final int? pointsAtStake;

  bool get isLive => state == 'live';
  bool get isFirstRun => kind == 'first_run';

  /// True only when the gap is KNOWN and this player is ahead. Deliberately
  /// not `leadPct >= 0` — an unknown gap must not read as a lead.
  bool get isAhead => leadPct != null && leadPct! > 0;

  factory GameDuel.fromJson(Map<String, dynamic> j) {
    final opp = (j['opponent'] as Map<String, dynamic>?) ?? const {};
    return GameDuel(
      kind: j['kind'] as String? ?? 'auto',
      cadence: j['cadence'] as String? ?? 'week',
      state: j['state'] as String? ?? 'live',
      opponentHandle: opp['handle'] as String? ?? 'Unnamed',
      opponentIsDesk: opp['is_desk'] as bool? ?? false,
      opponentDeskRule: opp['desk_rule'] as String?,
      opponentTwrPct: (opp['twr_pct'] as num?)?.toDouble(),
      myTwrPct: (j['my_twr_pct'] as num?)?.toDouble(),
      leadPct: (j['lead_pct'] as num?)?.toDouble(),
      outcome: j['outcome'] as String?,
      pointsDelta: (j['points_delta'] as num?)?.toInt() ?? 0,
      pointsAtStake: (j['points_at_stake'] as num?)?.toInt(),
    );
  }
}

/// One OPEN short position in a run — CR109 Amendment G.
///
/// [unrealisedPnl] arrives computed from the server rather than derived
/// here. The sign convention on a short is the opposite of a long's, and a
/// client that got it backwards would draw a losing position in green on the
/// one position type whose loss is unbounded. The server already computes it
/// for the score; this reads the same number.
class GameShort {
  const GameShort({
    required this.id,
    required this.ticker,
    required this.quantity,
    required this.entryPrice,
    required this.cashPosted,
    required this.mark,
    required this.unrealisedPnl,
  });

  final String id;
  final String ticker;
  final double quantity;
  final double entryPrice;

  /// The AMI Cash tied up at open — the FULL notional, not a margin
  /// fraction. The game runs no leverage, so shorting 5,000 of AMI Cash
  /// costs 5,000 of the stake, exactly as buying 5,000 would.
  final double cashPosted;
  final double mark;

  /// Positive when the mark is BELOW entry.
  final double unrealisedPnl;

  double get unrealisedPct =>
      cashPosted == 0 ? 0 : (unrealisedPnl / cashPosted) * 100;

  /// What the position is worth to the book right now: the posted cash back,
  /// adjusted for the move. Can go negative — see the backend's
  /// `trading_math/shorts.py`.
  double get value => cashPosted + unrealisedPnl;

  factory GameShort.fromJson(Map<String, dynamic> j) {
    final entry = (j['entry_price'] as num?)?.toDouble() ?? 0;
    final qty = (j['quantity'] as num?)?.toDouble() ?? 0;
    final mark = (j['mark'] as num?)?.toDouble() ?? entry;
    return GameShort(
      id: j['id'] as String? ?? '',
      ticker: j['ticker'] as String? ?? '',
      quantity: qty,
      entryPrice: entry,
      cashPosted: (j['cash_posted'] as num?)?.toDouble() ?? entry * qty,
      mark: mark,
      // Derived only as a fallback for a payload that predates the field —
      // the server's own number wins whenever it is present, so the two can
      // never disagree about which way a short is.
      unrealisedPnl:
          (j['unrealised_pnl'] as num?)?.toDouble() ?? (entry - mark) * qty,
    );
  }
}

/// One order waiting on the next US open — `GET /v1/games/runs/{id}/orders`.
///
/// §13.3 calls this "the most-seen state in the product" for GCC/SEA
/// players, because US market hours are their evening and past-midnight.
/// The app shipped the ticket's promise — *"free to cancel any time before
/// it fills"* — for a week with no surface that could show an order, let
/// alone cancel one.
///
/// Every money field here is an ESTIMATE recomputed on each read at the
/// current quote; the fill happens at the next open's price. [priceSource]
/// rides along for the same CR040 reason it rides a NAV point: an estimate
/// drawn from `mock_walk` must not be presented as a live one.
class GameQueuedOrder {
  const GameQueuedOrder({
    required this.orderId,
    required this.ticker,
    required this.side,
    required this.quantity,
    this.queuedAt,
    this.estPrice = 0,
    this.estNotional = 0,
    this.estFee = 0,
    this.estTotal = 0,
    this.priceSource = 'live',
    this.state = 'queued',
    this.cancelReason,
  });

  final String orderId;
  final String ticker;
  /// 'buy' | 'sell'.
  final String side;
  final double quantity;
  final DateTime? queuedAt;
  final double estPrice;
  final double estNotional;
  final double estFee;
  final double estTotal;
  final String priceSource;

  /// 'queued' — waiting on the next open — or 'refused', an order the open
  /// would not take.
  final String state;

  /// Why the open refused it, server-authored (*"insufficient cash: need
  /// $500.00, have $12.00"*). Null on a live queued order.
  final String? cancelReason;

  /// An order that will not happen. It stays on the list precisely because
  /// it will not: it used to be filtered out server-side, so a refused order
  /// simply vanished overnight and the player found some orders filled, some
  /// gone, and nothing anywhere saying which or why.
  bool get isRefused => state == 'refused';

  bool get isBuy => side == 'buy';
  bool get estimateIsLive =>
      !priceSource.startsWith('mock') && priceSource != 'stale';

  factory GameQueuedOrder.fromJson(Map<String, dynamic> j) {
    final notional = (j['est_notional'] as num?)?.toDouble() ?? 0;
    final fee = (j['est_fee'] as num?)?.toDouble() ?? 0;
    return GameQueuedOrder(
      orderId: (j['id'] ?? j['order_id']) as String? ?? '',
      ticker: j['ticker'] as String? ?? '',
      side: j['side'] as String? ?? 'buy',
      quantity: (j['quantity'] as num?)?.toDouble() ?? 0,
      queuedAt: _parseDate(j['queued_at']),
      estPrice: (j['est_price'] as num?)?.toDouble() ?? 0,
      estNotional: notional,
      estFee: fee,
      estTotal: (j['est_total'] as num?)?.toDouble() ?? (notional + fee),
      priceSource: j['price_source'] as String? ?? 'live',
      state: j['state'] as String? ?? 'queued',
      cancelReason: j['cancel_reason'] as String?,
    );
  }
}

/// `POST /v1/games/runs/{run_id}/trade/quote` — the ticket's TAP-3 confirm
/// card (§5.4): shares, est. fee, book-percentage. [willQueue] is TRUE for
/// most requests from GCC/SEA users (§5.1) — that is the *normal* path, not
/// an error state, and the UI must not style it as one.
class GameTradeQuote {
  const GameTradeQuote({
    required this.ticker,
    required this.side,
    required this.shares,
    required this.price,
    required this.notional,
    required this.estFee,
    required this.bookPercentage,
    this.priceSource = 'live',
    this.willQueue,
  });

  final String ticker;
  /// 'buy' | 'sell'.
  final String side;
  final double shares;
  final double price;
  final double notional;
  final double estFee;
  final double bookPercentage;
  final String priceSource;

  /// True = queues until the next open, false = fills now, **null = the
  /// server said neither**. Nullable on purpose; see [_willQueue].
  final bool? willQueue;

  /// Whether the ticket must show the queue caveat. Unknown counts as yes —
  /// the cost of an unnecessary caveat is a redundant line, the cost of a
  /// missing one is a player believing they hold something they do not.
  bool get mayQueue => willQueue != false;

  /// Whether [price] came from the live feed rather than the fallback walk.
  /// Same rule as [GameNavPoint.isLive] and [GameRunDetail.marksAreLive] —
  /// a simulated price may never be drawn as a real one (CR040).
  bool get priceIsLive =>
      !priceSource.startsWith('mock') && priceSource != 'stale';

  factory GameTradeQuote.fromJson(Map<String, dynamic> j) => GameTradeQuote(
        ticker: j['ticker'] as String? ?? '',
        side: j['side'] as String? ?? 'buy',
        // The backend names these `quantity` and `estimated_fee`. Reading
        // only `shares`/`est_fee` did not throw — both defaulted to 0, so the
        // confirm card would have shown "0 shares" and a zero trading cost
        // on a real order. Accept both spellings.
        shares: ((j['shares'] ?? j['quantity']) as num?)?.toDouble() ?? 0,
        price: (j['price'] as num?)?.toDouble() ?? 0,
        notional: (j['notional'] as num?)?.toDouble() ?? 0,
        estFee: ((j['est_fee'] ?? j['estimated_fee']) as num?)?.toDouble() ?? 0,
        bookPercentage: (j['book_percentage'] as num?)?.toDouble() ?? 0,
        priceSource: j['price_source'] as String? ?? 'live',
        willQueue: _willQueue(j),
      );

  /// The backend does not send `will_queue`. It sends **`market_open`** —
  /// the inverse — so this read defaulted to `false` on every quote and the
  /// confirm card never showed the queue note, on the path §5.1 calls the
  /// NORMAL one for GCC/SEA players. The seventh instance of the same class
  /// as the six in this file's other fallbacks.
  ///
  /// Null means neither key arrived, which is not the same as "it will
  /// fill." Absent information must never render as the affirmative claim
  /// (see [GameTradeResult.fromJson]) — here the affirmative claim is
  /// "this executes now," so unknown surfaces the queue caveat too.
  static bool? _willQueue(Map<String, dynamic> j) {
    final explicit = j['will_queue'] as bool?;
    if (explicit != null) return explicit;
    final open = j['market_open'] as bool?;
    return open == null ? null : !open;
  }
}

/// `POST /v1/games/runs/{run_id}/trade` — the placed or queued order.
class GameTradeResult {
  const GameTradeResult({
    required this.status,
    required this.ticker,
    required this.side,
    this.shares,
    this.price,
    this.fee,
    this.queuedFor,
  });

  /// 'filled' | 'queued'.
  final String status;
  final String ticker;
  final String side;
  final double? shares;
  final double? price;
  final double? fee;
  final DateTime? queuedFor;

  bool get isQueued => status == 'queued';

  /// True only when the order actually executed. Deliberately NOT
  /// `!isQueued` — "not queued" also covers "we do not know", and the one
  /// thing this class must never do is imply a fill it cannot evidence.
  bool get isFilled => status == 'filled';

  /// The backend reports the outcome as two BOOLEANS — `{"queued": true,
  /// "filled": false, "next_open_at": …}` — and sends no `status` key at all.
  ///
  /// This read `j['status']` and defaulted to **`'filled'`**, so every order
  /// placed outside market hours told the player it had EXECUTED when it had
  /// only been queued. Saiful caught it: *"It says filled. I don't think it
  /// was."* He was right — the market was shut.
  ///
  /// That default is the CR040 failure in its purest form: absent
  /// information, the app asserted the affirmative, and did so about a
  /// position in a scored contest. A player would believe they held AMD when
  /// they held nothing until the next open. The fallback is now `unknown`,
  /// which the UI must render as uncertainty rather than as a fill.
  factory GameTradeResult.fromJson(Map<String, dynamic> j) {
    final queued = j['queued'] == true;
    final filled = j['filled'] == true;
    final status = (j['status'] as String?) ??
        (queued
            ? 'queued'
            : filled
                ? 'filled'
                : 'unknown');
    return GameTradeResult(
      status: status,
      ticker: j['ticker'] as String? ?? '',
      side: j['side'] as String? ?? 'buy',
      shares: ((j['shares'] ?? j['quantity']) as num?)?.toDouble(),
      price: (j['price'] as num?)?.toDouble(),
      fee: (j['fee'] as num?)?.toDouble(),
      queuedFor: _parseDate(j['queued_for'] ?? j['next_open_at']),
    );
  }
}

/// `POST /v1/games/runs/{run_id}/restart` — §6.7's forfeit preview-then-commit.
/// Called with `confirm: false` (the API client's default) it returns the
/// forfeit cost without acting; `confirm: true` commits it. Not built into a
/// screen this slice (out of the explicit slice-2 mobile scope), but wired
/// on the client so the contract is codeable against as soon as it is.
class GameRestartPreview {
  const GameRestartPreview({
    required this.runId,
    required this.careerPointsDebit,
    this.committed = false,
  });

  final String runId;
  final int careerPointsDebit;
  final bool committed;

  factory GameRestartPreview.fromJson(Map<String, dynamic> j) =>
      GameRestartPreview(
        runId: (j['run_id'] ?? '') as String,
        careerPointsDebit: (j['career_points_debit'] as num?)?.toInt() ?? 0,
        committed: j['committed'] as bool? ?? false,
      );
}

// ─────────────────────────────────────────────────────────────────────────
// CR109 slice 3 — the Close and the Record.
// ─────────────────────────────────────────────────────────────────────────

/// `GET /v1/games/runs/{run_id}/close` — the Close's full payload (design
/// §10.2, implementation_plan.md §6). Screens read a SUBSET of this for the
/// three-beat ceremony (`screens/games/games_close_screen.dart`); the rest
/// backs the debrief panel one tap deeper.
///
/// **There is no entitlement field anywhere on this model, on purpose.**
/// implementation_plan.md §6: "the Close payload is complete without an
/// entitlement... a free user's response carries rank, delta, curve, both
/// counterfactual lines, markers and the re-entry CTA." The paid agent
/// post-mortem is a later slice and is deliberately not modeled here — see
/// `games_close_screen.dart`'s file docstring.
///
/// [alphaScored] and [alphaDisplay] are two SEPARATE wire fields
/// (implementation_plan.md §6.6.2 / §6): net-of-fee (what the score is
/// based on) and gross-vs-costless-index (what the boast shows). Neither is
/// ever computed from the other on this client.
/// The duel verdict as beat 2 of the Close — CR109 slice 3b.
///
/// Thinner than [GameDuel] on purpose: once the result exists, the run
/// screen's live-gap machinery (points at stake, days left, the
/// unmeasured-gap caption) is noise. What survives is who, what happened,
/// by how much, and what it was worth.
class GameCloseDuel {
  const GameCloseDuel({
    required this.outcome,
    required this.opponentHandle,
    this.duelKind = 'auto',
    this.opponentIsDesk = false,
    this.opponentDeskRule,
    this.myTwrPct,
    this.opponentTwrPct,
    this.marginPct,
    this.pointsDelta = 0,
  });

  /// 'won' | 'lost' | 'draw'. A void duel never reaches beat 2 at all.
  final String outcome;
  final String opponentHandle;

  /// 'auto' | 'first_run'. Named `duel_kind` on the wire, NOT `kind` — the
  /// beat envelope uses `kind` as its own discriminator ('duel' vs
  /// 'counterfactual'), and a duel spread into it under the same key
  /// silently overwrote that.
  final String duelKind;
  final bool opponentIsDesk;
  final String? opponentDeskRule;
  final double? myTwrPct;
  final double? opponentTwrPct;

  /// Signed from this player's side, computed by the server. Positive on a
  /// win. Null only if a side was never measured, which beat 2 filters out.
  final double? marginPct;
  final int pointsDelta;

  bool get isFirstRun => duelKind == 'first_run';

  factory GameCloseDuel.fromJson(Map<String, dynamic> j) => GameCloseDuel(
        outcome: j['outcome'] as String? ?? 'draw',
        opponentHandle: j['opponent_handle'] as String? ?? 'Unnamed',
        duelKind: j['duel_kind'] as String? ?? 'auto',
        opponentIsDesk: j['opponent_is_desk'] as bool? ?? false,
        opponentDeskRule: j['opponent_desk_rule'] as String?,
        myTwrPct: (j['my_twr_pct'] as num?)?.toDouble(),
        opponentTwrPct: (j['opponent_twr_pct'] as num?)?.toDouble(),
        marginPct: (j['margin_pct'] as num?)?.toDouble(),
        pointsDelta: (j['points_delta'] as num?)?.toInt() ?? 0,
      );
}

/// Reads beat 2 ONLY when the server labelled it a duel. A payload whose
/// insight is the counterfactual yields null here, so the two can never both
/// render — the three-beat budget is the whole point of the surface.
GameCloseDuel? _duelVerdictFrom(Map<String, dynamic> j) {
  final beats = j['beats'];
  if (beats is! Map) return null;
  final insight = beats['insight'];
  if (insight is! Map || insight['kind'] != 'duel') return null;
  return GameCloseDuel.fromJson(Map<String, dynamic>.from(insight));
}

class GameCloseResult {
  const GameCloseResult({
    required this.runId,
    required this.fieldId,
    required this.cadence,
    this.state = 'finished',
    this.scoringBasis = 'placement',
    this.entrantCount = 0,
    this.scoredEntrantCount,
    this.rank,
    this.voidReason,
    this.careerPointsDelta = 0,
    this.finalTwrPct,
    this.alphaScored,
    this.alphaDisplay,
    this.counterfactualFirstPicksPct,
    this.counterfactualIndexPct,
    this.navSeries = const [],
    this.intent,
    this.wildnessIndex,
    this.feesPaid,
    this.tradeCount = 0,
    this.stipendAwarded = false,
    this.stipendPoints,
    this.nearMissLabel,
    this.nearMissGapPct,
    this.duelVerdict,
    this.windUp,
    this.marker,
  });

  final String runId;
  final String fieldId;
  final String cadence;

  /// 'finished' | 'forfeit' | 'void' — a closed `game_entries` state.
  final String state;

  /// 'placement' | 'benchmark' — resolved at close, then frozen
  /// (implementation_plan.md §4.3).
  final String scoringBasis;
  final int entrantCount;

  /// The `n` the rank was actually divided by — the entries with a
  /// comparable result. Deliberately NOT [entrantCount], which counts
  /// everyone who entered including VOID runs whose numbers were never
  /// usable: "3rd of 9" in a field where two runs voided is a sentence
  /// about a contest that did not happen. Null on a run scored before
  /// slice 4, where [rankedFieldSize] falls back.
  final int? scoredEntrantCount;
  final int? rank;
  final String? voidReason;
  final int careerPointsDelta;
  final double? finalTwrPct;

  /// Net of the one entry fee — what the score is based on
  /// (implementation_plan.md §6.6.2). NEVER derive from [alphaDisplay].
  final double? alphaScored;

  /// Gross vs the costless index — what the boast shows. NEVER derive from
  /// [alphaScored]. The whole point of shipping both is that they differ.
  final double? alphaDisplay;

  /// "If you'd held your first picks untouched: +X%" (design §10.4).
  final double? counterfactualFirstPicksPct;

  /// "If you'd just held the S&P: +Y%" (design §10.4).
  final double? counterfactualIndexPct;

  final List<GameNavPoint> navSeries;

  /// 'wild' | 'thesis' | 'disciplined' — the intent tag declared at entry
  /// (design §10.4), null until a later slice's entry flow sets one.
  final String? intent;
  final double? wildnessIndex;
  final double? feesPaid;
  final int tradeCount;

  /// Whether the finish stipend paid on this entry (design §6.5). A VOID
  /// run can still be true here — "the feed failed, not the player."
  /// Derived from [stipendPoints] when the server sends only that.
  final bool stipendAwarded;

  /// The stipend's own point value, when the server sends one separately
  /// from [careerPointsDelta] (`stipend_points` on the wire) — kept
  /// distinct so the debrief can show "showed up" points apart from
  /// "performed" points, per implementation_plan.md §4.5's reasoning for
  /// keeping the two as separate ledger rows.
  final int? stipendPoints;

  /// Server-authored, pre-vetted to point UP only (design §10.1's fence:
  /// "near-miss framing points up only, never at a loss"). Null when no
  /// near-miss applies; this client never computes one itself.
  final String? nearMissLabel;
  final double? nearMissGapPct;

  /// The settled duel, when the server chose it for beat 2 — CR109 slice 3b,
  /// §10.2's priority order (*the duel verdict on a first run · the
  /// post-mortem on a blowup · the near-miss · otherwise the
  /// counterfactual*).
  ///
  /// **The server picks the beat, not the client.** The Close has a
  /// three-beat budget precisely because it had become "a report with
  /// confetti", and a client that decided its own priority would drift from
  /// the one place the rule is written down. Null means the server chose
  /// something else — including for a VOID duel, which has nothing to say.
  final GameCloseDuel? duelVerdict;

  /// CR109 slice 5 — the Wind-Up (design §10). Non-null ONLY when the run
  /// was a blowup; the server decides, because this governs the tone of the
  /// screen and a threshold duplicated on both sides will eventually
  /// disagree with itself and put confetti over a wipeout.
  final GameWindUp? windUp;

  bool get isWindUp => windUp != null;

  /// CR109 slice 8 (§8.4) — the one progress marker this close earned, or
  /// null when it earned none. Null is a real and frequent answer: a marker
  /// invented for every close is the participation trophy §8.4 opens by
  /// excluding.
  final GameMarker? marker;

  bool get isVoid => state == 'void';

  /// Defensive/forward-compatible only: the live `games_record_service.py`
  /// (`get_close_payload`) 404/409s a forfeited run before this model ever
  /// sees one — "a forfeit has no Close," by that module's own docstring.
  /// A `state == 'forfeit'` payload is therefore not reachable through
  /// today's `/close` endpoint; kept so this model degrades correctly
  /// rather than crashing if that ever changes. The reachable dignified
  /// treatment for a forfeited run today lives on
  /// `GamesRecordScreen`'s history row instead — see that file.
  bool get isForfeit => state == 'forfeit';
  bool get isThinField => scoringBasis == 'benchmark';

  /// What a rank should be shown OUT OF. Prefers the scored count and
  /// falls back to the field's own total for pre-slice-4 rows — never to
  /// zero, because "1st of 0" is the one rendering that is worse than
  /// showing the wider number.
  int get rankedFieldSize =>
      (scoredEntrantCount != null && scoredEntrantCount! > 0)
          ? scoredEntrantCount!
          : entrantCount;
  bool get hasNearMiss => nearMissLabel != null && nearMissGapPct != null;

  /// Wire keys are read with fallbacks across the plan-doc's prose names
  /// AND the shipped `games_record_service.py` names where they differ
  /// (e.g. `alpha_scored` vs. the actual `alpha_scored_pct`) — both lanes
  /// build from the same implementation plan in parallel, so this stays
  /// correct against either.
  factory GameCloseResult.fromJson(Map<String, dynamic> j) => GameCloseResult(
        runId: (j['run_id'] ?? j['id']) as String? ?? '',
        fieldId: j['field_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'finished',
        scoringBasis: j['scoring_basis'] as String? ?? 'placement',
        entrantCount: (j['entrant_count'] as num?)?.toInt() ?? 0,
        scoredEntrantCount: (j['scored_entrant_count'] as num?)?.toInt(),
        rank: ((j['final_rank'] ?? j['rank']) as num?)?.toInt(),
        voidReason: j['void_reason'] as String?,
        careerPointsDelta:
            ((j['career_points_delta'] ?? j['career_point_delta']) as num?)
                    ?.toInt() ??
                0,
        finalTwrPct: ((j['final_twr_pct'] ?? j['twr_pct']) as num?)
            ?.toDouble(),
        alphaScored:
            ((j['alpha_scored_pct'] ?? j['alpha_scored']) as num?)
                ?.toDouble(),
        alphaDisplay:
            ((j['alpha_display_pct'] ?? j['alpha_display']) as num?)
                ?.toDouble(),
        counterfactualFirstPicksPct: ((j['counterfactual_hold_first_picks_pct'] ??
                j['counterfactual_first_picks_pct'] ??
                j['counterfactual_buy_hold_pct']) as num?)
            ?.toDouble(),
        counterfactualIndexPct: ((j['counterfactual_hold_index_pct'] ??
                j['counterfactual_index_pct'] ??
                j['counterfactual_benchmark_pct']) as num?)
            ?.toDouble(),
        navSeries: ((j['curve'] ?? j['nav_series'] ?? j['points']) as List? ??
                const [])
            .map((p) => GameNavPoint.fromJson(p as Map<String, dynamic>))
            .toList(),
        intent: j['intent'] as String?,
        wildnessIndex: (j['wildness_index'] as num?)?.toDouble(),
        feesPaid: (j['fees_paid'] as num?)?.toDouble(),
        tradeCount: (j['trade_count'] as num?)?.toInt() ?? 0,
        stipendAwarded: j['stipend_awarded'] as bool? ??
            (((j['stipend_points'] as num?)?.toInt() ?? 0) > 0),
        stipendPoints: (j['stipend_points'] as num?)?.toInt(),
        duelVerdict: _duelVerdictFrom(j),
        nearMissLabel: j['near_miss_label'] as String?,
        nearMissGapPct: (j['near_miss_gap_pct'] as num?)?.toDouble(),
        windUp: j['wind_up'] is Map<String, dynamic>
            ? GameWindUp.fromJson(j['wind_up'] as Map<String, dynamic>)
            : null,
        marker: j['marker'] is Map<String, dynamic>
            ? GameMarker.fromJson(j['marker'] as Map<String, dynamic>)
            : null,
      );
}

/// One progress marker — CR109 slice 8, design §8.4.
///
/// *"If one player in 26 receives something, twenty-five received nothing,
/// and that is the churn."* Every marker is a THRESHOLD CROSSED rather than
/// a thing that happens for showing up — the finish stipend already pays for
/// showing up, and §8.4 is explicit that the two are one ethos said twice.
class GameMarker {
  const GameMarker({required this.kind, this.value});

  /// 'first_finish' | 'first_positive' | 'first_podium' |
  /// 'personal_best_twr' | 'clean_streak'.
  final String kind;

  /// The number the marker is about — a return, a rank, a count — or null
  /// for a marker that is purely an event (a first finish).
  final num? value;

  factory GameMarker.fromJson(Map<String, dynamic> j) => GameMarker(
        kind: j['kind'] as String? ?? '',
        value: j['value'] as num?,
      );
}

/// `GET /v1/games/record` — the Record's "identity / movement / history"
/// surface (design §13.3, implementation_plan.md §6).
///
/// [careerPoints] is `SUM(delta)` straight from the append-only ledger. The
/// ledger clamps AT WRITE TIME (implementation_plan.md §4.5's Amendment-D
/// correction — "the ledger clamps, not the display"), so this number must
/// be rendered EXACTLY as received by every caller — never re-clamped,
/// never `math.max(0, ...)`'d, on this client.
class GameRecord {
  const GameRecord({
    this.careerPoints = 0,
    this.enteredCount = 0,
    this.finishedCount = 0,
    this.forfeitCount = 0,
    this.voidCount = 0,
    this.title,
    this.nextTitle,
    this.runHistory = const [],
  });

  final int careerPoints;
  final int enteredCount;
  final int finishedCount;
  final int forfeitCount;
  final int voidCount;

  /// The title held right now — §6.4 thresholds, recomputed on read rather
  /// than stored as a promotion, so there is nothing here that can fall out
  /// of sync with [careerPoints] beside it. Still nullable: a backend that
  /// predates slice 4 simply omits it, and the IDENTITY section renders
  /// only when it is present.
  final String? title;

  /// The rung above, and what still stands between the player and it.
  ///
  /// This is the surface Amendment D correction 3 actually asked for. The
  /// finding was never that progression is slow — it is that the median
  /// player, oscillating around `p = 0.5`, nets roughly zero per run and so
  /// can SEE no progression at all. A total that moves on placement noise
  /// says nothing about where it is going; this says what the target is and
  /// how far away it is, in the unit that closes it.
  final GameTitleGoal? nextTitle;

  final List<GameRecordRunHistoryEntry> runHistory;

  /// Same dual-fallback posture as [GameCloseResult.fromJson] — the shipped
  /// `games_record_service.py.get_record` names the ledger total
  /// `career_points_net` and the total-entries count `run_count`, both read
  /// here alongside the plan-doc's prose names.
  factory GameRecord.fromJson(Map<String, dynamic> j) => GameRecord(
        careerPoints: ((j['career_points_net'] ??
                    j['career_points'] ??
                    j['career_points_total']) as num?)
                ?.toInt() ??
            0,
        enteredCount:
            ((j['run_count'] ?? j['entered_count']) as num?)?.toInt() ?? 0,
        finishedCount: (j['finished_count'] as num?)?.toInt() ?? 0,
        forfeitCount: (j['forfeit_count'] as num?)?.toInt() ?? 0,
        voidCount: (j['void_count'] as num?)?.toInt() ?? 0,
        title: j['title'] as String?,
        nextTitle: j['next_title'] == null
            ? null
            : GameTitleGoal.fromJson(j['next_title'] as Map<String, dynamic>),
        runHistory: ((j['run_history'] ?? j['runs']) as List? ?? const [])
            .map((e) => GameRecordRunHistoryEntry.fromJson(
                e as Map<String, dynamic>))
            .toList(),
      );
}

/// The next rung on the title ladder and the distance to it.
///
/// `requirement` is `finished_runs` for the milestone rung and
/// `career_points` for every rung above it — the two are not
/// interchangeable, and a client that rendered "3 more points" for a
/// milestone would be describing a threshold that does not exist.
class GameTitleGoal {
  const GameTitleGoal({
    required this.title,
    required this.requirement,
    required this.remaining,
  });

  final String title;
  final String requirement;
  final int remaining;

  bool get isMilestone => requirement == 'finished_runs';

  factory GameTitleGoal.fromJson(Map<String, dynamic> j) => GameTitleGoal(
        title: j['title'] as String? ?? '',
        requirement: j['requirement'] as String? ?? 'career_points',
        remaining: (j['remaining'] as num?)?.toInt() ?? 0,
      );
}

/// One row of the Record's run-history list.
class GameRecordRunHistoryEntry {
  const GameRecordRunHistoryEntry({
    required this.entryId,
    required this.cadence,
    this.runId,
    this.state = 'finished',
    this.closedAt,
    this.rank,
    this.entrantCount,
    this.careerPointsDelta = 0,
    this.finalTwrPct,
  });

  final String entryId;

  /// The run this entry scored — when present, the row can open
  /// [GameCloseResult] for it (`GamesCloseScreen`); null degrades to a
  /// non-tappable row rather than a broken link.
  final String? runId;
  final String cadence;

  /// 'entered' | 'active' | 'finished' | 'forfeit' | 'void'.
  final String state;
  final DateTime? closedAt;
  final int? rank;
  final int? entrantCount;
  final int careerPointsDelta;
  final double? finalTwrPct;

  /// `games_record_service.py.get_record`'s `run_history` rows carry no
  /// `entry_id` at all (only `run_id`) and no `closed_at`/`scored_at` —
  /// [entryId] degrades to `''` (still safe: nothing keys off it) and
  /// [closedAt] falls back to the field's `ends_on`, which is the closest
  /// available date to "when this entry's Close happened."
  factory GameRecordRunHistoryEntry.fromJson(Map<String, dynamic> j) =>
      GameRecordRunHistoryEntry(
        entryId: (j['entry_id'] ?? j['id']) as String? ?? '',
        runId: j['run_id'] as String?,
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'finished',
        closedAt: _parseDate(j['closed_at'] ?? j['scored_at'] ?? j['ends_on']),
        rank: ((j['final_rank'] ?? j['rank']) as num?)?.toInt(),
        entrantCount: (j['entrant_count'] as num?)?.toInt(),
        careerPointsDelta: (j['career_points_delta'] as num?)?.toInt() ?? 0,
        finalTwrPct: ((j['final_twr_pct'] ?? j['twr_pct']) as num?)
            ?.toDouble(),
      );
}

/// `GET /v1/games/record/prs` — the PR board; a max-query over
/// `portfolio_nav_daily` + `game_entries`, no new table
/// (implementation_plan.md §4.4.2). "The only competitive surface that
/// works at n = 1."
class GamePersonalRecord {
  const GamePersonalRecord({
    required this.kind,
    required this.entryId,
    this.value,
    this.cadence,
    this.achievedAt,
  });

  /// Server-defined category key — design §4.4.2 lists the categories
  /// (best weekly TWR, best alpha, best drawdown control, longest hold,
  /// longest streak of finishes); the exact key strings are the backend
  /// lane's to define. An unrecognised [kind] degrades to [fallbackLabel]
  /// rather than being dropped — a new server-side category must never
  /// disappear on an un-updated client.
  final String kind;

  /// The `game_entries` id that SET this record — implementation_plan.md
  /// §4.4.2: "each carrying the entry_id that set it," required so a PR at
  /// n = 1 still reads as a real, attributable result rather than a bare
  /// number.
  final String entryId;
  final double? value;
  final String? cadence;
  final DateTime? achievedAt;

  /// Title-cased fallback for a [kind] this client's label map doesn't
  /// recognise yet.
  String get fallbackLabel => kind
      .split('_')
      .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');

  factory GamePersonalRecord.fromJson(Map<String, dynamic> j) =>
      GamePersonalRecord(
        kind: j['kind'] as String? ?? 'unknown',
        entryId: (j['entry_id'] ?? j['id']) as String? ?? '',
        value: (j['value'] as num?)?.toDouble(),
        cadence: j['cadence'] as String?,
        achievedAt: _parseDate(j['achieved_at'] ?? j['closed_at']),
      );
}

/// One row on the field board — `GET /v1/games/runs/{id}/board`.
///
/// **[twrPct] and [rank] are nullable and must stay that way.** An entrant
/// whose run has no completed close yet has not been measured; that is a
/// different fact from being exactly flat, and from being last. Defaulting
/// either to a number is the `?? 0` class that has now cost this feature nine
/// separate defects — the queue note that never rendered because `will_queue`
/// defaulted false, the "0 days to deploy it" from an absent `days_left`, the
/// second order that sized against zero cash mid-refresh. Same shape, one
/// level down each time. A dash is the honest render.
///
/// [isDesk] is not decoration. Design §11.2 makes disclosure a hard
/// requirement: a player who copies an undisclosed house account believes they
/// are copying a person, and once a screenshot leaves the app there is no
/// disclosure surface left. The server sends the desk's published rule with
/// every row so the board can show it in place.
class GameBoardRow {
  const GameBoardRow({
    required this.handle,
    required this.isDesk,
    this.deskKey,
    this.deskRule,
    this.twrPct,
    this.rank,
    this.closesCounted = 0,
    this.isYou = false,
    this.titleIneligibleReason,
  });

  final String handle;
  final bool isDesk;
  final String? deskKey;
  final String? deskRule;

  /// CR109 slice 8 (§8.5) — 'house_desk' | 'affiliated' | null.
  ///
  /// Published, not hidden: *"Ineligible does not mean invisible"*. The
  /// entrant ranks, the board shows what actually happened, and the row says
  /// out loud that this one cannot hold the title. A silent exclusion is the
  /// tell §11.2 exists to avoid.
  final String? titleIneligibleReason;

  /// `null` = not measured yet. NEVER coerce to 0.
  final double? twrPct;

  /// `null` = unranked (no close yet). NEVER coerce to `entrantCount`.
  final int? rank;

  final int closesCounted;
  final bool isYou;

  bool get isMeasured => twrPct != null;

  factory GameBoardRow.fromJson(Map<String, dynamic> j) => GameBoardRow(
        handle: j['handle'] as String? ?? '—',
        isDesk: j['is_desk'] == true,
        deskKey: j['desk_key'] as String?,
        deskRule: j['desk_rule'] as String?,
        twrPct: (j['twr_pct'] as num?)?.toDouble(),
        rank: (j['rank'] as num?)?.toInt(),
        closesCounted: (j['closes_counted'] as num?)?.toInt() ?? 0,
        isYou: j['is_you'] == true,
        titleIneligibleReason: j['title_ineligible_reason'] as String?,
      );
}

/// The field board — the answer to *"How do I see my current standing against
/// the rest of the field?"*
///
/// Ranks on % TWR only. Design §6.1 writes that down as an invariant because
/// a board that ranks absolute AMI Cash makes capital tier pay-to-win, so
/// this model carries no currency field at all — there is nothing here to
/// render money from even by accident.
///
/// [updates] is `daily_close`: the standings move once per US close, never per
/// tick (§10). The screen says so, because a player watching an unchanged
/// number all afternoon otherwise concludes the feature is broken.
class GameBoard {
  const GameBoard({
    required this.fieldId,
    required this.cadence,
    required this.rows,
    this.state = 'live',
    this.startsOn,
    this.endsOn,
    this.benchmarkTicker = 'SPY',
    this.entrantCount = 0,
    this.deskCount = 0,
    this.standingsOpen = false,
    this.yourRank,
    this.yourTwrPct,
    this.updates = 'daily_close',
    this.champion,
  });

  final String fieldId;
  final String cadence;
  final String state;
  final DateTime? startsOn;
  final DateTime? endsOn;
  final String benchmarkTicker;
  final int entrantCount;
  final int deskCount;

  /// False until at least one entrant has a completed close. The screen must
  /// render "standings open after the first close" rather than a field of
  /// zeroes that reads as everyone tied and flat.
  final bool standingsOpen;

  final int? yourRank;
  final double? yourTwrPct;
  final List<GameBoardRow> rows;
  final String updates;

  /// CR109 slice 8 (§8.5) — who holds the field's title, present only once
  /// the field has closed. Null on an all-desk field: a leader with no
  /// champion is a fact, and inventing one would be the silent promotion
  /// §8.5 names as the failure to avoid.
  final GameChampion? champion;

  int get humanCount => entrantCount - deskCount;
  int get measuredCount => rows.where((r) => r.isMeasured).length;

  factory GameBoard.fromJson(Map<String, dynamic> j) => GameBoard(
        fieldId: j['field_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'live',
        startsOn: _parseDate(j['starts_on']),
        endsOn: _parseDate(j['ends_on']),
        benchmarkTicker: j['benchmark_ticker'] as String? ?? 'SPY',
        entrantCount: (j['entrant_count'] as num?)?.toInt() ?? 0,
        deskCount: (j['desk_count'] as num?)?.toInt() ?? 0,
        standingsOpen: j['standings_open'] == true,
        yourRank: (j['your_rank'] as num?)?.toInt(),
        yourTwrPct: (j['your_twr_pct'] as num?)?.toDouble(),
        rows: ((j['rows'] as List?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GameBoardRow.fromJson)
            .toList(),
        updates: j['updates'] as String? ?? 'daily_close',
        champion: j['champion'] is Map<String, dynamic>
            ? GameChampion.fromJson(j['champion'] as Map<String, dynamic>)
            : null,
      );
}

/// The holder of a closed field's title — CR109 slice 8, design §8.5.
///
/// [displaced] is the case the design cares about: the board leader could
/// not hold the title, so it passed down. §8.5: *"When an ineligible entrant
/// places first, say so plainly — 'Title: SLATE_07 (2nd overall)' — rather
/// than silently renumbering. A board that quietly promotes second place
/// looks like a bug; one that explains itself looks like a rule."*
class GameChampion {
  const GameChampion({
    required this.handle,
    required this.rank,
    this.displaced = false,
  });

  final String handle;
  final int rank;
  final bool displaced;

  factory GameChampion.fromJson(Map<String, dynamic> j) => GameChampion(
        handle: j['handle'] as String? ?? '—',
        rank: (j['rank'] as num?)?.toInt() ?? 1,
        displaced: j['displaced'] == true,
      );
}

/// One house desk's published rule — `GET /v1/games/desks`.
///
/// Disclosure is the feature (§11.2), so the rule and the universe are wire
/// fields rather than app copy: a player must be able to reproduce any desk's
/// basket by hand, and a rule that lives only in the client would drift from
/// the code that actually selects the names.
class GameDeskProfile {
  const GameDeskProfile({
    required this.key,
    required this.name,
    required this.rule,
    this.universe = const [],
  });

  final String key;
  final String name;
  final String rule;
  final List<String> universe;

  factory GameDeskProfile.fromJson(Map<String, dynamic> j) => GameDeskProfile(
        key: j['key'] as String? ?? '',
        name: j['name'] as String? ?? '',
        rule: j['rule'] as String? ?? '',
        universe: ((j['universe'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
      );
}

// ── The period arc (CR109 slice 5, design §10) ──────────────────────────

/// Which beat of the period arc a run is in. String constants rather than an
/// enum because the server is the authority — an unknown value must render
/// as the plain live state, not throw.
abstract final class GameArcPhase {
  static const entryOpen = 'entry_open';
  static const bell = 'bell';
  static const live = 'live';
  static const finalStretch = 'final_stretch';
  static const settling = 'settling';
  static const closed = 'closed';
}

/// The biggest mover in a run — design §10's *"NVDA drove +1.9% of your
/// +2.3%"*. `pctPoints` is in percentage points of the opening stake and is
/// signed: the name that drove a loss is the one a losing run needs named.
class GameAttribution {
  const GameAttribution({
    required this.ticker,
    required this.pctPoints,
    this.stillHeld = false,
    this.priceSource,
  });

  final String ticker;
  final double pctPoints;
  final bool stillHeld;

  /// CR040 — which prices produced this line. A mock-priced attribution that
  /// renders as fact is the shape of DEF059.
  final String? priceSource;

  bool get isLivePriced => priceSource == null || priceSource == 'live';

  factory GameAttribution.fromJson(Map<String, dynamic> j) => GameAttribution(
        ticker: j['ticker'] as String? ?? '',
        pctPoints: (j['pct_points'] as num?)?.toDouble() ?? 0,
        stillHeld: j['still_held'] as bool? ?? false,
        priceSource: j['price_source'] as String?,
      );
}

/// `GET /v1/games/runs/{run_id}/arc` — the live half of the period arc.
///
/// **Two clocks, and the difference is deliberate.** [yourRank] and
/// [gapToNextPct] move once per US close ([standingsUpdate] says so out
/// loud); [attribution] is live, because it is your own book rather than
/// other people's. The server's `games_arc.py` docstring carries the full
/// reasoning.
///
/// **There is no downward gap, by construction.** Design §10 permits *"2nd
/// is 1.1% ahead"* and forbids the slot-machine twin that points at a loss.
/// The number a copywriter would need to cross that line is not in this
/// payload, so it cannot be crossed here.
class GameArc {
  const GameArc({
    required this.runId,
    required this.cadence,
    required this.phase,
    required this.daysLeft,
    required this.entrantCount,
    this.locksAt,
    this.endsOn,
    this.standingsOpen = false,
    this.yourRank,
    this.yourTwrPct,
    this.gapToNextPct,
    this.gapToNextRank,
    this.attribution,
    this.deskCount = 0,
    this.standingsUpdate = 'daily_close',
  });

  final String runId;
  final String cadence;
  final String phase;
  final int daysLeft;
  final int entrantCount;
  final DateTime? locksAt;
  final DateTime? endsOn;

  /// False until at least one entrant has a completed close. Renders as
  /// "standings open after the first close", never as a field of zeroes —
  /// a run that has not been measured and a run that is exactly flat are
  /// different facts.
  final bool standingsOpen;
  final int? yourRank;
  final double? yourTwrPct;

  /// How far ahead the entrant immediately above you is. Null when you lead,
  /// when nothing has been measured yet, or when there is nobody above —
  /// three different facts, none of which may render as 0.0.
  final double? gapToNextPct;
  final int? gapToNextRank;
  final GameAttribution? attribution;
  final int deskCount;
  final String standingsUpdate;

  bool get isFinalStretch => phase == GameArcPhase.finalStretch;
  bool get isEntryOpen => phase == GameArcPhase.entryOpen;
  bool get hasGap => gapToNextPct != null && gapToNextRank != null;

  factory GameArc.fromJson(Map<String, dynamic> j) => GameArc(
        runId: j['run_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        phase: j['phase'] as String? ?? GameArcPhase.live,
        daysLeft: (j['days_left'] as num?)?.toInt() ?? 0,
        entrantCount: (j['entrant_count'] as num?)?.toInt() ?? 0,
        locksAt: _parseDate(j['locks_at']),
        endsOn: _parseDate(j['ends_on']),
        standingsOpen: j['standings_open'] as bool? ?? false,
        yourRank: (j['your_rank'] as num?)?.toInt(),
        yourTwrPct: (j['your_twr_pct'] as num?)?.toDouble(),
        gapToNextPct: (j['gap_to_next_pct'] as num?)?.toDouble(),
        gapToNextRank: (j['gap_to_next_rank'] as num?)?.toInt(),
        attribution: j['attribution'] is Map<String, dynamic>
            ? GameAttribution.fromJson(j['attribution'] as Map<String, dynamic>)
            : null,
        deskCount: (j['desk_count'] as num?)?.toInt() ?? 0,
        standingsUpdate: j['standings_update'] as String? ?? 'daily_close',
      );
}

/// The Wind-Up — design §10's LOSS ceremony. Present on the Close payload
/// only when the run was a blowup; its presence IS the switch between the
/// two ceremonies, decided server-side so the threshold cannot drift.
///
/// *"A blowup gets a dignified post-mortem with real numbers and immediate
/// re-entry — never a fail screen. Losing must be a chapter, not an
/// ending."* Every word rendered around these numbers is an ARB string held
/// to that rule.
class GameWindUp {
  const GameWindUp({
    required this.reason,
    this.finalTwrPct,
    this.navShortfall,
    this.worstTicker,
    this.worstPctPoints,
    this.tradeCount = 0,
  });

  /// 'busted' (the book went below zero — Amendment I) | 'heavy_loss'.
  final String reason;
  final double? finalTwrPct;

  /// How far past zero the book actually went, which the floored NAV hides.
  /// Stated in the ceremony rather than swallowed.
  final double? navShortfall;
  final String? worstTicker;
  final double? worstPctPoints;
  final int tradeCount;

  bool get isBust => reason == 'busted';
  bool get hasWorst => worstTicker != null && worstPctPoints != null;

  factory GameWindUp.fromJson(Map<String, dynamic> j) {
    final worst = j['worst'];
    return GameWindUp(
      reason: j['reason'] as String? ?? 'heavy_loss',
      finalTwrPct: (j['final_twr_pct'] as num?)?.toDouble(),
      navShortfall: (j['nav_shortfall'] as num?)?.toDouble(),
      worstTicker: worst is Map<String, dynamic> ? worst['ticker'] as String? : null,
      worstPctPoints: worst is Map<String, dynamic>
          ? (worst['pct_points'] as num?)?.toDouble()
          : null,
      tradeCount: (j['trade_count'] as num?)?.toInt() ?? 0,
    );
  }
}
