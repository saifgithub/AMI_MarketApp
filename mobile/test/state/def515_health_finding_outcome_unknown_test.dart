/// DEF515 - a Finding request whose answer never arrived is not a failed one.
///
/// AMI-DL-9b (2026-11-21): the phone gave up on the Finding POST at 30 s, the
/// server finished at 44 s and wrote the Finding, and the app showed "did not
/// respond" over a trial slot it had already spent. These pin the client half:
/// the wait is longer than the route's real latency, and an unknown outcome is
/// resolved by asking the server (free tiles read, then the free replay), not
/// assumed.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/portfolio_health_fixtures.dart';

DioException _timeout() => DioException(
      requestOptions: RequestOptions(path: '/finding'),
      type: DioExceptionType.receiveTimeout,
    );

DioException _refusal(int status) {
  final o = RequestOptions(path: '/finding');
  return DioException(
    requestOptions: o,
    type: DioExceptionType.badResponse,
    response: Response<dynamic>(requestOptions: o, statusCode: status),
  );
}

HealthFinding _finding() => HealthFinding.fromJson(findingJson());

class _Adapter implements HttpClientAdapter {
  RequestOptions? last;
  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    return ResponseBody.fromString(jsonEncode(findingJson()), 200, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  Future<void> noWait(Duration _) async {}

  test('the Finding POST waits longer than the 44 s it was measured to take',
      () async {
    final adapter = _Adapter();
    final api = ApiClient(baseUrl: 'http://x', dioAdapter: adapter);
    await api.generateHealthFinding('u1');
    final t = adapter.last!.receiveTimeout;
    expect(t, kHealthFindingReceiveTimeout);
    expect(t! > const Duration(seconds: 44), isTrue);
  });

  test('a first-try answer is returned with no polling', () async {
    var tilesCalls = 0;
    final f = await fetchHealthFinding(
      generate: () async => _finding(),
      tiles: () async {
        tilesCalls++;
        return healthFixture();
      },
      wait: noWait,
    );
    expect(f.journalEntryId, isNotEmpty);
    expect(tilesCalls, 0);
  });

  test('a receive timeout resolves to the stored Finding once the server has it',
      () async {
    var generateCalls = 0;
    var tilesCalls = 0;
    final f = await fetchHealthFinding(
      generate: () async {
        generateCalls++;
        if (generateCalls == 1) throw _timeout();
        return _finding();
      },
      tiles: () async {
        tilesCalls++;
        // The server is still writing for the first two looks.
        return healthFixture(
          todaysFindingId: tilesCalls >= 3 ? 'entry-1' : null,
        );
      },
      wait: noWait,
    );
    expect(f.journalEntryId, isNotEmpty);
    expect(tilesCalls, 3);
    expect(generateCalls, 2, reason: 'one original + one free replay, no more');
  });

  test('never re-POSTs while the server has nothing stored', () async {
    var generateCalls = 0;
    await expectLater(
      fetchHealthFinding(
        generate: () async {
          generateCalls++;
          throw _timeout();
        },
        tiles: () async => healthFixture(),
        pollEvery: const Duration(seconds: 5),
        window: const Duration(seconds: 20),
        wait: noWait,
      ),
      throwsA(isA<DioException>()
          .having((e) => e.type, 'type', DioExceptionType.receiveTimeout)),
    );
    expect(generateCalls, 1,
        reason: 'a second POST would start a second model call');
  });

  test('a failing tiles read does not end the wait early', () async {
    var tilesCalls = 0;
    var generateCalls = 0;
    final f = await fetchHealthFinding(
      generate: () async {
        generateCalls++;
        if (generateCalls == 1) throw _timeout();
        return _finding();
      },
      tiles: () async {
        tilesCalls++;
        if (tilesCalls == 1) throw _timeout();
        return healthFixture(todaysFindingId: 'entry-1');
      },
      wait: noWait,
    );
    expect(f.journalEntryId, isNotEmpty);
    expect(tilesCalls, 2);
  });

  test('a gateway cut (524) is an unknown outcome; a refusal is a verdict',
      () async {
    expect(isOutcomeUnknown(_refusal(524)), isTrue);
    expect(isOutcomeUnknown(_refusal(502)), isTrue);
    expect(isOutcomeUnknown(_timeout()), isTrue);
    for (final code in [402, 409, 429, 500]) {
      expect(isOutcomeUnknown(_refusal(code)), isFalse, reason: '$code');
    }
  });

  test('refusals are rethrown untouched and never polled', () async {
    var tilesCalls = 0;
    await expectLater(
      fetchHealthFinding(
        generate: () async => throw _refusal(429),
        tiles: () async {
          tilesCalls++;
          return healthFixture();
        },
        wait: noWait,
      ),
      throwsA(isA<DioException>()
          .having((e) => e.response?.statusCode, 'status', 429)),
    );
    expect(tilesCalls, 0);
  });
}
