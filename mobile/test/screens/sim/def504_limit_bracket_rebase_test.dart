/// DEF504 — a limit order kept the market-price STOP/TARGET bracket.
///
/// Reported from a real iPhone (store build 0.1.0+118): LIMIT BUY 1 SCHD at
/// $5.00 with the market at about $34. The hint said "Waits until SCHD falls to
/// $5.00" but the default bracket (32.43 / 38.98) was still measured from the
/// live quote, so the stop sat ABOVE the $5.00 entry, `stopIsWrongSide` refused
/// the ticket, and SUBMIT stayed disabled until the tester typed 4 / 6 by hand.
///
/// These drive the real sheet against a fake API that answers the ticker check
/// and the quote, because the bracket is anchored off a live quote fetch.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _QuoteApi extends ApiClient {
  _QuoteApi(this.price) : super(baseUrl: 'test://localhost');
  final double price;

  @override
  Future<TickerValidation> validateTicker(String ticker) async =>
      TickerValidation(ticker: ticker, exists: true);

  @override
  Future<({double price, double changePct, String source, String marketState})>
      simQuoteDetail(String ticker) async => (
            price: price,
            changePct: 0.0,
            source: 'test',
            marketState: 'REGULAR',
          );
}

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

SimPortfolio _portfolio() => SimPortfolio(
      userId: 'u',
      portfolioId: 'p',
      startingCapital: 10000,
      currentCash: 10000,
      holdings: const [],
      totalValue: 10000,
      drawdownPct: 0,
    );

Future<void> _pump(WidgetTester t, {double price = 34.0}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(_QuoteApi(price)),
      simNotifierProvider.overrideWith((ref) => _FixedSim(
          ref,
          SimState(portfolio: _portfolio(), restingOrdersSupported: true))),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const TradeTicketSheet(tickerPrefill: 'SCHD'),
    ),
  ));
  // Past the validator's 450ms debounce, then the quote lands.
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

Finder _field(String label) => find.byWidgetPredicate((w) =>
    w is TextField &&
    w.decoration?.labelText != null &&
    w.decoration!.labelText!.toUpperCase() == label);

String _text(WidgetTester t, String label) =>
    t.widget<TextField>(_field(label)).controller!.text;

Future<void> _type(WidgetTester t, String label, String value) async {
  await t.enterText(_field(label), value);
  await t.pump(const Duration(milliseconds: 120));
}

Future<void> _tap(WidgetTester t, String text) async {
  await t.tap(find.text(text).first);
  await t.pump(const Duration(milliseconds: 120));
}

bool _submitEnabled(WidgetTester t) =>
    t.widget<ElevatedButton>(find.byType(ElevatedButton).last).onPressed !=
    null;

bool _refusalShown() => find.textContaining('belongs').evaluate().isNotEmpty;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('MARKET anchors the bracket on the live quote', (t) async {
    await _pump(t);
    expect(_text(t, 'STOP'), '31.96');
    expect(_text(t, 'TARGET'), '38.42');
    expect(_submitEnabled(t), isTrue);
  });

  testWidgets(
      'LIMIT BUY far below the market re-bases the bracket and SUBMIT stays '
      'enabled (the reported device case)', (t) async {
    await _pump(t);
    await _tap(t, 'LIMIT');
    await _type(t, 'LIMIT PRICE', '5.00');

    expect(_text(t, 'STOP'), '4.70');
    expect(_text(t, 'TARGET'), '5.65');
    expect(_refusalShown(), isFalse);
    expect(_submitEnabled(t), isTrue);
  });

  testWidgets('the bracket follows the limit price as it changes', (t) async {
    await _pump(t);
    await _tap(t, 'LIMIT');
    await _type(t, 'LIMIT PRICE', '5.00');
    await _type(t, 'LIMIT PRICE', '20.00');
    expect(_text(t, 'STOP'), '18.80');
    expect(_text(t, 'TARGET'), '22.60');
  });

  testWidgets('back to MARKET re-bases on the quote again', (t) async {
    await _pump(t);
    await _tap(t, 'LIMIT');
    await _type(t, 'LIMIT PRICE', '5.00');
    await _tap(t, 'MARKET');
    expect(_text(t, 'STOP'), '31.96');
    expect(_text(t, 'TARGET'), '38.42');
  });

  testWidgets('a stop the user typed is NOT overwritten when the limit changes',
      (t) async {
    await _pump(t);
    await _tap(t, 'LIMIT');
    await _type(t, 'STOP', '4.10');
    await _type(t, 'LIMIT PRICE', '5.00');

    expect(_text(t, 'STOP'), '4.10', reason: 'user-typed, must survive');
    expect(_text(t, 'TARGET'), '5.65',
        reason: 'the untouched field still follows the entry');

    await _type(t, 'LIMIT PRICE', '8.00');
    expect(_text(t, 'STOP'), '4.10');
    expect(_text(t, 'TARGET'), '9.04');
  });

  testWidgets('a short LIMIT re-bases with the inverted bracket', (t) async {
    await _pump(t);
    await _tap(t, 'SELL');
    expect(_text(t, 'STOP'), '36.04');
    await _tap(t, 'LIMIT');
    await _type(t, 'LIMIT PRICE', '50.00');

    expect(_text(t, 'STOP'), '53.00');
    expect(_text(t, 'TARGET'), '43.50');
    expect(_submitEnabled(t), isTrue);
  });
}
