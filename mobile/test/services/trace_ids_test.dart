// WP-38 (CR267) / CR239 - the client half of the error trace id.
//
// The backend echoes a trace id on every error response. These tests pin that
// ApiClient CAPTURES it (header, falling back to the body), that a request
// with no response is recorded as a gap rather than leaving a stale id to be
// shown for it, that the short on-screen reference round-trips back to the
// full id, and that the bug-report call attaches the recent ids.

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/api/trace_ids.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

const _id1 = 'a1b2c3d4-0000-4000-8000-000000000001';
const _id2 = 'e5f6a7b8-0000-4000-8000-000000000002';

class _Adapter implements HttpClientAdapter {
  _Adapter(this.respond);
  final ResponseBody Function(RequestOptions) respond;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    return respond(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _json(int status, Object body, {Map<String, String>? headers}) =>
    ResponseBody.fromString(jsonEncode(body), status, headers: {
      Headers.contentTypeHeader: ['application/json'],
      if (headers != null) for (final e in headers.entries) e.key: [e.value],
    });

void main() {
  final store = TraceIdStore.instance;
  setUp(store.clear);

  group('ApiClient captures the trace id off error responses', () {
    test('from the X-Request-Id header, on a 4xx', () async {
      final api = ApiClient(
          baseUrl: 'http://x',
          dioAdapter: _Adapter((_) => _json(409, {'detail': 'nope'},
              headers: {'x-request-id': _id1})));
      DioException? caught;
      try {
        await api.regenerateHandle();
      } on DioException catch (e) {
        caught = e;
      }
      expect(caught, isNotNull);
      expect(store.recentId(), _id1);
      expect(store.recentIds(), [_id1]);
      expect(caught!.requestOptions.extra[kTraceIdExtraKey], _id1);
      // ...and friendlyError turns the same id into the short footnote.
      expect(friendlyError(caught, action: 'rename'), endsWith('Ref: a1b2c3d4.'));
    });

    test('from the body request_id when the header is absent (5xx)', () async {
      final api = ApiClient(
          baseUrl: 'http://x',
          dioAdapter: _Adapter((_) => _json(
              500, {'detail': 'internal server error', 'request_id': _id2})));
      await expectLater(api.regenerateHandle(), throwsA(isA<DioException>()));
      expect(store.recentId(), _id2);
    });

    test('a failure that never reached the server is a gap, not a stale id',
        () async {
      store.record(_id1, path: '/old', status: 500);
      final api = ApiClient(
          baseUrl: 'http://x',
          dioAdapter: _Adapter((o) => throw DioException(
              requestOptions: o, type: DioExceptionType.connectionError)));
      await expectLater(api.regenerateHandle(), throwsA(isA<DioException>()));
      expect(store.recentId(), isNull,
          reason: 'the on-screen error was not _id1 - never show it as such');
      expect(store.recentIds(), [_id1],
          reason: 'but a bug report still carries the earlier real failure');
    });

    test('a successful response records nothing', () async {
      final api = ApiClient(
          baseUrl: 'http://x',
          dioAdapter: _Adapter((_) => _json(200, {'handle': 'h'},
              headers: {'x-request-id': _id1})));
      await api.regenerateHandle();
      expect(store.recentIds(), isEmpty);
    });
  });

  group('TraceIdStore', () {
    test('recentId expires; recentIds does not', () {
      var now = DateTime(2026, 11, 18, 12);
      final s = TraceIdStore(now: () => now);
      s.record(_id1);
      expect(s.recentId(), _id1);
      now = now.add(kTraceRefFreshness + const Duration(seconds: 1));
      expect(s.recentId(), isNull);
      expect(s.recentIds(), [_id1]);
    });

    test('recentIds is newest-first, distinct, and capped', () {
      final s = TraceIdStore();
      for (var i = 0; i < 8; i++) {
        s.record('id-$i');
      }
      s.record('id-7');
      expect(s.recentIds(), ['id-7', 'id-6', 'id-5', 'id-4', 'id-3']);
    });

    test('resolve maps the short prefix back to the full id', () {
      final s = TraceIdStore()..record(_id1);
      expect(s.resolve('a1b2c3d4'), _id1);
      expect(s.resolve('ffffffff'), isNull);
    });
  });

  group('splitTraceRef', () {
    test('splits a trailing Ref footnote off the headline', () {
      final p = splitTraceRef("Couldn't load — try again. Ref: a1b2c3d4.");
      expect(p.message, "Couldn't load — try again.");
      expect(p.ref, 'a1b2c3d4');
    });

    test('leaves a message without one, and the Room run ref, alone', () {
      expect(splitTraceRef('Plain.').ref, isNull);
      const room = 'Failed. Run ref: a1b2c3d4.';
      expect(splitTraceRef(room).ref, isNull);
      expect(splitTraceRef(room).message, room);
    });
  });

  test('submitBugReport attaches the recent trace ids to the form', () async {
    final adapter = _Adapter((_) => _json(201, {'id': 'r1'}));
    final api = ApiClient(baseUrl: 'http://x', dioAdapter: adapter);
    await api.submitBugReport(
      category: 'crash',
      title: 't',
      appVersion: '1.0+1',
      platform: 'ios',
      traceIds: [_id1, _id2],
    );
    final form = adapter.last!.data as FormData;
    final fields = {for (final f in form.fields) f.key: f.value};
    expect(fields['trace_ids'], '$_id1,$_id2');

    await api.submitBugReport(
        category: 'crash', title: 't', appVersion: '1.0+1', platform: 'ios');
    final bare = adapter.last!.data as FormData;
    expect(bare.fields.any((f) => f.key == 'trace_ids'), isFalse,
        reason: 'no ids -> no field, so an old server and a new one agree');
  });
}
