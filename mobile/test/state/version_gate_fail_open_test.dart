/// CR121 — the version gate fails OPEN.
///
/// Simulates the floor lookup raising (network unreachable, malformed JSON,
/// a melehost outage) and asserts: (1) `VersionGateController`'s state never
/// flips to blocked/nagging — the app proceeds exactly as if nothing were
/// gated — and (2) the failure is logged, not silently swallowed. A
/// fail-CLOSED gate here would turn any backend outage into a simultaneous
/// brick of every installed client (CLAUDE.md's degrade-loudly rule is
/// deliberately NOT followed for this one path — see the CR121 spec's
/// "Fail-open, loudly" section and `version_gate_providers.dart`'s
/// docstring).
///
/// `ApiClient`'s REST calls have no injectable transport (unlike its SSE
/// methods), so the throwing double subclasses `ApiClient` and overrides
/// just [ApiClient.getReleaseFloor] — no live network call either way.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/state/onboarding_providers.dart' show apiClientProvider;
import 'package:ami_trade/state/version_gate_providers.dart';
import 'package:flutter/foundation.dart' show debugPrint, DebugPrintCallback;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _ThrowingApiClient extends ApiClient {
  @override
  Future<ReleaseFloorResponse> getReleaseFloor({
    required int? build,
    required String locale,
    required String platform,
  }) {
    throw StateError('simulated: floor lookup unreachable');
  }
}

void main() {
  test('a lookup failure leaves the gate unraised and logs the failure',
      () async {
    final logs = <String>[];
    final DebugPrintCallback original = debugPrint;
    debugPrint = (String? message, {int? wrapWidth}) {
      if (message != null) logs.add(message);
    };

    final container = ProviderContainer(overrides: [
      apiClientProvider.overrideWithValue(_ThrowingApiClient()),
    ]);
    addTearDown(() {
      debugPrint = original;
      container.dispose();
    });

    // Explicit call, awaited — deterministic, independent of the provider
    // factory's own `Future.microtask(controller.check)` launch-time fire.
    await container
        .read(versionGateControllerProvider.notifier)
        .check();

    final state = container.read(versionGateControllerProvider);
    expect(state.isBlocked, isFalse);
    expect(state.isNagging, isFalse);

    expect(
      logs.any((l) => l.contains('version gate check failed')),
      isTrue,
      reason: 'the failure must be logged, never silently swallowed',
    );
  });
}
