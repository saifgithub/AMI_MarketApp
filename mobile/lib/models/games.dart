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

  factory GameCadenceInfo.fromJson(Map<String, dynamic> j) => GameCadenceInfo(
        cadence: j['cadence'] as String? ?? 'week',
        nextField: j['next_field'] is Map<String, dynamic>
            ? GameFieldSummary.fromJson(j['next_field'] as Map<String, dynamic>)
            : null,
        entryState: j['entry_state'] as String?,
        queueCount: (j['queue_count'] as num?)?.toInt() ?? 0,
        queueDeadline: _parseDate(j['queue_deadline']),
        alreadyHolds: j['already_holds'] as bool? ?? false,
      );
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
  /// 'live' | 'mock' | 'stale'.
  final String priceSource;

  bool get isLive => priceSource == 'live';

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
    this.twrPct,
    this.daysLeft,
    this.startsOn,
    this.endsOn,
    this.navSeries = const [],
  });

  final String runId;
  final String fieldId;
  final String cadence;
  final String state;
  final double stake;
  final double cash;
  final double? twrPct;
  final int? daysLeft;
  final DateTime? startsOn;
  final DateTime? endsOn;
  final List<GameNavPoint> navSeries;

  factory GameRunDetail.fromJson(Map<String, dynamic> j) => GameRunDetail(
        runId: (j['run_id'] ?? j['id']) as String? ?? '',
        fieldId: j['field_id'] as String? ?? '',
        cadence: j['cadence'] as String? ?? 'week',
        state: j['state'] as String? ?? 'active',
        stake: (j['stake'] as num?)?.toDouble() ?? 10000.0,
        cash: (j['cash'] as num?)?.toDouble() ?? 0.0,
        twrPct: (j['twr_pct'] as num?)?.toDouble(),
        daysLeft: (j['days_left'] as num?)?.toInt(),
        startsOn: _parseDate(j['starts_on']),
        endsOn: _parseDate(j['ends_on']),
        navSeries: ((j['nav_series'] ?? j['points']) as List? ?? const [])
            .map((p) => GameNavPoint.fromJson(p as Map<String, dynamic>))
            .toList(),
      );
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
    this.willQueue = false,
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
  final bool willQueue;

  factory GameTradeQuote.fromJson(Map<String, dynamic> j) => GameTradeQuote(
        ticker: j['ticker'] as String? ?? '',
        side: j['side'] as String? ?? 'buy',
        shares: (j['shares'] as num?)?.toDouble() ?? 0,
        price: (j['price'] as num?)?.toDouble() ?? 0,
        notional: (j['notional'] as num?)?.toDouble() ?? 0,
        estFee: (j['est_fee'] as num?)?.toDouble() ?? 0,
        bookPercentage: (j['book_percentage'] as num?)?.toDouble() ?? 0,
        priceSource: j['price_source'] as String? ?? 'live',
        willQueue: j['will_queue'] as bool? ?? false,
      );
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

  factory GameTradeResult.fromJson(Map<String, dynamic> j) => GameTradeResult(
        status: j['status'] as String? ?? 'filled',
        ticker: j['ticker'] as String? ?? '',
        side: j['side'] as String? ?? 'buy',
        shares: (j['shares'] as num?)?.toDouble(),
        price: (j['price'] as num?)?.toDouble(),
        fee: (j['fee'] as num?)?.toDouble(),
        queuedFor: _parseDate(j['queued_for']),
      );
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
