/// CR283 - the Floor search box with a market: the chip, name resolution, the
/// chooser, the lookup-down message, and that a Bursa-off box is untouched.
///
/// The resolver is a fake that records every call, so "Bursa off makes no
/// lookup" and "a code is never resolved" are assertions, not hopes.
library;

import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ResolvedTicker _c(String ticker, String market, String short, [String? long]) =>
    ResolvedTicker(
        ticker: ticker,
        market: market,
        shortName: short,
        longName: long ?? '$short Holdings');

class _Resolver {
  _Resolver(this.table, {this.down = false});

  /// `'<q>|<MARKET>'` -> hits.
  final Map<String, List<ResolvedTicker>> table;
  bool down;
  final calls = <String>[];

  Future<List<ResolvedTicker>> call(String q, AppMarket m) async {
    calls.add('${q.toLowerCase()}|${m.apiCode}');
    if (down) throw Exception('503');
    return table['${q.toLowerCase()}|${m.apiCode}'] ?? const [];
  }
}

class _Harness {
  _Harness(this.resolver, this.convened, this.asked, this.markets);
  final _Resolver resolver;
  final List<String> convened;
  final List<String> asked;
  final List<AppMarket> markets;
}

Future<_Harness> _pump(
  WidgetTester t, {
  required AppMarket? market,
  _Resolver? resolver,
}) async {
  final r = resolver ?? _Resolver({});
  final convened = <String>[];
  final asked = <String>[];
  final markets = <AppMarket>[];
  await t.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: SingleChildScrollView(
        child: FloorOmnibox(
          validate: (tk) async => TickerValidation(ticker: tk, exists: true),
          onConvene: convened.add,
          onAsk: asked.add,
          onPick: () {},
          market: market,
          onMarketChanged: markets.add,
          resolve: market == null ? null : r.call,
        ),
      ),
    ),
  ));
  return _Harness(r, convened, asked, markets);
}

Future<void> _type(WidgetTester t, String text) async {
  await t.enterText(find.byType(TextField), text);
  await t.pump(const Duration(milliseconds: 900));
}

String _cta(WidgetTester t) => t
    .widget<HexButton>(find.byType(HexButton))
    .label
    .toUpperCase();

final _cimb = {
  'cimb|MY': [_c('1023.KL', 'MY', 'CIMB', 'CIMB Group Holdings Berhad')],
  'maybank|MY': [_c('1155.KL', 'MY', 'Maybank', 'Malayan Banking Berhad')],
  'aapl|US': [_c('AAPL', 'US', 'Apple Inc.')],
};

void main() {
  group('Bursa on, MY active', () {
    testWidgets('CIMB convenes 1023.KL and the CTA names ticker and code',
        (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await _type(t, 'CIMB');
      expect(_cta(t), 'CONVENE THE ROOM · CIMB · 1023');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['1023.KL']);
    });

    testWidgets('maybank convenes 1155.KL', (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await _type(t, 'maybank');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['1155.KL']);
    });

    testWidgets('tapping CONVENE before the debounce settles still resolves',
        (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await t.enterText(find.byType(TextField), 'maybank');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['1155.KL']);
    });

    testWidgets('lookup down says so and convenes nothing', (t) async {
      final h = await _pump(t,
          market: AppMarket.my, resolver: _Resolver(_cimb, down: true));
      await _type(t, 'CIMB');
      expect(find.byKey(const Key('omnibox-lookup-down')), findsOneWidget);
      expect(find.text("Can't look up names right now — use the 4-digit code."),
          findsOneWidget);
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, isEmpty);
      expect(h.asked, isEmpty);
    });

    testWidgets('a 4-digit code goes to Bursa with no lookup', (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await _type(t, '1023');
      expect(_cta(t), 'CONVENE THE ROOM · 1023.KL');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['1023.KL']);
      expect(h.resolver.calls, isEmpty);
    });

    testWidgets('a sentence goes to AMI, nothing resolved', (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await _type(t, 'what is a P/E ratio?');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.asked, ['what is a P/E ratio?']);
      expect(h.resolver.calls, isEmpty);
    });

    testWidgets('a short phrase nothing matches falls through to AMI',
        (t) async {
      final h = await _pump(t, market: AppMarket.my, resolver: _Resolver(_cimb));
      await _type(t, 'hello there');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.asked, ['hello there']);
    });
  });

  group('Bursa on, US active', () {
    testWidgets('AAPL convenes AAPL', (t) async {
      final h = await _pump(t, market: AppMarket.us, resolver: _Resolver(_cimb));
      await _type(t, 'AAPL');
      expect(_cta(t), 'CONVENE THE ROOM · AAPL');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['AAPL']);
    });

    testWidgets('a word listed in both markets shows the chooser, US first',
        (t) async {
      final both = {
        ..._cimb,
        'cimb|US': [_c('CIMB', 'US', 'CIMB Test Corp')],
      };
      final h = await _pump(t, market: AppMarket.us, resolver: _Resolver(both));
      await _type(t, 'CIMB');
      expect(find.text('WHICH MARKET?'), findsNothing);
      expect(find.text('Which market?'), findsOneWidget);
      final us = t.getTopLeft(find.byKey(const Key('omnibox-choice-CIMB')));
      final my = t.getTopLeft(find.byKey(const Key('omnibox-choice-1023.KL')));
      expect(us.dy, lessThan(my.dy), reason: 'active market first');

      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, isEmpty, reason: 'never a silent pick');

      await t.tap(find.byKey(const Key('omnibox-choice-1023.KL')));
      await t.pumpAndSettle();
      expect(h.convened, ['1023.KL']);
    });

    testWidgets('with MY active the chooser lists MY first', (t) async {
      final both = {
        ..._cimb,
        'cimb|US': [_c('CIMB', 'US', 'CIMB Test Corp')],
      };
      await _pump(t, market: AppMarket.my, resolver: _Resolver(both));
      await _type(t, 'CIMB');
      final us = t.getTopLeft(find.byKey(const Key('omnibox-choice-CIMB')));
      final my = t.getTopLeft(find.byKey(const Key('omnibox-choice-1023.KL')));
      expect(my.dy, lessThan(us.dy));
    });

    testWidgets('lookup down falls back to today\'s ticker rule', (t) async {
      final h = await _pump(t,
          market: AppMarket.us, resolver: _Resolver(_cimb, down: true));
      await _type(t, 'AAPL');
      expect(find.byKey(const Key('omnibox-lookup-down')), findsNothing);
      expect(_cta(t), 'CONVENE THE ROOM · AAPL');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['AAPL']);
    });

    testWidgets('1023 goes to Bursa in US mode too, no lookup', (t) async {
      final h = await _pump(t, market: AppMarket.us, resolver: _Resolver(_cimb));
      await _type(t, '1023');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['1023.KL']);
      expect(h.resolver.calls, isEmpty);
    });
  });

  group('the chip', () {
    testWidgets('shows the active market and asks for the other on tap',
        (t) async {
      final h = await _pump(t, market: AppMarket.us);
      expect(find.byKey(const Key('floor-market-chip')), findsOneWidget);
      expect(find.text('US'), findsOneWidget);
      await t.tap(find.byKey(const Key('floor-market-chip')));
      expect(h.markets, [AppMarket.my]);
    });

    testWidgets('MY chip asks for US', (t) async {
      final h = await _pump(t, market: AppMarket.my);
      expect(find.text('MY'), findsOneWidget);
      await t.tap(find.byKey(const Key('floor-market-chip')));
      expect(h.markets, [AppMarket.us]);
    });

    testWidgets('switching market re-resolves the same word', (t) async {
      final resolver = _Resolver({
        'cimb|MY': [_c('1023.KL', 'MY', 'CIMB')],
        'cimb|US': [_c('CIMB', 'US', 'CIMB Test Corp')],
      });
      Widget build(AppMarket m) => MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(
              body: SingleChildScrollView(
                child: FloorOmnibox(
                  validate: (tk) async =>
                      TickerValidation(ticker: tk, exists: true),
                  onConvene: (_) {},
                  onAsk: (_) {},
                  onPick: () {},
                  market: m,
                  resolve: resolver.call,
                ),
              ),
            ),
          );
      await t.pumpWidget(build(AppMarket.us));
      await _type(t, 'CIMB');
      final before = resolver.calls.length;
      await t.pumpWidget(build(AppMarket.my));
      await t.pump(const Duration(milliseconds: 900));
      expect(resolver.calls.length, greaterThan(before));
    });
  });

  group('Bursa off (no market passed)', () {
    testWidgets('no chip, no lookup, today\'s routing', (t) async {
      final h = await _pump(t, market: null);
      expect(find.byKey(const Key('floor-market-chip')), findsNothing);

      await _type(t, 'CIMB');
      expect(_cta(t), 'CONVENE THE ROOM · CIMB');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.convened, ['CIMB']);
      expect(h.resolver.calls, isEmpty);
    });

    testWidgets('a code is still a question for AMI', (t) async {
      final h = await _pump(t, market: null);
      await _type(t, '1023');
      expect(_cta(t), 'ASK AMI');
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();
      expect(h.asked, ['1023']);
      expect(h.resolver.calls, isEmpty);
    });
  });
}
