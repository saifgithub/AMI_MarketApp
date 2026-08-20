/// CR173 slice 2 — what the Floor's carousel reads.
///
/// The original two providers sit on paths the app already has: the sim
/// portfolio the PORTFOLIO tab renders, and the `ROOM_RUN` journal rows the
/// Decision Journal reads. CR183 added the sector-watch read (the one new
/// endpoint the Floor owns) and CR184 added the unactioned-calls view over
/// the same journal rows plus a history read for a PASS's reference close —
/// both reusing existing wire surfaces.
library;

import 'package:ami_trade/models/sector_watch.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// How many calls the card shows. The list screen behind it shows the rest —
/// the card is the answer, not the archive.
const int kCallsCardRows = 2;

/// How far back the calls surfaces look. Same window the Journal reads.
const int kCallsWindow = 50;

final teamCallsProvider =
    FutureProvider.autoDispose<List<TeamCall>>((ref) async {
  // Same reasoning as `insightsProvider`: `plan` is re-derived server-side, so
  // a wrong value here cannot widen retention — but guessing one would
  // aggregate over whatever a default returned, so wait for the real thing.
  final plan = ref.watch(mandateNotifierProvider).mandate?.plan;
  if (plan == null) return const [];
  final api = ref.read(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  final resp =
      await api.listJournal(userId: userId, plan: plan, limit: kCallsWindow);
  return teamCallsFrom(resp.entries);
});

/// The current price for one ticker, or **null** when it could not be read.
///
/// Null rather than a throw and rather than a last-known value: the caller
/// renders a dash and says the reading is unavailable. A delta computed against
/// a stale or defaulted price is the failure §4 names by name — a number that
/// looks measured and is not (CR040).
final callPriceProvider =
    FutureProvider.autoDispose.family<double?, String>((ref, ticker) async {
  try {
    return await ref.read(apiClientProvider).simQuote(ticker);
  } catch (_) {
    return null;
  }
});

/// How many rows the NOT ACTIONED card shows (CR184: "the last two").
const int kUnactionedCardRows = 2;

/// CR184 — the last [kUnactionedCardRows] convenes whose verdict the user
/// never executed, latest per ticker, newest first — never regret-ranked.
/// Derived from the same journal read as the calls card, so the two cards
/// cannot disagree about what a call was (DEF098).
final unactionedCallsProvider =
    FutureProvider.autoDispose<List<TeamCall>>((ref) async {
  final calls = await ref.watch(teamCallsProvider.future);
  return unactionedFrom(calls, limit: kUnactionedCardRows);
});

/// CR184 — a PASS row's reference price: the convene-day close reconstructed
/// from `/v1/sim/history` daily candles, or **null** when it cannot be read
/// honestly (request failed, mock-walk source, no candle before the convene).
/// Null renders as a dash — a delta against a fabricated close is exactly the
/// number-that-looks-measured CR040 forbids.
final conveneCloseProvider = FutureProvider.autoDispose
    .family<({double close, DateTime date})?, ({String ticker, DateTime at})>(
        (ref, k) async {
  try {
    final history = await ref.read(apiClientProvider).simHistory(
        k.ticker, historyPeriodFor(at: k.at, now: DateTime.now()));
    return conveneDayClose(history: history, at: k.at);
  } catch (_) {
    return null;
  }
});

/// CR183 — the SECTOR WATCH read. Errors surface as the provider's error
/// state and the card says the feed could not be read (CR040) — the endpoint
/// itself degrades in-body via `state`, so a thrown error here means the
/// request never came back at all.
final sectorWatchProvider =
    FutureProvider.autoDispose<SectorWatch>((ref) async {
  final api = ref.read(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.sectorWatch(userId);
});
