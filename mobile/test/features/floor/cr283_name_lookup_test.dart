/// CR283 - the pure half of Bursa name routing: what counts as a name, how two
/// markets' answers combine, and what the CTA says. Bursa off never reaches any
/// of it, which `omnibox_router_test.dart` already pins for `routeOmnibox`.
library;

import 'package:ami_trade/features/floor/omnibox_router.dart';
import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:flutter_test/flutter_test.dart';

ResolvedTicker _c(String ticker, String market, String short) => ResolvedTicker(
    ticker: ticker, market: market, shortName: short, longName: '$short Ltd');

final _cimbMy = _c('1023.KL', 'MY', 'CIMB');
final _cimbUs = _c('CIMB', 'US', 'CIMB Test Corp');

TickerResolver _fake(Map<AppMarket, List<ResolvedTicker>?> answers,
    [List<(String, AppMarket)>? log]) {
  return (q, m) async {
    log?.add((q, m));
    final a = answers[m];
    if (a == null) throw StateError('down');
    return a;
  };
}

void main() {
  group('isNameQuery', () {
    test('short letter phrases are names', () {
      for (final s in ['CIMB', 'maybank', 'public bank', r'$aapl', "Nestle M"]) {
        expect(isNameQuery(s), isTrue, reason: s);
      }
    });

    test('codes, sentences and punctuation are not', () {
      for (final s in [
        '',
        '1023',
        '1023.KL',
        '5099A',
        'what is a P/E ratio?',
        'tell me about maybank please',
        'a b c d',
        'x' * 31,
      ]) {
        expect(isNameQuery(s), isFalse, reason: s);
      }
    });
  });

  group('lookupName', () {
    test('one market matching is single', () async {
      final r = await lookupName('cimb',
          active: AppMarket.my,
          resolve: _fake({AppMarket.my: [_cimbMy], AppMarket.us: []}));
      expect(r.kind, NameLookupKind.single);
      expect(r.candidates.single.ticker, '1023.KL');
    });

    test('both matching is a choice, active market first', () async {
      final answers = {
        AppMarket.my: [_cimbMy],
        AppMarket.us: [_cimbUs],
      };
      final my = await lookupName('cimb',
          active: AppMarket.my, resolve: _fake(answers));
      expect(my.kind, NameLookupKind.choice);
      expect(my.candidates.map((c) => c.ticker), ['1023.KL', 'CIMB']);
      final us = await lookupName('cimb',
          active: AppMarket.us, resolve: _fake(answers));
      expect(us.candidates.map((c) => c.ticker), ['CIMB', '1023.KL']);
    });

    test('neither matching is none', () async {
      final r = await lookupName('zzzz',
          active: AppMarket.us,
          resolve: _fake({AppMarket.my: [], AppMarket.us: []}));
      expect(r.kind, NameLookupKind.none);
    });

    test('a failed leg is down even when the other leg matched', () async {
      final r = await lookupName('cimb',
          active: AppMarket.us,
          resolve: _fake({AppMarket.us: [_cimbUs], AppMarket.my: null}));
      expect(r.kind, NameLookupKind.down);
    });

    test('asks both markets with the trimmed query', () async {
      final log = <(String, AppMarket)>[];
      await lookupName('  cimb ',
          active: AppMarket.my,
          resolve: _fake({AppMarket.my: [], AppMarket.us: []}, log));
      expect(log.map((e) => e.$1).toSet(), {'cimb'});
      expect(log.map((e) => e.$2).toSet(), {AppMarket.my, AppMarket.us});
    });
  });

  test('resolvedLabel names a Bursa company and code, a US hit its ticker', () {
    expect(resolvedLabel(_cimbMy), 'CIMB · 1023');
    expect(resolvedLabel(_c('5099A.KL', 'MY', 'Foo')), 'FOO · 5099A');
    expect(resolvedLabel(_cimbUs), 'CIMB');
  });

  test('routeOmnibox is unchanged by CR283: a word is still ticker-shaped', () {
    expect(routeOmnibox('CIMB', bursaEnabled: true).ticker, 'CIMB');
    expect(routeOmnibox('1023', bursaEnabled: true).ticker, '1023.KL');
    expect(routeOmnibox('1023', bursaEnabled: false).route,
        OmniboxRoute.concierge);
  });
}
