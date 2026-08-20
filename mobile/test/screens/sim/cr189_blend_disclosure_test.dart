/// CR189 acceptance 5 — a buy that raises the blended position stop says so
/// BEFORE submit, naming both numbers.
///
/// Buy 10 @ $100 with a stop at $95, then buy 10 more with a stop at $99, and
/// the original $95 becomes $97 — the risk floor on shares the user already
/// owns rose because of a later, separate decision. This project's rule is
/// that a control does not change quietly (CR040), so the ticket states the
/// move in the CR188 slice-1 notice slot: one sentence above the button,
/// never two.
///
/// The "from" level is the server's own blended stop off the portfolio
/// payload (`SimHolding.stop` — the same single derivation the sweep fires on
/// and the tile draws); the sheet never assembles lots itself (DEF098). The
/// absence half of the suite is the load-bearing half: the sentence says
/// "raises", so it must be absent for a first buy (acceptance 7 — the blend
/// of one is itself), an unprotected position, an untyped stop, and a stop
/// that does not raise the blend.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

SimHolding _holding(String ticker, double qty, {double? stop}) => SimHolding(
      ticker: ticker,
      quantity: qty,
      avgCost: 100,
      mark: 110,
      value: qty * 110,
      unrealisedPnl: qty * 10,
      openedAt: DateTime.utc(2026, 8, 1),
      stop: stop,
    );

SimPortfolio _portfolio({List<SimHolding> holdings = const []}) => SimPortfolio(
      userId: 'u',
      portfolioId: 'p',
      startingCapital: 10000,
      currentCash: 10000,
      holdings: holdings,
      totalValue: 10000,
      drawdownPct: 0,
    );

Future<void> _pump(WidgetTester t, {List<SimHolding> holdings = const []}) async {
  await t.binding.setSurfaceSize(const Size(390, 1400));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith(
        (ref) => _FixedSim(ref, SimState(portfolio: _portfolio(holdings: holdings))),
      ),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: SingleChildScrollView(child: TradeTicketSheet())),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

/// Types into the labelled fields, then settles. No quote arrives in a widget
/// test (there is no server), so the stop field holds exactly what is typed —
/// the DEF314 auto-anchor never runs.
Future<void> _fill(
  WidgetTester t, {
  required String ticker,
  String? qty,
  String? stop,
  bool sell = false,
}) async {
  await t.enterText(
    find.byWidgetPredicate((w) =>
        w is TextField &&
        w.decoration?.labelText != null &&
        w.decoration!.labelText!.toUpperCase().contains('TICKER')),
    ticker,
  );
  if (sell) {
    await t.tap(find.text('SELL'));
    await t.pump(const Duration(milliseconds: 120));
  }
  if (qty != null) {
    await t.enterText(
      find.byWidgetPredicate((w) =>
          w is TextField &&
          w.decoration?.labelText != null &&
          w.decoration!.labelText!.toUpperCase().contains('QUANTITY')),
      qty,
    );
  }
  if (stop != null) {
    await t.enterText(
      find.byWidgetPredicate((w) =>
          w is TextField &&
          w.decoration?.labelText != null &&
          w.decoration!.labelText!.toUpperCase().contains('STOP')),
      stop,
    );
  }
  for (var i = 0; i < 3; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('CR189 acceptance 5 — the buy ticket discloses a raised stop', () {
    testWidgets('buying into a bracketed holding names both numbers',
        (t) async {
      // 10 held with the server's blended stop at $95; 10 more with a stop
      // at $99 blends to (10×95 + 10×99) / 20 = $97.00 — the CR's own
      // worked example.
      await _pump(t, holdings: [_holding('AAPL', 10, stop: 95)]);
      await _fill(t, ticker: 'AAPL', qty: '10', stop: '99');

      expect(
          find.textContaining('raises your stop on all 20 AAPL'), findsOneWidget);
      expect(find.textContaining(r'from $95.00 to $97.00'), findsOneWidget);
    });

    testWidgets('a stop below the current blend is not a raise — absent',
        (t) async {
      // The boundary the sentence is named after. Inverting the raise
      // comparison in `_blendRaiseNotice` turns this test red.
      await _pump(t, holdings: [_holding('AAPL', 10, stop: 95)]);
      await _fill(t, ticker: 'AAPL', qty: '10', stop: '90');

      expect(find.textContaining('raises your stop'), findsNothing);
    });

    testWidgets('acceptance 7 — a first buy has no blend to move', (t) async {
      // Same typed stop as the positive case, but nothing held: the blend of
      // one lot is itself, so there is nothing to disclose.
      await _pump(t);
      await _fill(t, ticker: 'TSLA', qty: '10', stop: '99');

      expect(find.textContaining('raises your stop'), findsNothing);
    });

    testWidgets('an unprotected position has no stop to raise', (t) async {
      await _pump(t, holdings: [_holding('AAPL', 10)]);
      await _fill(t, ticker: 'AAPL', qty: '10', stop: '99');

      expect(find.textContaining('raises your stop'), findsNothing);
    });

    testWidgets('no stop typed, nothing disclosed', (t) async {
      await _pump(t, holdings: [_holding('AAPL', 10, stop: 95)]);
      await _fill(t, ticker: 'AAPL', qty: '10');

      expect(find.textContaining('raises your stop'), findsNothing);
    });

    testWidgets('the slot stays single-sentence: a SELL shows the sell notice',
        (t) async {
      // Flipping to SELL with a typed stop must never render the buy-side
      // disclosure beside the CR188 sell notice — one sentence above the
      // button, never two.
      await _pump(t, holdings: [_holding('AAPL', 10, stop: 95)]);
      await _fill(t, ticker: 'AAPL', qty: '5', stop: '99', sell: true);

      expect(find.textContaining('You hold 10 AAPL'), findsOneWidget);
      expect(find.textContaining('raises your stop'), findsNothing);
    });
  });
}
