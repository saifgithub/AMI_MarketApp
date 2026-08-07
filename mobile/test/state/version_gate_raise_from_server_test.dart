/// CR121 audit MAJOR — a 426 from ANY request must reach the user as the
/// block screen, not as generic "that request wasn't accepted" copy.
///
/// The middleware's stated reason to exist is that "a patched binary that
/// never calls the floor endpoint at all still cannot transact". That was
/// true — the request failed — but the promised UX never appeared, because
/// `VersionGateController.check()` runs at exactly two moments (launch and
/// foreground-resume) and every other call funnelled its error through
/// `friendlyError`, which had no idea what a 426 meant. So a floor raised
/// while the app was open and foregrounded produced a refusal with no
/// headline, no store link, and advice to re-check details that were never
/// the problem.
///
/// Two halves are tested here: the copy (`friendlyError`/`isRetryable` know
/// what a 426 is) and the routing (`raiseFromServer` puts the controller
/// into the block state carrying the server's own per-raise message).
library;

import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/onboarding_providers.dart' show apiClientProvider;
import 'package:ami_trade/state/version_gate_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Never reaches the network: the launch-time `check()` the provider factory
/// fires would otherwise make a real call. Its failure is swallowed by the
/// fail-open catch, which is exactly what we want here — every test below
/// drives `raiseFromServer` explicitly.
class _InertApiClient extends ApiClient {
  @override
  Future<ReleaseFloorResponse> getReleaseFloor({
    required int? build,
    required String locale,
    required String platform,
  }) {
    throw StateError('no network in tests');
  }
}

VersionGateController _controller() {
  final container = ProviderContainer(overrides: [
    apiClientProvider.overrideWithValue(_InertApiClient()),
  ]);
  addTearDown(container.dispose);
  return container.read(versionGateControllerProvider.notifier);
}

const _blocked = UpgradeRequiredException(
  minBuild: 58,
  action: 'block',
  headline: 'Update required',
  body: 'Build 57 can no longer place trades.',
  storeUrl: 'https://testflight.apple.com/join/ABC123',
);

void main() {
  group('friendlyError knows what a 426 is', () {
    test('names the update, instead of blaming the request', () {
      final copy = friendlyError(_blocked, action: 'place that trade');
      expect(copy, contains('out of date'));
      expect(copy, contains('Update'));
      // The pre-fix copy, which told the user to re-check details that were
      // never the problem about a request that can never succeed.
      expect(copy, isNot(contains("wasn't accepted")));
      expect(copy, isNot(contains('Check the details')));
    });

    test('reads the annotation off a DioException too', () {
      // This is the shape call sites actually catch: the interceptor puts the
      // exception in `DioException.error`, it does not replace it.
      final err = DioException(
        requestOptions: RequestOptions(path: '/v1/sim/trade'),
        error: _blocked,
      );
      expect(
        friendlyError(err, action: 'place that trade'),
        contains('out of date'),
      );
    });

    test('never offers a retry — the same request cannot succeed', () {
      // DEF151's lesson: a retry affordance on a permanently-rejected call is
      // a promise the app cannot keep. Nothing about this request changes
      // until the app itself is updated.
      expect(isRetryable(_blocked), isFalse);
    });
  });

  group('raiseFromServer', () {
    test('blocks, carrying the server\'s own per-raise message', () {
      final c = _controller();
      expect(c.state.isBlocked, isFalse);

      c.raiseFromServer(_blocked);

      expect(c.state.isBlocked, isTrue);
      expect(c.state.floor!.minBuild, 58);
      expect(c.state.floor!.headline, 'Update required');
      expect(c.state.floor!.storeUrl, 'https://testflight.apple.com/join/ABC123');
    });

    test('a non-block action is not escalated into a hard block', () {
      // The middleware only emits 426 for the block case today. `action` is
      // carried rather than assumed so a future server that reuses 426 for
      // something softer cannot be silently mis-rendered as a hard block —
      // the one direction where guessing wrong is unrecoverable for the user.
      final c = _controller();
      c.raiseFromServer(const UpgradeRequiredException(action: 'nag'));
      expect(c.state.isBlocked, isFalse);
    });

    test('a second 426 does not overwrite the first block', () {
      // Several in-flight requests all 426 at once. The first raise carries
      // the real per-raise copy; a later bodyless one must not blank it.
      final c = _controller();
      c.raiseFromServer(_blocked);
      c.raiseFromServer(const UpgradeRequiredException());
      expect(c.state.floor!.headline, 'Update required');
    });
  });

  group('the model boundary the 426 body crosses', () {
    test('a 426 detail parses into the same shape the endpoint returns', () {
      // One screen renders either source, so the two must agree.
      final fromGate = UpgradeRequiredException.fromJson({
        'detail': {
          'min_build': 58,
          'action': 'block',
          'headline': 'Update required',
          'body': 'Build 57 can no longer place trades.',
          'store_url': null,
        },
      });
      final fromEndpoint = ReleaseFloorResponse.fromJson({
        'min_build': 58,
        'action': 'block',
        'headline': 'Update required',
        'body': 'Build 57 can no longer place trades.',
        'store_url': null,
      });
      expect(fromGate.minBuild, fromEndpoint.minBuild);
      expect(fromGate.action, fromEndpoint.action);
      expect(fromGate.headline, fromEndpoint.headline);
      expect(fromGate.body, fromEndpoint.body);
    });
  });
}
