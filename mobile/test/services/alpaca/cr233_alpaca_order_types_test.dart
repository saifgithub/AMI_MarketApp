/// CR233 — real Alpaca order types (market/limit/stop/stop_limit) and an
/// optional bracket, replacing CR227's market-only refusal.
///
/// Two layers, matching this file's own "predicts, never silently converts"
/// split of authority:
///  - [buildAlpacaOrderPayload] is asserted directly, golden-style, against
///    the exact `POST /v2/orders` body for each order type — the same
///    "extracted decision function" convention `isAlpacaPaperHost` already
///    uses in `alpaca_client_paper_only_test.dart`.
///  - [validateAlpacaOrder] is asserted directly for every refusal case: a
///    missing required price, an unknown order type, and a bracket whose
///    stop/target sits on the wrong side of the entry (DEF312/DEF377's
///    rule, applied to the Alpaca leg).
///  - `AlpacaClient.submitOrder` is exercised end-to-end against a fake
///    `HttpClientAdapter` that captures the exact request body Dio sent,
///    proving `buildAlpacaOrderPayload`'s output is what actually reaches
///    the wire and that a refused order never reaches the adapter at all.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/features/sim/order_pricing.dart' show SimOrderType, SimOrderTif;
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Captures every request Dio sends and returns a canned JSON response —
/// never touches the network. `calls` records path + decoded body so a test
/// can assert on the exact wire shape without any Dio-internal parsing.
class _RecordingAdapter implements HttpClientAdapter {
  final List<({String path, Map<String, dynamic> body})> calls = [];
  Map<String, dynamic> nextResponse = const {
    'id': 'ord_1',
    'symbol': 'AAPL',
    'side': 'buy',
    'qty': '1',
    'status': 'accepted',
  };

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add((
      path: options.path,
      body: (options.data as Map).cast<String, dynamic>(),
    ));
    final bytes = utf8.encode(jsonEncode(nextResponse));
    return ResponseBody.fromBytes(bytes, 200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('buildAlpacaOrderPayload — exact wire body per order type', () {
    test('market order', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.market,
      );
      expect(p, {
        'symbol': 'AAPL',
        'side': 'buy',
        'qty': '10.0',
        'type': 'market',
        'time_in_force': 'day',
      });
    });

    test('limit order carries limit_price and the requested TIF', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'NVDA',
        side: 'buy',
        qty: 5,
        orderType: SimOrderType.limit,
        limitPrice: 120.5,
        tif: SimOrderTif.gtd30,
      );
      expect(p, {
        'symbol': 'NVDA',
        'side': 'buy',
        'qty': '5.0',
        'type': 'limit',
        'time_in_force': 'gtc', // gtd30 → gtc, see alpacaTimeInForce
        'limit_price': '120.5',
      });
    });

    test('stop order carries stop_price, not limit_price', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'TSLA',
        side: 'sell',
        qty: 3,
        orderType: SimOrderType.stop,
        triggerPrice: 200.0,
        tif: SimOrderTif.day,
      );
      expect(p, {
        'symbol': 'TSLA',
        'side': 'sell',
        'qty': '3.0',
        'type': 'stop',
        'time_in_force': 'day',
        'stop_price': '200.0',
      });
    });

    test('stop_limit order carries both prices', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'MSFT',
        side: 'buy',
        qty: 2,
        orderType: SimOrderType.stopLimit,
        limitPrice: 410.0,
        triggerPrice: 405.0,
        tif: SimOrderTif.gtd90,
      );
      expect(p, {
        'symbol': 'MSFT',
        'side': 'buy',
        'qty': '2.0',
        'type': 'stop_limit',
        'time_in_force': 'gtc',
        'limit_price': '410.0',
        'stop_price': '405.0',
      });
    });

    test('a bracket adds order_class + take_profit/stop_loss legs', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.market,
        bracket: const AlpacaBracket(stopLoss: 90.0, takeProfit: 110.0),
      );
      expect(p['order_class'], 'bracket');
      expect(p['take_profit'], {'limit_price': '110.00'});
      expect(p['stop_loss'], {'stop_price': '90.00'});
    });

    test('a one-sided bracket sends only the leg that was set', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.market,
        bracket: const AlpacaBracket(stopLoss: 90.0),
      );
      expect(p['order_class'], 'bracket');
      expect(p.containsKey('take_profit'), isFalse);
      expect(p['stop_loss'], {'stop_price': '90.00'});
    });

    test('no bracket fields at all when neither stop nor target is set', () {
      final p = buildAlpacaOrderPayload(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.market,
        bracket: const AlpacaBracket(),
      );
      expect(p.containsKey('order_class'), isFalse);
      expect(p.containsKey('take_profit'), isFalse);
      expect(p.containsKey('stop_loss'), isFalse);
    });
  });

  group('alpacaTimeInForce', () {
    test('day maps to day', () {
      expect(alpacaTimeInForce(SimOrderTif.day), 'day');
    });
    test('gtd30 and gtd90 both map to gtc — no Alpaca N-day TIF exists', () {
      expect(alpacaTimeInForce(SimOrderTif.gtd30), 'gtc');
      expect(alpacaTimeInForce(SimOrderTif.gtd90), 'gtc');
    });
    test('unknown collapses to day, not the most permissive option', () {
      expect(alpacaTimeInForce(SimOrderTif.unknown), 'day');
    });
  });

  group('validateAlpacaOrder — refused loudly, never silently converted', () {
    test('an unknown order type is refused', () {
      expect(
        () => validateAlpacaOrder(
            side: 'buy', orderType: SimOrderType.unknown),
        throwsA(isA<AlpacaOrderRejected>()),
      );
    });

    test('a limit order with no limit price is refused', () {
      expect(
        () => validateAlpacaOrder(side: 'buy', orderType: SimOrderType.limit),
        throwsA(isA<AlpacaOrderRejected>()),
      );
    });

    test('a limit order with a zero/negative limit price is refused', () {
      expect(
        () => validateAlpacaOrder(
            side: 'buy', orderType: SimOrderType.limit, limitPrice: 0),
        throwsA(isA<AlpacaOrderRejected>()),
      );
      expect(
        () => validateAlpacaOrder(
            side: 'buy', orderType: SimOrderType.limit, limitPrice: -5),
        throwsA(isA<AlpacaOrderRejected>()),
      );
    });

    test('a stop order with no trigger price is refused', () {
      expect(
        () => validateAlpacaOrder(side: 'sell', orderType: SimOrderType.stop),
        throwsA(isA<AlpacaOrderRejected>()),
      );
    });

    test('a stop_limit order missing either price is refused', () {
      expect(
        () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.stopLimit,
            limitPrice: 100),
        throwsA(isA<AlpacaOrderRejected>()),
        reason: 'missing trigger_price',
      );
      expect(
        () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.stopLimit,
            triggerPrice: 95),
        throwsA(isA<AlpacaOrderRejected>()),
        reason: 'missing limit_price',
      );
    });

    test('a valid limit/stop/stop_limit order passes', () {
      expect(
        () => validateAlpacaOrder(
            side: 'buy', orderType: SimOrderType.limit, limitPrice: 100),
        returnsNormally,
      );
      expect(
        () => validateAlpacaOrder(
            side: 'sell', orderType: SimOrderType.stop, triggerPrice: 90),
        returnsNormally,
      );
      expect(
        () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.stopLimit,
            limitPrice: 100,
            triggerPrice: 95),
        returnsNormally,
      );
    });

    group('bracket wrong-side refusal — DEF312/DEF377 rule', () {
      test('a BUY limit with a stop-loss ABOVE entry is refused', () {
        expect(
          () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.limit,
            limitPrice: 100,
            bracket: const AlpacaBracket(stopLoss: 105), // wrong side
          ),
          throwsA(isA<AlpacaOrderRejected>()),
        );
      });

      test('a BUY limit with a take-profit BELOW entry is refused', () {
        expect(
          () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.limit,
            limitPrice: 100,
            bracket: const AlpacaBracket(takeProfit: 95), // wrong side
          ),
          throwsA(isA<AlpacaOrderRejected>()),
        );
      });

      test('a BUY limit with a correctly-sided bracket passes', () {
        expect(
          () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.limit,
            limitPrice: 100,
            bracket: const AlpacaBracket(stopLoss: 94, takeProfit: 113),
          ),
          returnsNormally,
        );
      });

      test('a SELL (short) stop_limit inverts: stop above, target below',
          () {
        expect(
          () => validateAlpacaOrder(
            side: 'sell',
            orderType: SimOrderType.stopLimit,
            limitPrice: 100,
            triggerPrice: 100,
            bracket: const AlpacaBracket(stopLoss: 106, takeProfit: 87),
          ),
          returnsNormally,
        );
        expect(
          () => validateAlpacaOrder(
            side: 'sell',
            orderType: SimOrderType.stopLimit,
            limitPrice: 100,
            triggerPrice: 100,
            bracket: const AlpacaBracket(stopLoss: 94), // wrong side for a short
          ),
          throwsA(isA<AlpacaOrderRejected>()),
        );
      });

      test('a bracket on a MARKET order (no named entry) is not judged',
          () {
        // No limit/trigger price to compare against — the same "nothing to
        // check yet" convention `stopIsWrongSide` uses for a null entry.
        expect(
          () => validateAlpacaOrder(
            side: 'buy',
            orderType: SimOrderType.market,
            bracket: const AlpacaBracket(stopLoss: 999, takeProfit: 1),
          ),
          returnsNormally,
        );
      });
    });
  });

  group('AlpacaClient.submitOrder — end-to-end wire body via a fake adapter',
      () {
    setUp(() async {
      FlutterSecureStoragePlatform.instance =
          TestFlutterSecureStoragePlatform(<String, String>{});
      SharedPreferences.setMockInitialValues({});
      AlpacaCredentialStore.resetCacheForTest();
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
    });

    test('a LIMIT order reaches the wire with the exact built payload',
        () async {
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      final order = await client.submitOrder(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.limit,
        limitPrice: 150.25,
        tif: SimOrderTif.day,
      );

      expect(adapter.calls, hasLength(1));
      expect(adapter.calls.single.path, contains('/v2/orders'));
      expect(adapter.calls.single.body, {
        'symbol': 'AAPL',
        'side': 'buy',
        'qty': '10.0',
        'type': 'limit',
        'time_in_force': 'day',
        'limit_price': '150.25',
      });
      expect(order.id, 'ord_1');
    });

    test('a bracket MARKET order reaches the wire with both legs', () async {
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await client.submitOrder(
        symbol: 'AAPL',
        side: 'buy',
        qty: 10,
        orderType: SimOrderType.market,
        bracket: const AlpacaBracket(stopLoss: 90, takeProfit: 110),
      );

      final body = adapter.calls.single.body;
      expect(body['order_class'], 'bracket');
      expect(body['take_profit'], {'limit_price': '110.00'});
      expect(body['stop_loss'], {'stop_price': '90.00'});
    });

    test('an invalid bracket never reaches the wire at all', () async {
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await expectLater(
        client.submitOrder(
          symbol: 'AAPL',
          side: 'buy',
          qty: 10,
          orderType: SimOrderType.limit,
          limitPrice: 100,
          bracket: const AlpacaBracket(stopLoss: 105), // wrong side
        ),
        throwsA(isA<AlpacaOrderRejected>()),
      );
      expect(adapter.calls, isEmpty,
          reason: 'a validation failure must refuse before any HTTP call, '
              'never place a mangled order');
    });

    test('a STOP order with no trigger price never reaches the wire',
        () async {
      final adapter = _RecordingAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      final client = AlpacaClient(dio: dio);

      await expectLater(
        client.submitOrder(
          symbol: 'AAPL',
          side: 'sell',
          qty: 1,
          orderType: SimOrderType.stop,
        ),
        throwsA(isA<AlpacaOrderRejected>()),
      );
      expect(adapter.calls, isEmpty);
    });
  });
}
