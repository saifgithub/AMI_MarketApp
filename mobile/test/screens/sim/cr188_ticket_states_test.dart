/// CR188 slice 1 — the ticket says what it is about to do, before it does it.
///
/// A SELL did one of three different things — reduce a holding, get refused, or
/// **open a short with uncapped loss** — decided entirely by a number that
/// appeared nowhere on the sheet. The quantity field defaulted to `1`, nothing
/// named the holding, and the only mention of the word "short" arrived in the
/// snackbar after the position existed.
///
/// The button's LABEL is the assertion that matters most here. CR171 already
/// had the words and fired them after the fill — right for the borrow-cost
/// advisory, wrong for "this is a different kind of position than you think".
/// A word on the control being pressed is structural; a sentence above it is an
/// instruction, and this project's own rule is that instructions are not
/// controls. Colour alone is not the fix and a test that accepted colour alone
/// would have passed against a first attempt that changed only the colour.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
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

SimHolding _holding(String ticker, double qty) => SimHolding(
      ticker: ticker,
      quantity: qty,
      avgCost: 180,
      mark: 190,
      value: qty * 190,
      unrealisedPnl: qty * 10,
      openedAt: DateTime.utc(2026, 8, 1),
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

/// Types into the ticker/quantity fields by their labels, then settles.
Future<void> _fill(
  WidgetTester t, {
  required String ticker,
  String? qty,
  String? stop,
  String? target,
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
  for (final (label, value) in [('STOP', stop), ('TARGET', target)]) {
    if (value == null) continue;
    await t.enterText(
      find.byWidgetPredicate((w) =>
          w is TextField &&
          w.decoration?.labelText != null &&
          w.decoration!.labelText!.toUpperCase().contains(label)),
      value,
    );
  }
  for (var i = 0; i < 3; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

/// Every string rendered inside the submit button, joined.
///
/// Read off the widget tree rather than off the button's `child`, because
/// `ElevatedButton.icon` wraps its label in a private type — a cast against
/// that is a test that breaks on a Flutter upgrade rather than on a defect.
String _ctaLabel(WidgetTester t) => t
    .widgetList<Text>(find.descendant(
      of: find.byType(ElevatedButton).last,
      matching: find.byType(Text),
    ))
    .map((w) => w.data ?? '')
    .join(' ');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the sheet says which of the three things a sell does', () {
    testWidgets('holding it: names the holding, button stays SELL-shaped',
        (t) async {
      await _pump(t, holdings: [_holding('AAPL', 10)]);
      await _fill(t, ticker: 'AAPL', sell: true, qty: '10');

      expect(find.textContaining('You hold 10 AAPL'), findsOneWidget);
      expect(_ctaLabel(t), isNot(contains('SHORT')));
    });

    testWidgets('holding NONE: says short before submit, and the BUTTON says it',
        (t) async {
      await _pump(t);
      await _fill(t, ticker: 'TSLA', sell: true, qty: '10');

      expect(find.textContaining('You hold no TSLA'), findsOneWidget);
      expect(find.textContaining('opens a short'), findsOneWidget);
      // The structural half. A first attempt changed only the button's colour,
      // which this assertion is here to fail.
      expect(_ctaLabel(t), contains('SHORT'),
          reason: 'the word must be on the control being pressed, not only '
              'above it');
    });

    testWidgets('a buy never claims to be a short', (t) async {
      await _pump(t, holdings: [_holding('AAPL', 10)]);
      await _fill(t, ticker: 'TSLA', qty: '10');

      expect(find.textContaining('opens a short'), findsNothing);
      expect(_ctaLabel(t), isNot(contains('SHORT')));
    });

    testWidgets('crossing zero is still the refusal, not the notice',
        (t) async {
      await _pump(t, holdings: [_holding('AAPL', 10)]);
      await _fill(t, ticker: 'AAPL', sell: true, qty: '15');

      expect(find.textContaining('Selling 15'), findsOneWidget);
      // One sentence before the button, never two competing ones.
      expect(find.textContaining('You hold 10 AAPL —'), findsNothing);
    });
  });

  group('SELL prefills what you actually hold', () {
    testWidgets('flipping to SELL fills the quantity from the holding',
        (t) async {
      await _pump(t, holdings: [_holding('AAPL', 7)]);
      await _fill(t, ticker: 'AAPL', sell: true);

      expect(find.textContaining('You hold 7 AAPL — selling 7'), findsOneWidget);
    });

    testWidgets('a ticker with nothing held is left alone, not pre-shorted',
        (t) async {
      await _pump(t);
      await _fill(t, ticker: 'TSLA', sell: true);

      // Still the default 1 — the sheet must not pre-load a short the user
      // never asked for.
      expect(find.textContaining('You hold no TSLA'), findsOneWidget);
    });
  });

  group('DEF312 — the long bracket is refused on the client too', () {
    /// A LIMIT order gives the sheet an entry price without a quote, which is
    /// the resting-order case the server judges at fill anyway.
    Future<void> pumpLimitBuy(
      WidgetTester t, {
      required String limit,
      String? stop,
      String? target,
    }) async {
      await t.binding.setSurfaceSize(const Size(390, 1600));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(ProviderScope(
        overrides: [
          simNotifierProvider.overrideWith((ref) => _FixedSim(
                ref,
                SimState(
                  portfolio: _portfolio(),
                  restingOrdersSupported: true,
                ),
              )),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(
            body: SingleChildScrollView(child: TradeTicketSheet()),
          ),
        ),
      ));
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      await _fill(t, ticker: 'AAPL', qty: '2', stop: stop, target: target);
      await t.tap(find.text('LIMIT'));
      await t.pump(const Duration(milliseconds: 120));
      await t.enterText(
        find.byWidgetPredicate((w) =>
            w is TextField &&
            w.decoration?.labelText != null &&
            w.decoration!.labelText!.toUpperCase().contains('LIMIT')),
        limit,
      );
      for (var i = 0; i < 3; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
    }

    testWidgets('a stop ABOVE the entry is refused', (t) async {
      await pumpLimitBuy(t, limit: '190', stop: '210');
      expect(find.textContaining('stop belongs below'), findsOneWidget);
    });

    testWidgets('a target BELOW the entry is refused', (t) async {
      await pumpLimitBuy(t, limit: '190', target: '180');
      expect(find.textContaining('target belongs above'), findsOneWidget);
    });

    testWidgets('a correct long bracket says nothing', (t) async {
      // Non-vacuity. Without this the whole group would pass against a rule
      // that refused every bracket.
      await pumpLimitBuy(t, limit: '190', stop: '180', target: '210');
      expect(find.textContaining('belongs below'), findsNothing);
      expect(find.textContaining('belongs above'), findsNothing);
    });

    testWidgets('an unset bracket is not a violation', (t) async {
      await pumpLimitBuy(t, limit: '190');
      expect(find.textContaining('belongs'), findsNothing);
    });
  });
}
