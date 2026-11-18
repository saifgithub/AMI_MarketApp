// DEF485 — creating a price alert intermittently failed client-side with "the
// connection is too slow" (3 of 5 device runs) while the server logged no
// matching request: a connect timeout, i.e. the request never left the phone.
// A connect timeout is the one failure that provably did not deliver the
// request, so the client retries it exactly once — safe even for a POST
// create. Everything that might have delivered it (receive/send timeouts,
// connection errors) must NOT be retried, or a create could be duplicated.

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/services/api/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this.script);

  /// One entry per request: an exception to throw, or null to answer 200.
  final List<DioExceptionType?> script;
  int calls = 0;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    final step = calls < script.length ? script[calls] : null;
    calls++;
    if (step != null) {
      throw DioException(requestOptions: options, type: step);
    }
    return ResponseBody.fromString(
      jsonEncode({
        'id': 'a1',
        'user_id': 'u1',
        'ticker': 'AAPL',
        'threshold_type': 'manual_above',
        'threshold_price': 200.0,
        'status': 'active',
        'created_at': '2026-10-20T00:00:00+00:00',
      }),
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Future<void> _create(ApiClient api) => api.createPriceAlert(
      'u1',
      ticker: 'AAPL',
      thresholdType: 'manual_above',
      thresholdPrice: 200,
    );

void main() {
  test('one connect timeout is retried and the create succeeds', () async {
    final adapter = _ScriptedAdapter([DioExceptionType.connectionTimeout]);
    final api = ApiClient(baseUrl: 'http://test', dioAdapter: adapter);

    await _create(api);

    expect(adapter.calls, 2);
  });

  test('two connect timeouts in a row still fail, after exactly one retry',
      () async {
    final adapter = _ScriptedAdapter([
      DioExceptionType.connectionTimeout,
      DioExceptionType.connectionTimeout,
    ]);
    final api = ApiClient(baseUrl: 'http://test', dioAdapter: adapter);

    await expectLater(
      _create(api),
      throwsA(isA<DioException>()
          .having((e) => e.type, 'type', DioExceptionType.connectionTimeout)),
    );
    expect(adapter.calls, 2);
  });

  for (final type in [
    DioExceptionType.receiveTimeout,
    DioExceptionType.sendTimeout,
    DioExceptionType.connectionError,
  ]) {
    test('${type.name} is NOT retried (the create may have been delivered)',
        () async {
      final adapter = _ScriptedAdapter([type]);
      final api = ApiClient(baseUrl: 'http://test', dioAdapter: adapter);

      await expectLater(_create(api), throwsA(isA<DioException>()));
      expect(adapter.calls, 1);
    });
  }
}
