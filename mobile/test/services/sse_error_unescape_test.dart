/// DEF139 — SSE `error` payloads reach the user unescaped.
///
/// DEF127 made every SSE sender escape a COMPLETE value, so an exception
/// message can no longer end its own event early or forge a new one. That was
/// the right fix and it must not be undone on the backend. But the client only
/// ran `unescapeSseText` on `token` and `agent_token`, so an error containing a
/// newline arrived with a literal backslash-n in it and showed the user the two
/// characters instead of a line break.
///
/// Strictly better than the pre-DEF127 behaviour, which truncated the message
/// at its first line and silently discarded the actual cause — which is why
/// this is a cosmetic defect and not a regression. It is still wrong.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DEF139 — an error payload is decoded, not shown raw', () {
    test('a two-line error renders as two lines', () {
      // What the backend now puts on the wire after DEF127.
      final parsed = parseRoomSseEvent('error', r'Room failed\nTry again later');

      expect(parsed, isNotNull);
      expect(parsed!['kind'], 'error');
      final message = parsed['message'] as String;

      expect(message, 'Room failed\nTry again later');
      expect(message.split('\n'), hasLength(2));
      expect(message, isNot(contains(r'\n')),
          reason: 'the literal two characters are what the user was seeing');
    });

    test('a single-line error is unchanged', () {
      final parsed = parseRoomSseEvent('error', 'Room failed');
      expect(parsed!['message'], 'Room failed');
    });

    test('nothing is lost — the whole message survives, not just line one', () {
      // The pre-DEF127 failure mode: truncation at the first newline, with the
      // actual cause discarded. Guard against a "fix" that reintroduces it.
      final parsed = parseRoomSseEvent(
          'error', r'Upstream refused\ncause: vLLM connection reset');
      expect(parsed!['message'], contains('vLLM connection reset'));
    });
  });
}
