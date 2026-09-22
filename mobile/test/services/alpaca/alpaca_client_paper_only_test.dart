/// CR227, D-071 — the Alpaca client refuses to place an order against
/// anything but a confirmed paper host, and refuses on its own account
/// rather than trusting whatever the caller (the trade ticket's UI) already
/// checked.
///
/// `isAlpacaPaperHost` is asserted directly as a pure function first — the
/// same "extracted decision function" convention `friendly_error_test.dart`
/// and `version_gate_interceptor_test.dart` use, so the boundary itself is
/// pinned independent of any widget or network plumbing. `submitOrder`'s
/// refusal is then asserted end-to-end against a stored non-paper `baseUrl`,
/// so a bypass of the UI's own check (or a future caller that never checks
/// at all) still cannot reach `/v2/orders` on a live host.
library;

import 'package:ami_trade/features/sim/order_pricing.dart' show SimOrderType;
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('isAlpacaPaperHost', () {
    test('the default paper host is recognized', () {
      expect(isAlpacaPaperHost(kDefaultAlpacaBaseUrl), isTrue);
    });

    test('a CR224 paper override with an account-prefixed subdomain is recognized', () {
      expect(isAlpacaPaperHost('https://paper-api-xyz.alpaca.markets'), isTrue);
    });

    test('the live/production host is refused', () {
      expect(isAlpacaPaperHost('https://api.alpaca.markets'), isFalse,
          reason: 'no "paper" segment in the hostname — this is the live '
              'trading host and must never be treated as paper');
    });

    test('a lookalike host outside alpaca.markets is refused', () {
      expect(
          isAlpacaPaperHost('https://paper-api.alpaca.markets.evil.example'),
          isFalse,
          reason: 'the host must END WITH .alpaca.markets, not merely '
              'contain it — a suffix check, not a substring check');
    });

    test('a malformed URL is refused, not thrown', () {
      expect(isAlpacaPaperHost('not a url'), isFalse);
    });

    test('an empty string is refused', () {
      expect(isAlpacaPaperHost(''), isFalse);
    });

    test('case is ignored', () {
      expect(isAlpacaPaperHost('https://PAPER-API.ALPACA.MARKETS'), isTrue);
    });
  });

  group('AlpacaClient.submitOrder — paper-only enforcement', () {
    setUp(() {
      FlutterSecureStoragePlatform.instance =
          TestFlutterSecureStoragePlatform(<String, String>{});
      SharedPreferences.setMockInitialValues({});
      AlpacaCredentialStore.resetCacheForTest();
    });

    test('refuses against a stored live host, independent of any UI check',
        () async {
      await AlpacaCredentialStore.save('key', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final client = AlpacaClient();
      expect(
        () => client.submitOrder(
            symbol: 'AAPL',
            side: 'buy',
            qty: 1,
            orderType: SimOrderType.market),
        throwsA(isA<AlpacaOrderRejected>()),
        reason: 'D-071: a live/production Alpaca account must never receive '
            'an order from this client, whatever the caller believes it '
            'already validated',
      );
    });

    test('refuses when unlinked', () async {
      final client = AlpacaClient();
      expect(
        () => client.submitOrder(
            symbol: 'AAPL',
            side: 'buy',
            qty: 1,
            orderType: SimOrderType.market),
        throwsA(isA<AlpacaException>()),
      );
    });

    test(
        'refuses a non-market order type before even checking the host or '
        'link state — auditor round-1 MAJOR-1', () async {
      // Unlinked AND a live host would both also refuse; this proves the
      // order-type check fires independently, matching how submitOrder()
      // now checks orderType before reading AlpacaCredentialStore at all.
      final client = AlpacaClient();
      for (final t in [
        SimOrderType.limit,
        SimOrderType.stop,
        SimOrderType.stopLimit,
      ]) {
        expect(
          () => client.submitOrder(
              symbol: 'AAPL', side: 'buy', qty: 1, orderType: t),
          throwsA(isA<AlpacaOrderRejected>()),
          reason: '$t must never reach Alpaca as a silently-converted '
              'market order (CR227 Non-goals)',
        );
      }
    });
  });
}
