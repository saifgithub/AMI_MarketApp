/// DEF536 — the Floor search box lost its name lookup after the market changed
/// under text that was already resolved.
///
/// Device report (AMI-DL-26, build 132): with "british american" already in
/// the box, the chip went to MY and the box then sat on a plain CONVENE THE
/// ROOM with no "Which market?" chooser, indefinitely; retyping or flipping the
/// chip again recovered it. The lookup state was keyed on the text alone, so a
/// market change cleared the result but left "this text is already looked up"
/// true — and the only path that re-arms the lookup (a text change) was gated on
/// that flag. Any controller notification after the flip (a cursor move, a tap
/// into the field) cancelled the pending debounce and never restarted it.
library;

import 'dart:async';

import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ResolvedTicker _c(String ticker, String market, String short) => ResolvedTicker(
    ticker: ticker,
    market: market,
    shortName: short,
    longName: '$short Holdings');

final _both = {
  'british american|US': [_c('BTI', 'US', 'British American Tobacco')],
  'british american|MY': [_c('4162.KL', 'MY', 'BAT Malaysia')],
};

class _Resolver {
  _Resolver({this.gate});

  /// When set, a US lookup waits on this completer (an in-flight request).
  Completer<void>? gate;
  final calls = <String>[];

  Future<List<ResolvedTicker>> call(String q, AppMarket m) async {
    calls.add('${q.toLowerCase()}|${m.apiCode}');
    if (m == AppMarket.us && gate != null) await gate!.future;
    return _both['${q.toLowerCase()}|${m.apiCode}'] ?? const [];
  }
}

Future<ValueNotifier<AppMarket>> _pump(
    WidgetTester t, _Resolver r, AppMarket start) async {
  final market = ValueNotifier(start);
  addTearDown(market.dispose);
  await t.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: SingleChildScrollView(
        child: ValueListenableBuilder<AppMarket>(
          valueListenable: market,
          builder: (_, m, __) => FloorOmnibox(
            validate: (tk) async => TickerValidation(ticker: tk, exists: true),
            onConvene: (_) {},
            onAsk: (_) {},
            onPick: () {},
            market: m,
            onMarketChanged: (n) => market.value = n,
            resolve: r.call,
          ),
        ),
      ),
    ),
  ));
  return market;
}

Future<void> _settle(WidgetTester t) =>
    t.pump(const Duration(milliseconds: 900));

double _y(WidgetTester t, String ticker) =>
    t.getTopLeft(find.byKey(Key('omnibox-choice-$ticker'))).dy;

void main() {
  testWidgets(
      'a cursor move after the chip flip does not strand the lookup',
      (t) async {
    final r = _Resolver();
    final market = await _pump(t, r, AppMarket.us);
    await t.enterText(find.byType(TextField), 'british american');
    await _settle(t);
    expect(find.text('Which market?'), findsOneWidget);
    expect(_y(t, 'BTI'), lessThan(_y(t, '4162.KL')));

    market.value = AppMarket.my;
    await t.pump(const Duration(milliseconds: 100));
    t.widget<TextField>(find.byType(TextField)).controller!.selection =
        const TextSelection.collapsed(offset: 3);
    await _settle(t);

    expect(find.text('Which market?'), findsOneWidget,
        reason: 'the MY lookup must still run after a cursor move');
    expect(_y(t, '4162.KL'), lessThan(_y(t, 'BTI')),
        reason: 'the active market is listed first');
  });

  testWidgets('a lookup still in flight for the old market is not shown',
      (t) async {
    final gate = Completer<void>();
    final r = _Resolver(gate: gate);
    final market = await _pump(t, r, AppMarket.us);
    await t.enterText(find.byType(TextField), 'british american');
    await t.pump(const Duration(milliseconds: 450));

    market.value = AppMarket.my;
    await t.pump(const Duration(milliseconds: 50));
    gate.complete();
    await t.pump(const Duration(milliseconds: 10));
    expect(find.text('Which market?'), findsNothing,
        reason: 'the US-first answer belongs to the market that was left');

    await _settle(t);
    expect(find.text('Which market?'), findsOneWidget);
    expect(_y(t, '4162.KL'), lessThan(_y(t, 'BTI')));
  });

  testWidgets('chip set to MY before typing resolves on the first try',
      (t) async {
    final r = _Resolver();
    final market = await _pump(t, r, AppMarket.us);
    market.value = AppMarket.my;
    await t.pump();
    await t.enterText(find.byType(TextField), 'british american');
    await _settle(t);
    expect(find.text('Which market?'), findsOneWidget);
    expect(_y(t, '4162.KL'), lessThan(_y(t, 'BTI')));
  });
}
