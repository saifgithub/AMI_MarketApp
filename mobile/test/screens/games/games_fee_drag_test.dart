/// DEF274 — the fee minimum, made legible on a small order.
///
/// Saiful's run held **4.09** against a 10,000 book. The size slider happily
/// offered 100% of it, and the confirm card priced the trade as *"est. fee
/// $1.00"* — true, unremarkable next to a stated 0.1% rate, and in fact
/// **24% of the trade**. `FEE_MIN` is a floor, so the smaller the order the
/// larger the bite, and the one number that said so was the one number not on
/// the card.
///
/// **Stated, never blocked.** §7.1's frictions doctrine is explicit that
/// *"nothing caps what a player may do"*, and when Saiful was asked to choose
/// between a cap and a price-shaped equivalent he took the price (Amendment
/// D's day-trade ruling). A minimum order size here would be the rule he
/// rejected; this is that rule's price, made visible before the confirm.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

GameRunDetail _detail({double cash = 10000}) => GameRunDetail(
      runId: _runId,
      fieldId: 'f1',
      cadence: 'week',
      state: 'active',
      stake: 10000,
      cash: cash,
      holdings: const [],
      shorts: const [],
      priceSource: 'yfinance',
      daysLeft: 3,
      twrPct: 1.0,
    );

GameTradeQuote _quote({required double notional, required double estFee}) =>
    GameTradeQuote(
      ticker: 'AAPL',
      side: 'buy',
      shares: notional / 180.0,
      price: 180.0,
      notional: notional,
      estFee: estFee,
      bookPercentage: notional / 100.0,
      priceSource: 'live',
      willQueue: false,
    );

/// Drives the ticket all the way to TAP 3, which is where the confirm card —
/// and the line under test — actually renders.
Future<void> _pumpToConfirm(
  WidgetTester tester, {
  required GameTradeQuote quote,
  required double cash,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(
          FakeGamesApiClient(tradeQuote: quote),
        ),
        gamesRunDetailProvider(_runId)
            .overrideWith((ref) async => _detail(cash: cash)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(
          body: GamesTradeTicketScreen(runId: _runId),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();

  // TAP 1 — no watchlist chips in this fixture, so type and submit.
  await tester.enterText(find.byType(TextField), 'AAPL');
  await tester.testTextInput.receiveAction(TextInputAction.done);
  await tester.pumpAndSettle();

  // TAP 2 — any size chip; the quote is fixed by the fake regardless.
  await tester.tap(find.text('25%'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a tiny order says what percentage the fee actually is',
      (tester) async {
    await _pumpToConfirm(
      tester,
      // 4.09 of book against the $1.00 minimum — 24.4%.
      quote: _quote(notional: 4.09, estFee: 1.00),
      cash: 4.09,
    );
    expect(find.textContaining('24.4% of this order'), findsOneWidget);
  });

  testWidgets('an ordinary order carries no such line', (tester) async {
    // The mutation guard: a line that always rendered would pass the test
    // above and put a scold on every ticket in the game — which is precisely
    // what CR134 §21 rules out for a mirror surface ("measurement, never a
    // scold").
    await _pumpToConfirm(
      tester,
      quote: _quote(notional: 2500.0, estFee: 2.50),  // 0.1%, the stated rate
      cash: 10000,
    );
    expect(find.textContaining('of this order'), findsNothing);
  });

  testWidgets('a zero-notional quote reports no drag rather than NaN%',
      (tester) async {
    // 0/0 renders as "NaN%" — a number that means nothing, on a card whose
    // whole job is to be checkable.
    await _pumpToConfirm(
      tester,
      quote: _quote(notional: 0.0, estFee: 1.00),
      cash: 10000,
    );
    expect(find.textContaining('NaN'), findsNothing);
    expect(find.textContaining('of this order'), findsNothing);
  });
}
