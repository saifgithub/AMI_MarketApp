/// CR109 slice 2 — Riverpod state for the dark-launched P&L game.
///
/// Read-only feeds (cadences, runs, run detail) are plain `FutureProvider`s,
/// same shape as `sim_providers.dart`'s `portfolioHistoryProvider` — this
/// screen has no long-lived mutable state of its own beyond the trade
/// ticket, which gets a `StateNotifier` below because it walks a
/// three-step flow (ticker → size → confirm, §5.4) a single future can't
/// hold. Unreachable in a store build: nothing here fires unless a gated
/// build's `/games` route is reached (`features/games/games_gate.dart`).
library;

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final gamesCadencesProvider =
    FutureProvider.autoDispose<List<GameCadenceInfo>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesCadences();
});

final gamesRunsProvider =
    FutureProvider.autoDispose<List<GameRunSummary>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesRuns();
});

final gamesRunDetailProvider =
    FutureProvider.autoDispose.family<GameRunDetail, String>((ref, runId) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesRunDetail(runId);
});

/// §13.3's Queued-orders surface. Separate from [gamesRunDetailProvider]
/// rather than folded into it: the run detail is read by the ticket on every
/// size drag, and the orders list is a heavier call (it quotes every open
/// order). Both are invalidated together after a trade or a cancel.
final gamesQueuedOrdersProvider = FutureProvider.autoDispose
    .family<List<GameQueuedOrder>, String>((ref, runId) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesQueuedOrders(runId);
});

/// Cancels one queued order and refreshes everything its cash touched.
///
/// Returns the SERVER's verdict, not "the call succeeded". An order that
/// filled between the list render and the tap comes back `cancelled: false`,
/// and the caller must be able to tell the player that rather than showing a
/// cancellation that did not happen.
Future<bool> cancelGamesQueuedOrder(
  WidgetRef ref, {
  required String runId,
  required String orderId,
}) async {
  final api = ref.read(apiClientProvider);
  final cancelled = await api.gamesCancelQueuedOrder(
    runId: runId,
    orderId: orderId,
  );
  ref.invalidate(gamesQueuedOrdersProvider(runId));
  // The run detail carries `cash_committed`/`cash_available`, so a cancel
  // changes what the ticket may size against — refresh it either way, since
  // a `cancelled: false` means the order FILLED, which moves cash too.
  ref.invalidate(gamesRunDetailProvider(runId));
  ref.invalidate(gamesRunsProvider);
  return cancelled;
}

/// The field board — `GET /v1/games/runs/{run_id}/board`.
///
/// Deliberately NOT folded into [gamesRunDetailProvider]: the board reads
/// every entrant's NAV series, so it is the heaviest games call there is, and
/// the run detail is re-read on every size drag of the ticket.
///
/// `.autoDispose` and no polling. The standings move once per US close (design
/// §10 — one rank beat per close, never per tick), so a timer here would spend
/// battery re-fetching a number that cannot have changed, and would make a
/// contest feel like a slot machine besides.
final gamesBoardProvider =
    FutureProvider.autoDispose.family<GameBoard, String>((ref, runId) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesBoard(runId);
});

/// The house desks' published rules — `GET /v1/games/desks`.
///
/// Not `.autoDispose`: the roster changes only when we ship a new desk, and
/// the rules sheet is opened from several places (board row, entry screen,
/// Close). Keeping it alive means the second open is instant.
final gamesDesksProvider = FutureProvider<List<GameDeskProfile>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesDesks();
});

// ── The Close and the Record (CR109 slice 3) ────────────────────────────

/// `GET /v1/games/runs/{run_id}/close` — read once per Close screen visit;
/// `.autoDispose` so a stale ceremony payload never survives past the
/// screen that showed it.
final gamesCloseProvider =
    FutureProvider.autoDispose.family<GameCloseResult, String>((ref, runId) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesClose(runId);
});

final gamesRecordProvider =
    FutureProvider.autoDispose<GameRecord>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesRecord();
});

final gamesRecordPrsProvider =
    FutureProvider.autoDispose<List<GamePersonalRecord>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.gamesRecordPrs();
});

// ── The no-rules disclosure's "seen" flag (§7, §13.3) ───────────────────
//
// Full text on first entry, a compressed chip on every entry after. Same
// SharedPreferences-flag shape as onboarding's `_kOnboardingDoneKey`
// (onboarding_providers.dart) — a plain boolean is the right amount of
// machinery for "has this device seen it once", and there is nothing
// server-side to keep in sync (the disclosure is copy, not an entitlement).
const _kGamesDisclosureSeenKey = 'ami_games_disclosure_seen';

Future<bool> gamesDisclosureSeen() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getBool(_kGamesDisclosureSeenKey) ?? false;
}

Future<void> markGamesDisclosureSeen() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setBool(_kGamesDisclosureSeenKey, true);
}

/// One step of the 3-tap ticket (§5.4). TAP 1 sets [ticker]; TAP 2 sets
/// [sizePct] (a size chip — instant, no round trip, per the design's
/// "client-side, cash and holdings cache so the size chips compute with
/// zero round trips" rule); TAP 3 calls [GamesTicketNotifier.fetchQuote]
/// for the confirm card's numbers, then [GamesTicketNotifier.confirm]
/// submits.
@immutable
class GamesTicketState {
  const GamesTicketState({
    this.ticker,
    this.side = 'buy',
    this.sizePct,
    this.quote,
    this.quoting = false,
    this.submitting = false,
    this.result,
    this.error,
  });

  final String? ticker;
  /// 'buy' | 'sell'.
  final String side;
  /// 10 | 25 | 50 | 100 — a percentage of the run's current cash.
  final double? sizePct;
  final GameTradeQuote? quote;
  final bool quoting;
  final bool submitting;
  final GameTradeResult? result;
  final String? error;

  /// 1 = picking a ticker, 2 = picking a size, 3 = confirming — drives which
  /// tap the ticket screen renders.
  int get step {
    if (ticker == null || ticker!.isEmpty) return 1;
    if (sizePct == null) return 2;
    return 3;
  }

  GamesTicketState copyWith({
    String? ticker,
    String? side,
    double? sizePct,
    GameTradeQuote? quote,
    bool? quoting,
    bool? submitting,
    GameTradeResult? result,
    String? error,
    bool clearQuote = false,
    bool clearError = false,
  }) {
    return GamesTicketState(
      ticker: ticker ?? this.ticker,
      side: side ?? this.side,
      sizePct: sizePct ?? this.sizePct,
      quote: clearQuote ? null : (quote ?? this.quote),
      quoting: quoting ?? this.quoting,
      submitting: submitting ?? this.submitting,
      result: result ?? this.result,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class GamesTicketNotifier extends StateNotifier<GamesTicketState> {
  GamesTicketNotifier(this._ref, this.runId) : super(const GamesTicketState());

  final Ref _ref;
  final String runId;

  /// TAP 1. A fresh ticker resets size/quote/result — a size chip or a
  /// stale quote priced against the PREVIOUS ticker must never survive a
  /// ticker change.
  void pickTicker(String ticker) {
    final t = ticker.trim().toUpperCase();
    state = GamesTicketState(ticker: t.isEmpty ? null : t, side: state.side);
  }

  /// Switching side clears the size and the quote — a size chip means
  /// "percent of cash" on a buy and "percent of the position" on a sell, so
  /// carrying one across would silently change what the number means, and a
  /// quote priced for the other direction is worse than none.
  void pickSide(String side) {
    state = GamesTicketState(ticker: state.ticker, side: side);
  }

  /// TAP 2 — instant, no network call (the size chips are pre-computed
  /// against a cash figure the screen already has).
  void pickSize(double pct) {
    state = state.copyWith(sizePct: pct, clearQuote: true, clearError: true);
  }

  /// TAP 3's data fetch. [cashAvailable] is the run's current cash; the
  /// screen supplies it from [gamesRunDetailProvider] so this notifier
  /// stays a pure request/response shape with no cached copy of the run to
  /// go stale.
  /// [heldQuantity] is the shares currently held of [state.ticker] — required
  /// on the SELL side, ignored on the buy side.
  ///
  /// The two sides divide up different things, and conflating them is what
  /// made selling impossible for as long as it was. A buy divides CASH: 25%
  /// means a quarter of what is available to deploy. A sell divides the
  /// POSITION: 25% means a quarter of the shares held, and 100% means close
  /// it. Sizing a sell against cash would be nonsense in the ordinary case
  /// and impossible in the important one — a player whose cash is fully
  /// committed has exactly 0 to size against, and closing a position is the
  /// one action they most need.
  Future<void> fetchQuote({
    required double? cashAvailable,
    double? heldQuantity,
  }) async {
    final ticker = state.ticker;
    final pct = state.sizePct;
    if (ticker == null || pct == null) return;

    if (state.side == 'sell') {
      // NULL means the holdings have not arrived; 0 means there is nothing to
      // sell. Same null-vs-zero split as the cash guard below, for the same
      // reason — one is something to wait for, the other is an answer.
      if (heldQuantity == null) {
        state = state.copyWith(quoting: true, clearQuote: true, clearError: true);
        return;
      }
      if (heldQuantity <= 0) {
        state = state.copyWith(
          quoting: false,
          clearQuote: true,
          error: 'You hold none of $ticker to sell.',
        );
        return;
      }
      // 4dp matches `game_queued_orders.quantity`'s Numeric(12, 4), so the
      // number quoted is exactly the number that can be stored and filled.
      final shares = double.parse((heldQuantity * (pct / 100)).toStringAsFixed(4));
      state = state.copyWith(quoting: true, clearError: true);
      try {
        final api = _ref.read(apiClientProvider);
        final quote = await api.gamesTradeQuote(
          runId: runId, ticker: ticker, side: 'sell', quantity: shares,
        );
        state = state.copyWith(quote: quote, quoting: false);
      } catch (e) {
        state = state.copyWith(
          quoting: false,
          error: friendlyError(e, action: 'price that trade'),
        );
      }
      return;
    }

    // Refuse to ask for a quote on nothing.
    //
    // The screen's cash read used to collapse to 0 while the run detail was
    // refetching (see the `valueOrNull` note in the ticket screen), and this
    // dutifully sent `notional: 0`. The API refused it with a 422 — correctly,
    // that guard exists because zero-share orders once queued silently — and
    // the player saw "that request wasn't accepted. Check the details",
    // pointing them at a ticker and a size that were both fine.
    //
    // Both halves are worth keeping. The screen no longer loses the value,
    // and this can no longer send a request that cannot succeed no matter
    // what a future caller passes in. Staying in `quoting` is the honest
    // state: cash is genuinely still arriving, and the confirm card renders
    // that as the loading it is.
    // NULL means "the run detail has not arrived", which is genuinely
    // something to wait for. Staying in `quoting` renders as the loading it
    // is, and the confirm card re-fires when the value lands.
    if (cashAvailable == null) {
      state = state.copyWith(quoting: true, clearQuote: true, clearError: true);
      return;
    }

    // ZERO is not something to wait for — it is an answer. The first version
    // of this guard treated the two the same, so a player whose cash was
    // fully committed to queued orders watched a spinner turn forever
    // (Saiful, build 78). The screen refuses to render the confirm step at
    // all in that case; this is the backstop for any other caller, and it
    // must end in a state the UI can draw, never in perpetual loading.
    if (cashAvailable <= 0) {
      state = state.copyWith(
        quoting: false,
        clearQuote: true,
        error: 'No AMI Cash available to deploy.',
      );
      return;
    }

    state = state.copyWith(quoting: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final notional = cashAvailable * (pct / 100);
      final quote = await api.gamesTradeQuote(
        runId: runId,
        ticker: ticker,
        side: state.side,
        notional: notional,
      );
      state = state.copyWith(quote: quote, quoting: false);
    } catch (e) {
      state = state.copyWith(
        quoting: false,
        error: friendlyError(e, action: 'price that trade'),
      );
    }
  }

  /// TAP 3's submit. Places (or, out of market hours, queues — §5.1) the
  /// exact SHARE COUNT the confirm card showed.
  ///
  /// Shares, not the notional: the backend refuses to price a queued order,
  /// so it cannot convert dollars for us, and the quote already did that
  /// conversion at a price the player saw. Sending `quote.quantity` means the
  /// order placed is exactly the one on the card.
  Future<GameTradeResult?> confirm() async {
    final ticker = state.ticker;
    final quote = state.quote;
    if (ticker == null || quote == null) return null;
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final result = await api.gamesTrade(
        runId: runId,
        ticker: ticker,
        side: state.side,
        quantity: quote.shares,
      );
      state = state.copyWith(submitting: false, result: result);
      _ref.invalidate(gamesRunDetailProvider(runId));
      _ref.invalidate(gamesRunsProvider);
      // Most orders from this audience QUEUE rather than fill (§5.1), so the
      // orders list is the surface that just changed — refreshing only the
      // run detail would leave the player's new order invisible on the very
      // screen built to show it.
      _ref.invalidate(gamesQueuedOrdersProvider(runId));
      return result;
    } catch (e) {
      state = state.copyWith(
        submitting: false,
        error: friendlyError(e, action: 'place that trade'),
      );
      return null;
    }
  }

  void reset() => state = const GamesTicketState();
}

final gamesTicketProvider = StateNotifierProvider.autoDispose
    .family<GamesTicketNotifier, GamesTicketState, String>(
        (ref, runId) => GamesTicketNotifier(ref, runId));
