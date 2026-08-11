/// DEF259 — you could open a game position and never close it.
///
/// Saiful, playing the shipped build: *"how do I close an open trade I have?
/// I want to sell (or buy, if I short) tickers during the day"*. You couldn't.
/// The backend has supported SELL since slice 2 and the ticket's notifier even
/// carried a `pickSide` method — which was called from **nowhere**. `side` was
/// hard-coded to `'buy'` and there was no sell affordance on any of the eight
/// games screens. In a contest scored on P&L that is not a missing
/// convenience, it is a missing half of the game: the only exit was the run
/// ending.
///
/// The subtle half of the fix, and what these tests mostly pin: **a buy and a
/// sell divide different things.** A buy divides CASH (25% = a quarter of
/// what's available to deploy); a sell divides the POSITION (25% = a quarter
/// of the shares held, 100% = close it). Sizing a sell against cash would be
/// nonsense in the ordinary case and impossible in the important one — a
/// player whose cash is fully committed to queued orders has exactly 0 to
/// size against, and closing a position is the one thing they most need to
/// do.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_run_screen.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

const _held = GameHolding(
  ticker: 'AAPL',
  quantity: 4.0,
  avgCost: 150.0,
  mark: 180.0,
);

GameRunDetail _detail({double cash = 5000, double committed = 0}) =>
    GameRunDetail(
      runId: _runId,
      fieldId: 'f1',
      cadence: 'week',
      state: 'active',
      stake: 10000,
      cash: cash,
      cashCommitted: committed,
      holdings: const [_held],
      priceSource: 'yfinance',
      daysLeft: 3,
      twrPct: 1.0,
    );

Future<FakeGamesApiClient> _pumpRun(
  WidgetTester tester, {
  GameRunDetail? detail,
}) async {
  final api = FakeGamesApiClient();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        gamesRunDetailProvider(_runId)
            .overrideWith((ref) async => detail ?? _detail()),
        gamesQueuedOrdersProvider(_runId).overrideWith((ref) async => []),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesRunScreen(runId: _runId),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  return api;
}

Future<FakeGamesApiClient> _pumpSellTicket(
  WidgetTester tester, {
  GameRunDetail? detail,
  double heldQuantity = 4.0,
}) async {
  final api = FakeGamesApiClient();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        gamesRunDetailProvider(_runId)
            .overrideWith((ref) async => detail ?? _detail()),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: GamesTradeTicketScreen(
            runId: _runId,
            sellTicker: 'AAPL',
            heldQuantity: heldQuantity,
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  await tester.pump();
  return api;
}

void main() {
  group('the exit exists at all', () {
    testWidgets('every open position offers a SELL', (tester) async {
      await _pumpRun(tester);
      expect(find.text('SELL'), findsOneWidget);
      expect(find.text('AAPL'), findsWidgets);
    });
  });

  group('a sell divides the position, not the cash', () {
    testWidgets('the size step says so', (tester) async {
      await _pumpSellTicket(tester);
      expect(find.text('HOW MUCH OF THE POSITION'), findsOneWidget);
      // Not the buy step's label — a different denominator gets a different
      // label, or the number silently changes meaning.
      expect(find.text('HOW MUCH'), findsNothing);
    });

    testWidgets('the readout is shares, never a dollar figure', (tester) async {
      await _pumpSellTicket(tester);
      // Default size chip applied to 4 shares.
      expect(find.textContaining('shares'), findsWidgets);
    });

    testWidgets('the 100% chip says it closes the position', (tester) async {
      await _pumpSellTicket(tester);
      expect(find.text('Close it'), findsOneWidget);
      // "All in" means the OPPOSITE thing and must not appear on a sell.
      expect(find.text('All in'), findsNothing);
    });

    testWidgets('the quote is sized in SHARES, not dollars', (tester) async {
      final api = await _pumpSellTicket(tester);
      await tester.tap(find.text('Close it'));
      await tester.pump();
      await tester.pump();

      expect(api.quantityQuoteCallsSeen.where((q) => q != null), isNotEmpty,
          reason: 'a sell must size by quantity — a dollar round-trip through '
              'a price leaves a dust holding behind at 100%');
      expect(api.quantityQuoteCallsSeen.last, 4.0);
      expect(api.quoteCallsSeen.last.side, 'sell');
    });
  });

  group('a fully-committed player can still get out', () {
    testWidgets('zero available cash does not block a sell', (tester) async {
      // 10,000 stake, all of it committed to queued orders: cashAvailable is
      // 0. This is the exact state Saiful was in on build 78, and it is the
      // state in which closing a position matters most.
      await _pumpSellTicket(
        tester,
        detail: _detail(cash: 0, committed: 10000),
      );

      expect(find.text('HOW MUCH OF THE POSITION'), findsOneWidget);
      // The "nothing left to deploy" panel is a BUY-side refusal and must not
      // appear here.
      expect(find.textContaining('Nothing left'), findsNothing);
    });
  });

  group('the notifier', () {
    test('sizes a sell off held shares and refuses when none are held', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickSide('sell');
      notifier.pickTicker('AAPL');
      notifier.pickSize(50);
      await notifier.fetchQuote(cashAvailable: 0, heldQuantity: 4.0);
      expect(container.read(gamesTicketProvider(_runId)).quote?.shares, 2.0);

      notifier.pickSize(100);
      await notifier.fetchQuote(cashAvailable: 0, heldQuantity: 0);
      final state = container.read(gamesTicketProvider(_runId));
      expect(state.quoting, isFalse, reason: 'must end in a drawable state');
      expect(state.error, contains('hold none'));
    });

    test('a null held quantity waits; zero is an answer', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickSide('sell');
      notifier.pickTicker('AAPL');
      notifier.pickSize(50);

      await notifier.fetchQuote(cashAvailable: 0, heldQuantity: null);
      expect(container.read(gamesTicketProvider(_runId)).quoting, isTrue,
          reason: 'holdings still arriving is something to wait for');

      await notifier.fetchQuote(cashAvailable: 0, heldQuantity: 0);
      expect(container.read(gamesTicketProvider(_runId)).quoting, isFalse,
          reason: 'zero held is an answer, not a wait');
    });

    test('switching side clears the size — the percentage changes meaning',
        () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickTicker('AAPL');
      notifier.pickSize(50);
      expect(container.read(gamesTicketProvider(_runId)).sizePct, 50);

      notifier.pickSide('sell');
      final state = container.read(gamesTicketProvider(_runId));
      expect(state.side, 'sell');
      expect(state.ticker, 'AAPL', reason: 'the instrument survives');
      expect(state.sizePct, isNull,
          reason: '50% of cash and 50% of the position are different orders');
    });
  });
}
