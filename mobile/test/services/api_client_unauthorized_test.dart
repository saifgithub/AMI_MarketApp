/// CR125 — `shouldRecoverFromUnauthorized`, the pure decision behind
/// `_AuthInterceptor`'s 401-recovery guard. Same technique
/// `version_gate_interceptor_test.dart` uses for the 426 gate: the decision
/// is extracted `@visibleForTesting` so it's checked directly rather than
/// through a live Dio round trip.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CR125 — shouldRecoverFromUnauthorized', () {
    test('fires for a guarded route with a bearer never reported before', () {
      expect(
        shouldRecoverFromUnauthorized(
          path: '/v1/mandate/abc',
          bearerToken: 'token-a',
          lastUnauthorizedToken: null,
        ),
        isTrue,
      );
    });

    test('does not fire for any /v1/auth/* route', () {
      for (final path in [
        '/v1/auth/anon',
        '/v1/auth/magic_link/start',
        '/v1/auth/magic_link/verify',
        '/v1/auth/apple',
        '/v1/auth/google',
        '/v1/auth/session',
        '/v1/auth/me',
      ]) {
        expect(
          shouldRecoverFromUnauthorized(
            path: path,
            bearerToken: 'token-a',
            lastUnauthorizedToken: null,
          ),
          isFalse,
          reason: '$path owns its own error handling',
        );
      }
    });

    test('does not fire when no bearer was attached', () {
      expect(
        shouldRecoverFromUnauthorized(
          path: '/v1/mandate/abc',
          bearerToken: null,
          lastUnauthorizedToken: null,
        ),
        isFalse,
      );
    });

    test('retry-loop guard: does not fire twice for the same token', () {
      expect(
        shouldRecoverFromUnauthorized(
          path: '/v1/mandate/abc',
          bearerToken: 'token-a',
          lastUnauthorizedToken: 'token-a',
        ),
        isFalse,
      );
    });

    test('fires again for a genuinely different (freshly re-issued) token', () {
      expect(
        shouldRecoverFromUnauthorized(
          path: '/v1/mandate/abc',
          bearerToken: 'token-b',
          lastUnauthorizedToken: 'token-a',
        ),
        isTrue,
      );
    });
  });
}
