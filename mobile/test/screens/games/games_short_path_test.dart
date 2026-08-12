/// CR109 Amendment G — shorting in the game, and the way back out.
///
/// Saiful, 2026-08-11: *"the game does not allow 'short' selling? we will
/// need to add a 'fee' for short selling. lets set it at 0.3% for now."*
///
/// The client-side risk this file exists to pin is the **denominator**. The
/// wire has two sides and four actions map onto them: a buy opens a long or
/// covers a short; a sell closes a long or opens one. The two opening
/// actions size against CASH; the two closing actions size against the
/// POSITION. A ticket that knew only the side had to guess, and guessing
/// wrong makes "25%" mean two different quantities on one screen — the exact
/// class of defect DEF259 and the size-slider bug were both instances of.
/// So the ticket carries a MODE, and these tests assert the mode picks the
/// right denominator every time.
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

const _short = GameShort(
  id: 'sp-1',
  ticker: 'TSLA',
  quantity: 10.0,
  entryPrice: 200.0,
  cashPosted: 2000.0,
  mark: 180.0,
  unrealisedPnl: 200.0,
);

const _held = GameHolding(
  ticker: 'AAPL',
  quantity: 4.0,
  avgCost: 150.0,
  mark: 180.0,
);

GameRunDetail _detail({
  double cash = 5000,
  List<GameHolding> holdings = const [_held],
  List<GameShort> shorts = const [_short],
  double cashCommitted = 0,
  int queuedOrders = 0,
}) =>
    GameRunDetail(
      runId: _runId,
      fieldId: 'f1',
      cadence: 'week',
      state: 'active',
      stake: 10000,
      cash: cash,
      cashCommitted: cashCommitted,
      queuedOrderCount: queuedOrders,
      holdings: holdings,
      shorts: shorts,
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

Future<FakeGamesApiClient> _pumpTicket(
  WidgetTester tester, {
  GameRunDetail? detail,
  String? coverTicker,
  double? coverQuantity,
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
            coverTicker: coverTicker,
            coverQuantity: coverQuantity,
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
  group('a short is drawn as its own kind of position', () {
    testWidgets('it gets its own section, not a row in POSITIONS',
        (tester) async {
      await _pumpRun(tester);
      expect(find.text('SHORTS'), findsOneWidget);
      expect(find.text('POSITIONS'), findsOneWidget);
    });

    testWidgets('the row is labelled SHORT on the row itself', (tester) async {
      await _pumpRun(tester);
      // Not only under the heading — a player scrolling past it must still
      // be able to tell which way the position points.
      expect(find.text('SHORT'), findsWidgets);
    });

    testWidgets('a book with only shorts is not the empty-book state',
        (tester) async {
      await _pumpRun(
        tester,
        detail: _detail(holdings: const []),
      );
      // §13.3's empty-book panel would tell a player holding a live short
      // that they have deployed nothing. (Matched on the panel's own body,
      // not on "to deploy" — the cash header carries "Available to deploy"
      // on every run and would make this pass for the wrong reason.)
      expect(find.text('SHORTS'), findsOneWidget);
      expect(find.textContaining('There is no rule about how'), findsNothing);
    });

    testWidgets('every open short offers a COVER', (tester) async {
      await _pumpRun(tester);
      expect(find.text('COVER'), findsOneWidget);
    });
  });

  group('the direction toggle', () {
    testWidgets('the ticket offers LONG and SHORT before the ticker',
        (tester) async {
      await _pumpTicket(tester);
      expect(find.text('DIRECTION'), findsOneWidget);
      expect(find.text('LONG'), findsOneWidget);
      expect(find.text('SHORT'), findsOneWidget);
    });

    testWidgets('picking SHORT states the fee, the collateral and the floor',
        (tester) async {
      // REWRITTEN for CR109 Amendment I. This used to assert the words "no
      // floor", from Amendment G's *"A short can lose more than it ties up.
      // There is no floor."* The forced buy-in made that false, so the test
      // asserting it had to go with it — a green test pinning a retired rule
      // is worse than no test, because it argues for keeping the rule.
      await _pumpTicket(tester);
      await tester.tap(find.text('SHORT'));
      await tester.pump();
      expect(find.textContaining('0.3%'), findsOneWidget);
      // DEF272 — why the size slider divides cash on a short. Its absence is
      // what made the ticket read as "behaving as if I am buying".
      expect(find.textContaining('no leverage'), findsOneWidget);
      // The floor, and the gap that can still jump it. BOTH: a hard cap we
      // do not have would be the worse of the two errors to ship.
      expect(find.textContaining('climbs 90%'), findsOneWidget);
      expect(find.textContaining('gap'), findsOneWidget);
    });

    testWidgets('the retired "no floor" claim is gone from the ticket',
        (tester) async {
      // The mutation guard for the rewrite above: re-adding the old string
      // alongside the new one would pass every assertion in it.
      await _pumpTicket(tester);
      await tester.tap(find.text('SHORT'));
      await tester.pump();
      expect(find.textContaining('no floor'), findsNothing);
    });

    testWidgets('the size readout calls a short\'s cash COLLATERAL, not spend',
        (tester) async {
      // DEF272. Same number as a buy's — a short posts its full notional, so
      // the arithmetic is identical — and the wrong noun for it. "2,500.00
      // AMI Cash" reads as money gone; it comes back on the cover.
      await _pumpTicket(tester);
      await tester.tap(find.text('SHORT'));
      await tester.pump();
      // No watchlist chips in this fixture — type + submit, same as
      // games_trade_ticket_test.dart's TAP 1.
      await tester.enterText(find.byType(TextField), 'TSLA');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      expect(find.text('2 · HOW MUCH TO SHORT'), findsOneWidget);
      expect(find.textContaining('posted as collateral'), findsOneWidget);
      // And never the buy's noun for the same number.
      expect(find.textContaining('AMI Cash'), findsNothing);
    });
  });

  group('DEF272 — the dead end when every unit is deployed', () {
    testWidgets('cash in POSITIONS names the no-leverage rule, not phantom orders',
        (tester) async {
      // A fully-deployed book with ZERO queued orders — the shape of
      // Saiful's run (4.09 free against 10,000, every other unit in
      // positions). The old panel said "0.00 is committed to 0 orders
      // waiting on the next open. Cancel one to free up cash" — a false
      // sentence pointing at an empty list, on the screen that had just
      // refused him.
      await _pumpTicket(
        tester,
        detail: _detail(cash: 0),
      );
      expect(find.textContaining('in open positions'), findsOneWidget);
      expect(find.textContaining('no leverage'), findsOneWidget);
      expect(find.textContaining('waiting on the next open'), findsNothing);
      expect(find.text('SEE POSITIONS'), findsOneWidget);
    });

    testWidgets('cash in QUEUED ORDERS still says so, and offers the cancel',
        (tester) async {
      // The mutation guard: a panel rewritten to always blame positions
      // would pass the test above and break the case it was built for.
      await _pumpTicket(
        tester,
        detail: _detail(cash: 9995.91, cashCommitted: 9995.91, queuedOrders: 3),
      );
      expect(find.textContaining('waiting on the next open'), findsOneWidget);
      expect(find.textContaining('in open positions'), findsNothing);
      expect(find.text('SEE QUEUED ORDERS'), findsOneWidget);
    });

    test('a short quotes on the SELL side, sized in AMI Cash', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final api = container.read(apiClientProvider) as FakeGamesApiClient;
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickMode('short');
      notifier.pickTicker('TSLA');
      notifier.pickSize(50);
      await notifier.fetchQuote(cashAvailable: 4000);

      expect(api.quoteCallsSeen.last.side, 'sell');
      // Sized against CASH — a notional, not a share count. A short opens a
      // position that does not exist yet, so there is no position to divide;
      // half of 4,000 is 2,000 of AMI Cash committed.
      expect(api.quoteCallsSeen.last.notional, 2000.0);
      expect(api.quantityQuoteCallsSeen.last, isNull);
    });

    test('a short is refused when there is no cash, exactly as a buy is',
        () async {
      // No leverage: a short ties up the full notional, so an empty balance
      // blocks it. The COVER is the one that must never be blocked.
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickMode('short');
      notifier.pickTicker('TSLA');
      notifier.pickSize(50);
      await notifier.fetchQuote(cashAvailable: 0);

      final state = container.read(gamesTicketProvider(_runId));
      expect(state.quoting, isFalse, reason: 'must end in a drawable state');
      expect(state.error, isNotNull);
    });

    test('switching direction clears the size', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container.read(gamesTicketProvider(_runId).notifier);

      notifier.pickTicker('TSLA');
      notifier.pickSize(50);
      expect(container.read(gamesTicketProvider(_runId)).sizePct, 50);

      notifier.pickMode('short');
      // A percentage chosen while going long must not survive the switch —
      // the number would keep its value and change its meaning.
      expect(container.read(gamesTicketProvider(_runId)).sizePct, isNull);
    });
  });

  group('mode decides the wire side and the denominator', () {
    test('buy and cover both send `buy`; short and sell both send `sell`', () {
      const buy = GamesTicketState(mode: 'buy');
      const cover = GamesTicketState(mode: 'cover');
      const short = GamesTicketState(mode: 'short');
      const sell = GamesTicketState(mode: 'sell');

      expect(buy.side, 'buy');
      expect(cover.side, 'buy');
      expect(short.side, 'sell');
      expect(sell.side, 'sell');
    });

    test('only a SELL divides the position', () {
      // The whole reason `mode` exists. `short` shares a wire side with
      // `sell` and a denominator with `buy`; nothing derivable from the side
      // alone can tell them apart.
      expect(const GamesTicketState(mode: 'sell').sizesAgainstPosition, isTrue);
      expect(
          const GamesTicketState(mode: 'short').sizesAgainstPosition, isFalse);
      expect(const GamesTicketState(mode: 'buy').sizesAgainstPosition, isFalse);
      expect(
          const GamesTicketState(mode: 'cover').sizesAgainstPosition, isFalse);
    });

    test('a cover skips the size step entirely', () {
      const cover = GamesTicketState(mode: 'cover', ticker: 'TSLA');
      // Straight to confirm: the server accepts the whole position or
      // nothing, so a percentage would be a choice it refuses.
      expect(cover.step, 3);
      const buy = GamesTicketState(mode: 'buy', ticker: 'TSLA');
      expect(buy.step, 2);
    });
  });

  group('covering', () {
    testWidgets('the ticket opens on the named short with no size step',
        (tester) async {
      await _pumpTicket(tester, coverTicker: 'TSLA', coverQuantity: 10.0);
      expect(find.textContaining('Cover TSLA'), findsOneWidget);
      expect(find.textContaining('short 10.0000 shares'), findsOneWidget);
      expect(find.text('HOW MUCH'), findsNothing);
      expect(find.text('HOW MUCH OF THE POSITION'), findsNothing);
    });

    testWidgets('it says why there is no size step', (tester) async {
      await _pumpTicket(tester, coverTicker: 'TSLA', coverQuantity: 10.0);
      expect(find.textContaining('whole position'), findsOneWidget);
    });

    testWidgets('it quotes the WHOLE short on the buy side', (tester) async {
      final api =
          await _pumpTicket(tester, coverTicker: 'TSLA', coverQuantity: 10.0);
      await tester.pumpAndSettle();

      expect(api.quoteCallsSeen, isNotEmpty);
      expect(api.quoteCallsSeen.last.side, 'buy');
      expect(api.quoteCallsSeen.last.ticker, 'TSLA');
      // Shares, and exactly the position's shares — not a percentage of it.
      expect(api.quantityQuoteCallsSeen.last, 10.0);
    });

    testWidgets('a cover is offered even with zero cash available',
        (tester) async {
      // The mirror of DEF259's load-bearing guard. The cash to buy back was
      // posted when the short was opened; gating the cover behind a balance
      // would trap a player in the one position whose loss is unbounded.
      final api = await _pumpTicket(
        tester,
        detail: _detail(cash: 0),
        coverTicker: 'TSLA',
        coverQuantity: 10.0,
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Nothing left to deploy'), findsNothing);
      expect(api.quoteCallsSeen, isNotEmpty);
    });
  });

  group('the short position model', () {
    test('P&L is read from the server, never re-derived with a flipped sign',
        () {
      final s = GameShort.fromJson(const {
        'id': 'sp-1',
        'ticker': 'TSLA',
        'quantity': 10.0,
        'entry_price': 200.0,
        'cash_posted': 2000.0,
        'mark': 180.0,
        'unrealised_pnl': 200.0,
      });
      expect(s.unrealisedPnl, 200.0);
      expect(s.unrealisedPct, closeTo(10.0, 0.001));
      expect(s.value, 2200.0);
    });

    test('a short that moved against the player is worth less than it posted',
        () {
      final s = GameShort.fromJson(const {
        'id': 'sp-1',
        'ticker': 'TSLA',
        'quantity': 10.0,
        'entry_price': 200.0,
        'cash_posted': 2000.0,
        'mark': 320.0,
        'unrealised_pnl': -1200.0,
      });
      expect(s.value, 800.0);
      expect(s.unrealisedPct, closeTo(-60.0, 0.001));
    });

    test('the run detail parses a shorts array off the wire', () {
      final d = GameRunDetail.fromJson(const {
        'run_id': _runId,
        'cadence': 'week',
        'state': 'active',
        'total_value': 10000.0,
        'current_cash': 5000.0,
        'holdings': [],
        'shorts': [
          {
            'id': 'sp-1',
            'ticker': 'TSLA',
            'quantity': 10.0,
            'entry_price': 200.0,
            'cash_posted': 2000.0,
            'mark': 180.0,
            'unrealised_pnl': 200.0,
          }
        ],
      });
      expect(d.shorts.single.ticker, 'TSLA');
      // A book holding only shorts has been deployed — it is not empty.
      expect(d.isEmptyBook, isFalse);
    });

    test('a payload with no shorts key yields an empty list, never a null', () {
      final d = GameRunDetail.fromJson(const {
        'run_id': _runId,
        'current_cash': 5000.0,
        'holdings': [],
      });
      expect(d.shorts, isEmpty);
      expect(d.isEmptyBook, isTrue);
    });
  });
}
