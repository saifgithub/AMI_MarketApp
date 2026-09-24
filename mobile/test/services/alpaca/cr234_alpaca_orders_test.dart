/// CR234 — `AlpacaClient.orders()` (list) and `cancelOrder()` (cancel), the
/// read/cancel half CR233's real order types made necessary: a limit order
/// could reach Alpaca and rest there with no way in the app to ever see it
/// again.
///
/// Same fake-`HttpClientAdapter` convention `cr233_alpaca_order_types_test.dart`
/// established: capture the exact request Dio sends (method + path + query),
/// return a canned response, never touch the network.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingAdapter implements HttpClientAdapter {
  final List<({String method, String path, Map<String, dynamic> query})> calls = [];
  dynamic nextResponse = const <dynamic>[];
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
      query: options.queryParameters,
    ));
    final bytes = utf8.encode(jsonEncode(nextResponse));
    return ResponseBody.fromBytes(bytes, statusCode,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  group('AlpacaClient.orders — exact GET request', () {
    test('builds GET /v2/orders with status/nested/limit query params', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await client.orders(status: 'open', limit: 50);

      expect(adapter.calls, hasLength(1));
      final call = adapter.calls.single;
      expect(call.method, 'GET');
      expect(call.path, contains('/v2/orders'));
      expect(call.query['status'], 'open');
      expect(call.query['nested'], true);
      expect(call.query['limit'], 50);
    });

    test('defaults to status=open, nested=true, no limit param', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await client.orders();

      final call = adapter.calls.single;
      expect(call.query['status'], 'open');
      expect(call.query['nested'], true);
      expect(call.query.containsKey('limit'), isFalse);
    });

    test('closed/history call passes status=closed and the given limit',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await client.orders(status: 'closed', limit: 50);

      expect(adapter.calls.single.query['status'], 'closed');
      expect(adapter.calls.single.query['limit'], 50);
    });

    test('parses the returned list into AlpacaOrder objects', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter()
        ..nextResponse = [
          {
            'id': 'ord_1',
            'symbol': 'AAPL',
            'side': 'buy',
            'qty': '10',
            'status': 'new',
            'type': 'limit',
            'limit_price': '150.00',
          },
          {
            'id': 'ord_2',
            'symbol': 'MSFT',
            'side': 'sell',
            'qty': '5',
            'status': 'filled',
            'type': 'market',
            'filled_avg_price': '410.25',
          },
        ];
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      final orders = await client.orders();
      expect(orders, hasLength(2));
      expect(orders[0].id, 'ord_1');
      expect(orders[0].limitPrice, 150.0);
      expect(orders[1].filledAvgPrice, 410.25);
    });

    test('throws AlpacaException when unlinked', () async {
      final client = AlpacaClient();
      expect(() => client.orders(), throwsA(isA<AlpacaException>()));
    });
  });

  group('AlpacaOrder.fromJson — nested bracket legs', () {
    test('a bracket parent carries its stop-loss/take-profit legs', () {
      final order = AlpacaOrder.fromJson({
        'id': 'ord_parent',
        'symbol': 'AAPL',
        'side': 'buy',
        'qty': '10',
        'status': 'new',
        'type': 'limit',
        'limit_price': '150.00',
        'legs': [
          {
            'id': 'ord_stop',
            'symbol': 'AAPL',
            'side': 'sell',
            'qty': '10',
            'status': 'held',
            'type': 'stop',
            'stop_price': '140.00',
          },
          {
            'id': 'ord_target',
            'symbol': 'AAPL',
            'side': 'sell',
            'qty': '10',
            'status': 'held',
            'type': 'limit',
            'limit_price': '170.00',
          },
        ],
      });

      expect(order.legs, hasLength(2));
      expect(order.legs[0].stopPrice, 140.0);
      expect(order.legs[1].limitPrice, 170.0);
    });

    test('no legs field parses to an empty list, not null or a throw', () {
      final order = AlpacaOrder.fromJson({
        'id': 'ord_1',
        'symbol': 'AAPL',
        'side': 'buy',
        'qty': '10',
        'status': 'filled',
      });
      expect(order.legs, isEmpty);
    });
  });

  group('AlpacaOrder.isClosed / isCancellable', () {
    test('new/accepted/held are open and cancellable', () {
      for (final s in ['new', 'accepted', 'held', 'pending_new']) {
        final o = AlpacaOrder(
            id: 'x', symbol: 'AAPL', side: 'buy', qty: 1, status: s);
        expect(o.isClosed, isFalse, reason: s);
        expect(o.isCancellable, isTrue, reason: s);
      }
    });

    test('filled/canceled/expired/rejected are closed, never cancellable',
        () {
      for (final s in ['filled', 'canceled', 'expired', 'rejected']) {
        final o = AlpacaOrder(
            id: 'x', symbol: 'AAPL', side: 'buy', qty: 1, status: s);
        expect(o.isClosed, isTrue, reason: s);
        expect(o.isCancellable, isFalse, reason: s);
      }
    });

    test('pending_cancel is open but not offered a second cancel', () {
      final o = AlpacaOrder(
          id: 'x', symbol: 'AAPL', side: 'buy', qty: 1, status: 'pending_cancel');
      expect(o.isClosed, isFalse);
      expect(o.isCancellable, isFalse);
    });
  });

  group('AlpacaClient.cancelOrder — exact DELETE request + paper-only enforcement', () {
    test('builds DELETE /v2/orders/{id} against the stored paper host',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter()..statusCode = 204;
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await client.cancelOrder('ord_123');

      expect(adapter.calls, hasLength(1));
      expect(adapter.calls.single.method, 'DELETE');
      expect(adapter.calls.single.path, contains('/v2/orders/ord_123'));
    });

    test('refuses against a stored live host, independent of any UI check',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      expect(
        () => client.cancelOrder('ord_123'),
        throwsA(isA<AlpacaOrderRejected>()),
        reason: 'D-071/D-074: a cancel is a write, same as submitOrder — a '
            'live/production Alpaca account must never receive one from '
            'this client',
      );
      expect(adapter.calls, isEmpty,
          reason: 'the paper-host check must run before any HTTP call');
    });

    test('refuses when unlinked', () async {
      final client = AlpacaClient();
      expect(
          () => client.cancelOrder('ord_123'), throwsA(isA<AlpacaException>()));
    });

    test('a failed cancel (already filled) surfaces as AlpacaException',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final adapter = _RecordingAdapter()
        ..statusCode = 422
        ..nextResponse = {'message': 'order already filled'};
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await expectLater(
        client.cancelOrder('ord_123'),
        throwsA(isA<AlpacaException>()),
      );
    });
  });
}
