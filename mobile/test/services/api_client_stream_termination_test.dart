/// DEF114 (D4/D6) — the CR090-MOBILE auditor mutation "make `done` no
/// longer terminate the generator" (M2) stayed green because none of the
/// three SSE stream methods could be driven with a controlled response: each
/// built its own `http.Client()` inline. `ApiClient` now takes an injectable
/// `http.Client` (see `api_client.dart`'s constructor); this file drives all
/// three surfaces through a fake client whose response deliberately contains
/// a bogus event *after* `done`, and asserts it is never reached.
library;

import 'dart:async';
import 'dart:convert';

import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

/// Replays [sseBody] verbatim as the streamed response, split across
/// multiple chunks so the parser has to buffer across `send()` boundaries —
/// exercising the same multi-chunk path production traffic takes.
class _ScriptedSseClient extends http.BaseClient {
  _ScriptedSseClient(this.sseBody);
  final String sseBody;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final bytes = utf8.encode(sseBody);
    final mid = bytes.length ~/ 2;
    final chunks = Stream<List<int>>.fromIterable([
      bytes.sublist(0, mid),
      bytes.sublist(mid),
    ]);
    return http.StreamedResponse(chunks, 200);
  }

  @override
  void close() {}
}

String _sseFrame(String event, String data) => 'event: $event\ndata: $data\n\n';

void main() {
  group('DEF114 (D4/D6) — done terminates the SSE generator', () {
    test('streamRoom stops at done and never yields the frame after it', () async {
      final body = _sseFrame('phase', '{"label": "convening"}') +
          _sseFrame('agent_token', '{"agent_id": "pm", "text": "hi"}') +
          _sseFrame('done', '{"run_id": "r1"}') +
          _sseFrame('agent_token', '{"agent_id": "pm", "text": "should never arrive"}');

      final client = ApiClient(httpClient: _ScriptedSseClient(body));
      client.setToken('test-token');

      final events = await client
          .streamRoom(userId: 'u1', ticker: 'AAPL')
          .toList();

      expect(events.map((e) => e['kind']), ['phase', 'agent_token', 'done']);
    });

    test('streamBriefMessage stops at done and never yields the token after it', () async {
      final body = _sseFrame('token', 'hello') +
          _sseFrame('done', '{}') +
          _sseFrame('token', 'should never arrive');

      final client = ApiClient(httpClient: _ScriptedSseClient(body));
      client.setToken('test-token');

      final tokens = await client
          .streamBriefMessage(
            sessionId: 's1',
            userMessage: 'hi',
            history: const <ChatMessage>[],
          )
          .toList();

      expect(tokens, ['hello']);
    });

    test('streamOneOnOneMessage stops at done and never yields the token after it', () async {
      final body = _sseFrame('token', 'hello') +
          _sseFrame('done', '{}') +
          _sseFrame('token', 'should never arrive');

      final client = ApiClient(httpClient: _ScriptedSseClient(body));
      client.setToken('test-token');

      final tokens = await client
          .streamOneOnOneMessage(
            sessionId: 's1',
            userMessage: 'hi',
            history: const <ChatMessage>[],
          )
          .toList();

      expect(tokens, ['hello']);
    });
  });
}
