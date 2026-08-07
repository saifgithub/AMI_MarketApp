/// CR121 — `_VersionGateInterceptor` raises the gate on a 426 and leaves
/// every other status untouched.
///
/// The interceptor class itself is private to `api_client.dart` (same
/// shape as DEF073's `_ServerErrorInterceptor`); what's tested here is its
/// decision function, `upgradeRequiredExceptionFor` — exported
/// `@visibleForTesting` for exactly this reason, mirroring how
/// `parseRoomSseEvent` is tested directly rather than through a live
/// stream. No live server involved: `DioException`/`Response` objects are
/// constructed by hand, same technique `friendly_error_test.dart` uses for
/// DEF073's own decision.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

DioException _errorWithStatus(int? status, {Object? data}) => DioException(
      requestOptions: RequestOptions(path: '/v1/sim/portfolio/x'),
      response: status == null
          ? null
          : Response<Object?>(
              requestOptions: RequestOptions(path: '/v1/sim/portfolio/x'),
              statusCode: status,
              data: data,
            ),
    );

void main() {
  group('CR121 — upgradeRequiredExceptionFor (the 426 gate decision)', () {
    test('raises on 426 and carries the server-shaped detail', () {
      final err = _errorWithStatus(426, data: {
        'detail': {
          'min_build': 58,
          'recommended_build': 61,
          'action': 'block',
          'headline': 'Update required',
          'body': 'This build is no longer supported.',
          'store_url': 'https://testflight.apple.com/join/ABC123',
        },
      });

      final upgrade = upgradeRequiredExceptionFor(err);

      expect(upgrade, isNotNull);
      expect(upgrade!.minBuild, 58);
      expect(upgrade.recommendedBuild, 61);
      expect(upgrade.action, 'block');
      expect(upgrade.headline, 'Update required');
      expect(upgrade.body, 'This build is no longer supported.');
      expect(upgrade.storeUrl, 'https://testflight.apple.com/join/ABC123');
    });

    test('426 with an unparseable body still raises, with null fields', () {
      final err = _errorWithStatus(426, data: 'not json');
      final upgrade = upgradeRequiredExceptionFor(err);
      expect(upgrade, isNotNull);
      expect(upgrade!.minBuild, isNull);
      expect(upgrade.action, 'block');
    });

    test('does not raise on 2xx/4xx/5xx statuses other than 426', () {
      for (final status in [200, 401, 402, 404, 409, 422, 429, 500, 502, 503]) {
        expect(upgradeRequiredExceptionFor(_errorWithStatus(status)), isNull,
            reason: 'status $status must not raise the version gate');
      }
    });

    test('does not raise when there is no response at all (e.g. timeout)', () {
      expect(upgradeRequiredExceptionFor(_errorWithStatus(null)), isNull);
    });
  });

  group('CR121 — upgradeRequiredFrom', () {
    test('unwraps the annotated DioException', () {
      const inner = UpgradeRequiredException(minBuild: 58, action: 'block');
      final wrapped = DioException(
        requestOptions: RequestOptions(path: '/x'),
        error: inner,
      );
      expect(upgradeRequiredFrom(wrapped), same(inner));
    });

    test('returns null for an unrelated error', () {
      expect(upgradeRequiredFrom(Exception('boom')), isNull);
    });
  });
}
