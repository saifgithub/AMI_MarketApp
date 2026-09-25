/// DEF430 (Saiful, 2026-09-25: "paper only") — a live/production Alpaca
/// account's summary must never leave the device. The agents (Room convene,
/// 1-on-1) and the DEF419 per-account mandate preview must only ever see a
/// PAPER account's cash/positions; a live account still renders on the
/// Portfolio screen, it just never gets uploaded.
///
/// Same fake-`HttpClientAdapter` convention `cr234_alpaca_orders_test.dart`
/// established: capture whether a network call happened at all, never touch
/// the real network. The point under test is that a live host short-circuits
/// BEFORE any Alpaca call is made — not just that the upload is later
/// dropped — so "no calls recorded" is the actual assertion, not merely
/// "returned null".
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingAdapter implements HttpClientAdapter {
  final List<String> paths = [];
  dynamic accountResponse = const {
    'cash': '100.0',
    'portfolio_value': '100.0',
    'equity': '100.0',
    'buying_power': '100.0',
  };
  dynamic positionsResponse = const <dynamic>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    paths.add(options.path);
    final body = options.path.contains('/v2/positions')
        ? positionsResponse
        : accountResponse;
    final bytes = utf8.encode(jsonEncode(body));
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

  late _RecordingAdapter adapter;
  late AlpacaClient client;

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
    adapter = _RecordingAdapter();
    final dio = Dio()..httpClientAdapter = adapter;
    client = AlpacaClient(dio: dio);
  });

  group('AlpacaSnapshotCache.current — DEF430 paper-only', () {
    test('unlinked: no snapshot, no Alpaca call', () async {
      final cache = AlpacaSnapshotCache(client);
      final snap = await cache.current();
      expect(snap, isNull);
      expect(adapter.paths, isEmpty);
    });

    test('live host: no snapshot sent, and no Alpaca call is even made',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final cache = AlpacaSnapshotCache(client);

      final snap = await cache.current();

      expect(snap, isNull,
          reason: 'DEF430: a live account\'s summary must never leave the '
              'device');
      expect(adapter.paths, isEmpty,
          reason: 'the paper-host check must short-circuit before any '
              'network call, not merely drop the result afterwards');
    });

    test('paper host (default): snapshot is fetched and returned', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final cache = AlpacaSnapshotCache(client);

      final snap = await cache.current();

      expect(snap, isNotNull);
      expect(adapter.paths.any((p) => p.contains('/v2/account')), isTrue);
      expect(adapter.paths.any((p) => p.contains('/v2/positions')), isTrue);
    });

    test('a CR224 account-prefixed paper subdomain still sends', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://paper-api-xyz.alpaca.markets');
      final cache = AlpacaSnapshotCache(client);

      final snap = await cache.current();

      expect(snap, isNotNull);
      expect(adapter.paths, isNotEmpty);
    });

    test('a lookalike host outside alpaca.markets is refused like any other '
        'non-paper host', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://paper-api.alpaca.markets.evil.example');
      final cache = AlpacaSnapshotCache(client);

      final snap = await cache.current();

      expect(snap, isNull);
      expect(adapter.paths, isEmpty);
    });

    test('does not throw — a live host degrades to null like any other '
        'unavailable-overlay case', () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final cache = AlpacaSnapshotCache(client);

      await expectLater(cache.current(), completion(isNull));
    });
  });
}
