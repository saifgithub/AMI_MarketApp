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
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show visibleForTesting;
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
  return fetchHealthFinding(
    generate: () => api.generateHealthFinding(userId),
    tiles: () => api.portfolioHealth(userId),
  );
});

/// DEF515 — a request whose answer never arrived is not a request that failed.
///
/// The Finding POST runs the model and writes the report before it answers. If
/// the phone stops waiting (a receive timeout, a dropped radio, a gateway cut)
/// the server still finishes: the row is written, a trial slot is spent, and
/// the response goes nowhere. AMI-DL-9b hit exactly that — the app said "did
/// not respond" over a Finding that existed and had already been counted.
///
/// So for those errors, and only those, ask the server rather than assume: the
/// tiles are free and report whether today's Finding is stored. When it
/// appears, the same POST replays it (free, ungated, no model call). When it
/// never does within [window], the original error stands — the Finding really
/// was not written and a manual retry is honest.
///
/// Refusals (402/409/429) and anything else with a verdict are rethrown
/// untouched: the screen keys its panels on those.
@visibleForTesting
Future<HealthFinding> fetchHealthFinding({
  required Future<HealthFinding> Function() generate,
  required Future<PortfolioHealth> Function() tiles,
  Duration pollEvery = const Duration(seconds: 5),
  Duration window = const Duration(seconds: 120),
  Future<void> Function(Duration)? wait,
}) async {
  final sleep = wait ?? (d) => Future<void>.delayed(d);
  try {
    return await generate();
  } on DioException catch (e) {
    if (!isOutcomeUnknown(e)) rethrow;
    var waited = Duration.zero;
    while (waited < window) {
      await sleep(pollEvery);
      waited += pollEvery;
      try {
        final health = await tiles();
        if (health.todaysFindingId != null) return await generate();
      } on DioException {
        // The tiles read can fail for the same reason the POST did; keep
        // asking until the window closes.
      }
    }
    rethrow;
  }
}

/// True when [e] says nothing about whether the server acted: the request may
/// have been written, and may have completed, with no answer coming back.
@visibleForTesting
bool isOutcomeUnknown(DioException e) {
  switch (e.type) {
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.connectionError:
    case DioExceptionType.unknown:
      return true;
    case DioExceptionType.badResponse:
      final code = e.response?.statusCode;
      return code == 502 || code == 503 || code == 504 || code == 524;
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.badCertificate:
    case DioExceptionType.cancel:
      return false;
  }
}
