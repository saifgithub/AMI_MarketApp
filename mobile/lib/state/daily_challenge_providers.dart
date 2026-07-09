/// Riverpod state for the daily challenge card on the Floor tab.
///
/// Fetches today's challenge from /v1/daily_challenge/today, which now
/// carries the caller's server-truth `my_attempt` (CR010 B5) — so a
/// submitted answer + result survives a tab switch or restart. Only the
/// pre-submit selection (before the user taps SUBMIT) stays local UI state
/// in the screen, since it has nothing to persist yet.
library;

import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final dailyChallengeTodayProvider =
    FutureProvider.autoDispose<DailyChallengeWithDate?>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.dailyChallengeToday();
});
