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
  }) : super(baseUrl: 'test://localhost');

  /// Canned response for [gamesQueuedOrders].
  List<GameQueuedOrder> queuedOrders;

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
    required double notional,
  }) async {
    quoteCallsSeen.add((ticker: ticker, side: side, notional: notional));
    return tradeQuote ??
        GameTradeQuote(
          ticker: ticker,
          side: side,
          shares: notional / 180.0,
          price: 180.0,
          notional: notional,
          estFee: notional * 0.001 < 1.0 ? 1.0 : notional * 0.001,
          bookPercentage: (notional / 10000) * 100,
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
