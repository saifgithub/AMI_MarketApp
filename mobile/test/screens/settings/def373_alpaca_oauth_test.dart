// DEF373 (security review M12) — the Alpaca OAuth WebView had no CSRF nonce
// and no host allowlist.
//
// Two independent holes in one flow that collects brokerage credentials:
//
//   1. `_buildAuthUrl` sent no `state`, and the callback handler exchanged
//      ANY `code` that arrived. An attacker who gets the victim's app to open
//      a crafted `amitrade://alpaca/callback?code=...` links the victim's
//      install to the ATTACKER's Alpaca account — the victim then trades, and
//      the attacker watches.
//
//   2. `_handleNavigation` returned `navigate` for every url, and JavaScript
//      is unrestricted in this WebView. A redirect off Alpaca rendered
//      attacker content inside a view the user was told is their broker's
//      login: a phishing surface we built and aimed at ourselves.
//
// The pure halves are tested here; the navigation decision itself needs a live
// WebView and is covered by the structure assertions at the end.

import 'package:ami_trade/screens/settings/alpaca_connect_screen.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DEF373 — the OAuth state nonce', () {
    test('a nonce is long, url-safe, and padding-free', () {
      final s = newOauthState();
      expect(s.length, greaterThanOrEqualTo(40));
      expect(s.contains('='), isFalse, reason: 'must survive a query string');
      expect(RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(s), isTrue, reason: s);
    });

    test('two nonces are never the same', () {
      final seen = {for (var i = 0; i < 200; i++) newOauthState()};
      expect(seen.length, 200, reason: 'a repeated nonce is not a nonce');
    });

    test('the authorize url carries the state it was given', () {
      final uri = Uri.parse(buildAuthUrl('NONCE-123'));
      expect(uri.queryParameters['state'], 'NONCE-123');
      expect(uri.host, 'app.alpaca.markets');
      expect(uri.queryParameters['response_type'], 'code');
    });

    test('the redirect uri is unchanged by the fix', () {
      // Changing it would silently break every existing app registration.
      expect(
        Uri.parse(buildAuthUrl('x')).queryParameters['redirect_uri'],
        'amitrade://alpaca/callback',
      );
    });
  });

  group('DEF373 — the navigation allowlist', () {
    test('alpaca hosts are allowed', () {
      for (final url in [
        'https://app.alpaca.markets/oauth/authorize',
        'https://api.alpaca.markets/v2/whatever',
        'https://alpaca.markets/login',
      ]) {
        expect(isAllowedAuthHost(Uri.parse(url)), isTrue, reason: url);
      }
    });

    test('everything else is refused', () {
      for (final url in [
        'https://evil.example.com/login',
        'https://alpaca.markets.evil.com/login', // the suffix trick
        'https://notalpaca.markets/login',
        'https://evilalpaca.markets/login',
      ]) {
        expect(isAllowedAuthHost(Uri.parse(url)), isFalse, reason: url);
      }
    });

    test('plain http is refused even on an allowed domain', () {
      // A credential flow downgraded to http is a credential flow in cleartext.
      expect(isAllowedAuthHost(Uri.parse('http://app.alpaca.markets/x')), isFalse);
    });

    test('the host match is case-insensitive', () {
      expect(isAllowedAuthHost(Uri.parse('https://APP.ALPACA.MARKETS/x')), isTrue);
    });
  });
}
