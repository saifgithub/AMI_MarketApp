/// CR178 — the INSIGHTS fetch.
///
/// Its own read rather than reuse of `journalNotifierProvider.entries`: the
/// Journal list is filtered by the user's own chips and search box, so
/// aggregating it would silently describe *"your last 100 room runs"* under a
/// heading that says decisions — a number computed over a slice the reader
/// cannot see. That is the same failure the window label exists to prevent, one
/// level down.
///
/// `autoDispose` so opening the segment again re-reads: the aggregate is stale
/// the moment the user closes a trade, and a card that quietly describes
/// yesterday is worse than a spinner.
library;

import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final insightsProvider = FutureProvider.autoDispose<InsightsData>((ref) async {
  // DEF173/DEF202 — `plan` is a required parameter on the client and is
  // re-derived server-side from the authenticated user, so a wrong value here
  // cannot widen retention. It still must not be guessed: watching the mandate
  // means this re-runs once the real plan lands rather than aggregating over
  // whatever a default returned.
  final plan = ref.watch(mandateNotifierProvider).mandate?.plan;
  if (plan == null) return const InsightsData(entryCount: 0);
  // Deliberately no try/catch: the raw error propagates and the widget's error
  // branch runs it through `friendlyError`. Wrapping it here in an `Exception`
  // would put a humanised sentence inside `Exception: …`, and the DEF148 guard
  // is right that what reaches the user must go through one place.
  final api = ref.read(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  final resp = await api.listJournal(
    userId: userId,
    plan: plan,
    limit: kInsightsWindow,
  );
  return buildInsights(resp.entries);
});
