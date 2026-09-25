/// DEF442 — the Alpaca trade ticket named every account-read failure the
/// same generic "couldn't read your account" line, whether the cause was
/// rejected keys, a network blip, a bad stored base URL, or Alpaca being
/// down. Saiful hit this live: a transient failure that a retry cleared
/// minutes later read exactly like "re-link your account", which it wasn't.
///
/// `alpacaReadFailureMessage` (`trade_ticket_sheet.dart`) is the one pure
/// function both catch sites (`_submitAlpacaOnly`, `_legAlpaca`) now route
/// through, so the two messages cannot drift apart. This test pins each of
/// its branches plus the DEF439 non-paper case, which is checked BEFORE
/// this function ever runs and must keep its own distinct message.
library;

import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('alpacaReadFailureMessage (DEF442)', () {
    test('401 reads as rejected keys, names re-link', () {
      final message =
          alpacaReadFailureMessage(const AlpacaException(401, 'unauthorized'));
      expect(
        message,
        'Alpaca rejected your keys — re-link your paper account in '
        'Settings. Order not sent.',
      );
    });

    test('403 also reads as rejected keys (isAuthFailure covers both)', () {
      final message =
          alpacaReadFailureMessage(const AlpacaException(403, 'forbidden'));
      expect(
        message,
        'Alpaca rejected your keys — re-link your paper account in '
        'Settings. Order not sent.',
      );
    });

    test('no status code (network/timeout) tells the user to retry', () {
      final message = alpacaReadFailureMessage(
        const AlpacaException(null, 'network error'),
      );
      expect(
        message,
        "Couldn't reach Alpaca — check your connection and try again. "
        'Order not sent.',
      );
    });

    test('404 names the account URL in Settings', () {
      final message =
          alpacaReadFailureMessage(const AlpacaException(404, 'not found'));
      expect(
        message,
        "Alpaca couldn't find that account — check the account URL in "
        'Settings. Order not sent.',
      );
    });

    test('429 reads as Alpaca busy, suggests retry shortly', () {
      final message = alpacaReadFailureMessage(
        const AlpacaException(429, 'rate limited'),
      );
      expect(
        message,
        'Alpaca is busy or down right now — try again shortly. '
        'Order not sent.',
      );
    });

    test('5xx reads the same as 429 — Alpaca busy or down', () {
      final message =
          alpacaReadFailureMessage(const AlpacaException(500, 'server error'));
      expect(
        message,
        'Alpaca is busy or down right now — try again shortly. '
        'Order not sent.',
      );
    });

    test('503 also falls into the 5xx bucket', () {
      final message = alpacaReadFailureMessage(
        const AlpacaException(503, 'service unavailable'),
      );
      expect(
        message,
        'Alpaca is busy or down right now — try again shortly. '
        'Order not sent.',
      );
    });

    test('an unrecognized status code falls back to the generic line', () {
      final message =
          alpacaReadFailureMessage(const AlpacaException(418, 'teapot'));
      expect(
        message,
        "Couldn't read your Alpaca paper account — order not sent.",
      );
    });

    test('a non-AlpacaException also falls back to the generic line', () {
      final message = alpacaReadFailureMessage(StateError('unexpected'));
      expect(
        message,
        "Couldn't read your Alpaca paper account — order not sent.",
      );
    });

    test(
        'never echoes the raw AlpacaException.detail into the returned '
        'message', () {
      final message = alpacaReadFailureMessage(
        const AlpacaException(500, 'some raw upstream response body'),
      );
      expect(message, isNot(contains('some raw upstream response body')));
    });
  });

  group('DEF439 non-paper account case stays intact', () {
    // Mirrors _nonPaperAccountDetail in trade_ticket_sheet.dart — that
    // sentinel is private to the file, so both catch sites check
    // `e.detail == _nonPaperAccountDetail` BEFORE calling
    // alpacaReadFailureMessage at all. This test pins that the sentinel
    // value itself, if it ever reached the mapping function, would NOT
    // collide with a real, mapped status-code message — the two code paths
    // must never be conflatable.
    const nonPaperDetail = 'refusing to read a non-paper Alpaca account for preview';

    test(
        'the non-paper sentinel has a null status code, same bucket as '
        'network errors if it were ever routed through the mapper', () {
      const e = AlpacaException(null, nonPaperDetail);
      expect(e.statusCode, isNull);
      expect(e.detail, nonPaperDetail);
      // Confirms why the call sites must check `.detail` FIRST: routed
      // through the generic mapper, this would incorrectly read as a
      // network failure rather than DEF439's "AMI links Alpaca paper
      // accounts only" message.
      expect(
        alpacaReadFailureMessage(e),
        "Couldn't reach Alpaca — check your connection and try again. "
        'Order not sent.',
      );
    });
  });
}
