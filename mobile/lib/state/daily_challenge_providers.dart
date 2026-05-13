/// Riverpod state for the daily challenge card on the Floor tab.
///
/// Fetches today's challenge from /v1/daily_challenge/today on first
/// read. The screen-level submit state (selected option + submitted)
/// is local UI state, not Riverpod, since it doesn't survive a tab
/// switch by design — every day is a fresh attempt.
library;

import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final dailyChallengeTodayProvider =
    FutureProvider.autoDispose<DailyChallengeWithDate?>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.dailyChallengeToday();
});
