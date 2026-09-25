/// DEF439 — `AlpacaClient.validateOAuthToken`, the OAuth-mode counterpart to
/// `validate()`.
///
/// Alpaca's `/oauth/authorize` documents no `env=paper` selector (see
/// `alpaca_connect_screen.dart`'s file docstring) — which Alpaca account a
/// token resolves to is decided by whichever account the user was logged
/// into in the browser, not by anything AMI's authorize request can pass. So
/// the connect screen verifies the token itself against the paper host
/// before ever storing it, and this file pins that the client method does
/// exactly that: hits `GET /v2/account` on the given (paper) host with a
/// `Bearer` header, and a non-2xx response (a live-account token, rejected
/// by the paper host) surfaces as an `AlpacaException` whose
/// `isAuthFailure` is true for a 401 — same signal the API-key path already
/// gives the connect screen.
///
/// Same fake-`HttpClientAdapter` convention `cr234_alpaca_orders_test.dart`
/// established: capture the exact request Dio sends, never touch the
/// network.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart'
    show kDefaultAlpacaBaseUrl;
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
      headers: options.headers
          .map((k, v) => MapEntry(k, v.toString())),
    ));
    final bytes = utf8.encode(jsonEncode(<String, dynamic>{}));
    return ResponseBody.fromBytes(bytes, statusCode, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('hits GET /v2/account on the given host with a Bearer header',
      () async {
    final adapter = _RecordingAdapter();
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await client.validateOAuthToken('the-access-token',
        baseUrl: 'https://paper-api.alpaca.markets');

    final call = adapter.calls.single;
    expect(call.method, 'GET');
    expect(call.path, 'https://paper-api.alpaca.markets/v2/account');
    expect(call.headers['Authorization'], 'Bearer the-access-token');
  });

  test('defaults to the paper host when none is given', () async {
    final adapter = _RecordingAdapter();
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await client.validateOAuthToken('tok');

    expect(adapter.calls.single.path,
        '$kDefaultAlpacaBaseUrl/v2/account');
  });

  test(
      'a 401 (a live-account token, rejected by the paper host) surfaces as '
      'an AlpacaException with isAuthFailure true', () async {
    final adapter = _RecordingAdapter()..statusCode = 401;
    final dio = Dio()..httpClientAdapter = adapter;
    final client = AlpacaClient(dio: dio);

    await expectLater(
      client.validateOAuthToken('live-token'),
      throwsA(isA<AlpacaException>()
          .having((e) => e.isAuthFailure, 'isAuthFailure', isTrue)),
    );
  });
}
