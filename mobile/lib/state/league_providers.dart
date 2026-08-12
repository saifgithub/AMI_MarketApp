/// CR010 (B2/B5) — league + streak providers. Read by the Floor streak chip
/// now, and by the league surface (CR011) later. autoDispose so a Floor
/// revisit refetches; invalidate after any point-awarding action (e.g. a
/// daily-challenge attempt) so the streak/points reflect it immediately.
library;

import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// CR109 slice 7, first half — survive a backend that no longer has a league.
///
/// Amendment A replaces the reputation league with the P&L game, which means
/// `/v1/league/*` eventually stops existing. **The two halves of that removal
/// cannot ship together**: the backend goes out by rsync the same day, and
/// the client goes out through store review days later. So for a window
/// measured in days, every INSTALLED build is talking to a backend with no
/// league in it.
///
/// A 404 is therefore an expected answer here, not a failure, and it is
/// translated into "there is nothing to show" rather than an error state.
/// Every consumer already reads these through `.valueOrNull`, so a null
/// simply removes the streak chip — which is the correct end state anyway.
///
/// Any OTHER error still propagates. A 500 or a dropped connection is not
/// "the league was removed", and swallowing those would hide a real outage
/// behind the same silence — the CR040 line between a planned absence and a
/// broken one.
Future<T?> _nullOn404<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on DioException catch (e) {
    if (e.response?.statusCode == 404) return null;
    rethrow;
  }
}

final leagueMeProvider = FutureProvider.autoDispose<LeagueMe?>((ref) async {
  final api = ref.watch(apiClientProvider);
  return _nullOn404(() => api.leagueMe());
});

final standingsProvider =
    FutureProvider.autoDispose<LeagueStandings?>((ref) async {
  final api = ref.watch(apiClientProvider);
  // Already nullable on the wire — a league with no cohort yet answers null —
  // so the 404 case folds into the answer it already has for "nothing here".
  return _nullOn404<LeagueStandings?>(() => api.leagueStandings());
});
