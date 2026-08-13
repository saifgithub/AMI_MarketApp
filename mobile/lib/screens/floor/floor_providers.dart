/// CR173 slice 2 — what the Floor's carousel reads.
///
/// Both providers sit on paths the app already has: the sim portfolio the
/// PORTFOLIO tab renders, and the `ROOM_RUN` journal rows the Decision Journal
/// reads. §4's inventory allows exactly one candidate backend surface in this
/// CR — the price lookup for the calls card — and even that reuses
/// `/v1/sim/quote/{ticker}` rather than adding an endpoint.
library;

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
