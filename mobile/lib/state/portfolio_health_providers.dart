/// CR136 M09 — providers for the Health card (free tiles GET) and Finding generation (gated POST; same-day POST is idempotent server-side).
///
/// Two providers rather than one notifier, mirroring `sectorAllocationProvider`
/// (`sim_providers.dart`): both are read-only endpoints the holdings list does
/// not otherwise need, and neither holds state between screens.
///
/// [healthFindingProvider] wraps a POST, which is normally the wrong shape for
/// a `FutureProvider` — a rebuild would re-submit. It is safe here for one
/// specific reason: M07 §3.5 makes a same-day POST idempotent, returning the
/// stored entry with `created:false`, no LLM call, no write and no budget
/// spent. If that ever stops being true, this must become a notifier with an
/// explicit trigger.
library;

import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The tiles feed. Free in every gate mode — the CTA state it carries is
/// reported, not applied (M07 §3.4).
final portfolioHealthProvider =
    FutureProvider.autoDispose<PortfolioHealth>((ref) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.portfolioHealth(userId);
});

/// Generates today's Finding, or replays it. Gate refusals surface as an
/// `AsyncError` carrying the `DioException`, so the Finding screen can read
/// the server's own `detail.code` instead of inventing one.
final healthFindingProvider =
    FutureProvider.autoDispose<HealthFinding>((ref) async {
  final api = ref.watch(apiClientProvider);
  final userId = await DeviceUser.getOrCreate();
  return api.generateHealthFinding(userId);
});
