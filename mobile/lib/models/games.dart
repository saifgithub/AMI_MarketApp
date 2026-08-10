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
  });

  final String runId;
  final String fieldId;
  final String cadence;
  final double? twrPct;
  final int? daysLeft;
  final DateTime? endsOn;
  /// 'entered' | 'active' | 'finished' | 'forfeit' | 'void'.
  final String state;

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

  /// Provenance of the marks behind [stake] — 'live' | 'cash' | 'mock' |
  /// 'stale' | a raw provider name. Only [marksAreLive] may be drawn as fact.
  final String priceSource;
  final double feesPaid;
  final int tradeCount;

  /// The book is empty AND nothing is waiting to fill it — §13.3's
  /// "highest-anxiety moment in the product", which must not render as a
  /// blank list. A player with queued orders is NOT in this state: they have
  /// acted, and the queued-orders surface is what they need to see.
  bool get isEmptyBook => holdings.isEmpty && queuedOrderCount == 0;

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
      holdings.isEmpty ||
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
class GameCloseResult {
  const GameCloseResult({
    required this.runId,
    required this.fieldId,
    required this.cadence,
    this.state = 'finished',
    this.scoringBasis = 'placement',
    this.entrantCount = 0,
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
        nearMissLabel: j['near_miss_label'] as String?,
        nearMissGapPct: (j['near_miss_gap_pct'] as num?)?.toDouble(),
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
    this.runHistory = const [],
  });

  final int careerPoints;
  final int enteredCount;
  final int finishedCount;
  final int forfeitCount;
  final int voidCount;

  /// Present only once a title system ships (slice 4 — DARK this slice per
  /// implementation_plan.md §2). Parsed defensively for forward-compat;
  /// the Record's IDENTITY section renders only when this is non-null.
  final String? title;

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
        runHistory: ((j['run_history'] ?? j['runs']) as List? ?? const [])
            .map((e) => GameRecordRunHistoryEntry.fromJson(
                e as Map<String, dynamic>))
            .toList(),
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
