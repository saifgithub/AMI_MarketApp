/// CR109 slice 2 — a canned `ApiClient` for game-surface widget tests.
///
/// Shared by the entry-sheet and trade-ticket tests so both exercise the
/// real `GamesEntrySheet` / `GamesTicketNotifier` logic against
/// deterministic responses, never a rewritten stand-in — same shape as
/// `journal_plan_trust_boundary_test.dart`'s `_RecordingApiClient`.
library;

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/services/api/api_client.dart';

class FakeGamesApiClient extends ApiClient {
  FakeGamesApiClient({
    this.tradeQuote,
    this.tradeResult,
    this.queuedOrders = const [],
    this.cancelSucceeds = true,
    this.quoteError,
    this.board,
    this.arc,
    this.desks = const [],
  }) : super(baseUrl: 'test://localhost');

  /// When set, [gamesTradeQuote] throws it instead of answering — models a
  /// transport failure (Saiful hit a real one when the Cloudflare tunnel
  /// dropped every edge connector for ~70s and his phone got a 502).
  Object? quoteError;

  /// Canned response for [gamesQueuedOrders].
  List<GameQueuedOrder> queuedOrders;

  /// Canned response for [gamesBoard] — the field standings.
  GameBoard? board;

  /// Canned response for [gamesArc] — the period arc's live beat (CR109
  /// slice 5). Answered by default rather than left to fall through to the
  /// real `ApiClient`: the run screen mounts the beat card unconditionally,
  /// so an un-overridden method here throws a transport error inside a
  /// FutureProvider and the test framework fails the whole file on it.
  GameArc? arc;

  /// Canned response for [gamesDesks] — the house desks' published rules.
  List<GameDeskProfile> desks = const [];

  /// What the SERVER reports for a cancel. `false` models the real race —
  /// the order filled between the list being drawn and the tap — which the
  /// UI must report as "too late", never as a cancellation.
  bool cancelSucceeds;

  final List<({String runId, String orderId})> cancelCallsSeen = [];

  /// Canned response for [gamesTradeQuote]; a sensible default when the
  /// caller doesn't need to control the numbers.
  GameTradeQuote? tradeQuote;

  /// Canned response for [gamesTrade].
  GameTradeResult? tradeResult;

  final List<String> enterCadencesSeen = [];
  final List<({String ticker, String side, double notional})> quoteCallsSeen =
      [];

  /// The `quantity` argument of each quote call — non-null exactly when the
  /// caller sized in SHARES, which is the sell path.
  final List<double?> quantityQuoteCallsSeen = [];
  final List<({String ticker, String side, double quantity})> tradeCallsSeen =
      [];

  @override
  Future<GameEntry> gamesEnter({required String cadence}) async {
    enterCadencesSeen.add(cadence);
    return GameEntry(
      entryId: 'entry-1',
      fieldId: 'field-1',
      runId: 'run-1',
      cadence: cadence,
      state: 'entered',
    );
  }

  @override
  Future<List<GameCadenceInfo>> gamesCadences() async => const [
        GameCadenceInfo(cadence: 'week'),
      ];

  @override
  Future<List<GameRunSummary>> gamesRuns() async => const [];

  @override
  Future<GameRunDetail> gamesRunDetail(String runId) async => GameRunDetail(
        runId: runId,
        fieldId: 'field-1',
        cadence: 'week',
        state: 'active',
        stake: 10000,
        cash: 10000,
      );

  @override
  Future<List<GameQueuedOrder>> gamesQueuedOrders(String runId) async =>
      queuedOrders;

  @override
  Future<GameBoard> gamesBoard(String runId) async =>
      board ??
      GameBoard(fieldId: 'field-1', cadence: 'week', rows: const []);

  @override
  Future<GameArc> gamesArc(String runId) async =>
      arc ??
      GameArc(
        runId: runId,
        cadence: 'week',
        phase: GameArcPhase.live,
        daysLeft: 3,
        entrantCount: 1,
      );

  @override
  Future<List<GameDeskProfile>> gamesDesks() async => desks;

  @override
  Future<bool> gamesCancelQueuedOrder({
    required String runId,
    required String orderId,
  }) async {
    cancelCallsSeen.add((runId: runId, orderId: orderId));
    return cancelSucceeds;
  }

  @override
  Future<GameTradeQuote> gamesTradeQuote({
    required String runId,
    required String ticker,
    required String side,
    double? notional,
    double? quantity,
  }) async {
    // A SELL sizes in shares, a BUY in dollars — the fake resolves whichever
    // it was given at the same fixed 180.00 so a test can assert on either.
    final resolvedNotional = notional ?? (quantity! * 180.0);
    quoteCallsSeen
        .add((ticker: ticker, side: side, notional: resolvedNotional));
    quantityQuoteCallsSeen.add(quantity);
    if (quoteError != null) throw quoteError!;
    return tradeQuote ??
        GameTradeQuote(
          ticker: ticker,
          side: side,
          shares: quantity ?? resolvedNotional / 180.0,
          price: 180.0,
          notional: resolvedNotional,
          estFee: resolvedNotional * 0.001 < 1.0 ? 1.0 : resolvedNotional * 0.001,
          bookPercentage: (resolvedNotional / 10000) * 100,
          priceSource: 'live',
          willQueue: false,
        );
  }

  @override
  Future<GameTradeResult> gamesTrade({
    required String runId,
    required String ticker,
    required String side,
    required double quantity,
  }) async {
    tradeCallsSeen.add((ticker: ticker, side: side, quantity: quantity));
    return tradeResult ??
        GameTradeResult(
          status: 'filled',
          ticker: ticker,
          side: side,
          shares: quantity,
          price: 180.0,
          fee: 1.0,
        );
  }
}
