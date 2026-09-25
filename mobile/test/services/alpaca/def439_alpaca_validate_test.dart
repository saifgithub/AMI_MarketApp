/// DEF439 round 2 (auditor u66 MINOR-1) — `AlpacaClient.validate()` (the
/// API-key path) had no direct test: every existing test overrides `validate`
/// with a fake (`_RecordingAlpacaClient` in
/// `def439_alpaca_paper_only_link_test.dart`), so nothing exercised the real
/// method against a live Dio response. Auditor mutation M8 (swallowing the
/// `DioException` inside `validate()`, making it fail OPEN — a bad key pair
/// would then read as "valid") survived all 170 targeted tests for exactly
/// that reason.
///
/// This file drives the real `AlpacaClient.validate()` with a fake HTTP
/// adapter (same `_RecordingAdapter` convention
/// `def439_alpaca_oauth_paper_validate_test.dart` and
/// `cr234_alpaca_orders_test.dart` established), so a swallowed exception
/// here is a real regression, not a fake-client gap.
///
/// The auditor also notes M16 (API-key save stores a hardcoded live host
/// instead of the validated one) survives — that a live host would then
/// still be refused downstream by `isLinkedToPaperAccount`'s host re-check,
/// making it a defence-in-depth gap rather than a live path. Not repinned
/// here; `def439_alpaca_linked_paper_only_test.dart` already pins that
/// downstream re-check.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _RecordingAdapter implements HttpClientAdapter {
  final List<({String method, String path, Map<String, String> headers})>
      calls = [];
  int statusCode = 200;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add((
      method: options.method,
      path: options.path,
      headers: options.headers.map((k, v) => MapEntry(k, v.toString())),
    ));
    final bytes = utf8.encode(jsonEncode(<String, dynamic>{}));
    if (statusCode >= 400) {
      throw DioException(
        requestOptions: options,
        response: Response(
          requestOptions: options,
          statusCode: statusCode,
          data: <String, dynamic>{'message': 'unauthorized'},
        ),
      );
    }
    return ResponseBody.fromBytes(bytes, statusCode, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('validate() hits GET /v2/account with the key/secret headers',
      () async {
    final adapter = _RecordingAdapter();
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await client.validate('PKTESTKEYID', 'test-secret',
        baseUrl: 'https://paper-api.alpaca.markets');

    final call = adapter.calls.single;
    expect(call.method, 'GET');
    expect(call.path, 'https://paper-api.alpaca.markets/v2/account');
    expect(call.headers['APCA-API-KEY-ID'], 'PKTESTKEYID');
    expect(call.headers['APCA-API-SECRET-KEY'], 'test-secret');
  });

  // DEF439 round 2 MINOR-1 — the regression guard for mutation M8. If
  // `validate()` ever swallows the DioException instead of rethrowing as
  // `AlpacaException`, a bad (or live-rejected-by-paper-host) key pair reads
  // as valid and gets stored. Deleting the `throw AlpacaException(...)` line
  // (or wrapping the whole body in a no-op try/catch) must fail this test.
  test(
      'a 401 from validate() throws an AlpacaException with isAuthFailure — '
      'DEF439 round 2 MINOR-1 (mutation M8 guard)', () async {
    final adapter = _RecordingAdapter()..statusCode = 401;
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await expectLater(
      client.validate('AKLIVEKEYID', 'live-secret',
          baseUrl: 'https://paper-api.alpaca.markets'),
      throwsA(isA<AlpacaException>()
          .having((e) => e.isAuthFailure, 'isAuthFailure', isTrue)),
    );
  });

  test('a network error from validate() throws (not silently swallowed)',
      () async {
    final adapter = _RecordingAdapter()..statusCode = 500;
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await expectLater(
      client.validate('PKTESTKEYID', 'test-secret'),
      throwsA(isA<AlpacaException>()),
    );
  });
}
