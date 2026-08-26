/// The signed-in user's own identity — today, just the handle.
///
/// **CR109 slice 7.** This replaces `league_providers.dart`, which is gone with
/// the reputation league Amendment A retired. The handle is not a league
/// artifact: it is the player's public name, and the games board renders and
/// sorts by it, so it outlived the surface it used to be fetched from.
///
/// Deliberately NOT `_nullOn404`-wrapped the way `leagueMeProvider` was. That
/// wrapper existed because the league was being removed underneath installed
/// clients, so a 404 was an expected answer. `/v1/me` is not going anywhere —
/// a 404 here is a real failure and must read as one (CR040).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ami_trade/state/onboarding_providers.dart';

final myHandleProvider = FutureProvider.autoDispose<String?>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.myHandle();
});
