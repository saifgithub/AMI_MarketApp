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
  Future<void> fetchQuote({required double cashAvailable}) async {
    final ticker = state.ticker;
    final pct = state.sizePct;
    if (ticker == null || pct == null) return;
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
  /// exact notional the confirm card showed.
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
        notional: quote.notional,
      );
      state = state.copyWith(submitting: false, result: result);
      _ref.invalidate(gamesRunDetailProvider(runId));
      _ref.invalidate(gamesRunsProvider);
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
