/// CR010 (B2/B5) — league + streak providers. Read by the Floor streak chip
/// now, and by the league surface (CR011) later. autoDispose so a Floor
/// revisit refetches; invalidate after any point-awarding action (e.g. a
/// daily-challenge attempt) so the streak/points reflect it immediately.
library;

import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final leagueMeProvider = FutureProvider.autoDispose<LeagueMe>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.leagueMe();
});

final standingsProvider =
    FutureProvider.autoDispose<LeagueStandings?>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.leagueStandings();
});
