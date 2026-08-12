/// CR109 — "My run", the screen that closes the slice-2 gap Saiful found by
/// using the shipped build.
///
/// These tests assert the things the ABSENCE of this screen broke, not that
/// widgets render:
///
///   * a queued order can be SEEN and CANCELLED — the ticket has promised
///     "free to cancel any time before it fills" (§5.1) since slice 2
///     shipped, with nothing behind the promise;
///   * a cancel that the SERVER refused is never reported as a cancellation;
///   * an estimate says it is an estimate, and says so differently when the
///     price feed fell through to the mock walk (CR040);
///   * the empty book is §13.3's stated surface, not a blank list;
///   * a player with orders queued is NOT in the empty-book state — they
///     have acted, and telling them otherwise is the anxiety §13.3 names.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_run_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

GameRunDetail _detail({
  double cash = 10000,
  double committed = 0,
  double? available,
  int queuedCount = 0,
  List<GameHolding> holdings = const [],
  double stake = 10000,
  String priceSource = 'yfinance',
  int daysLeft = 5,
}) {
  return GameRunDetail(
    runId: _runId,
    fieldId: 'f1',
    cadence: 'week',
    state: 'active',
    stake: stake,
    cash: cash,
    cashCommitted: committed,
    cashAvailable: available,
    queuedOrderCount: queuedCount,
    holdings: holdings,
    priceSource: priceSource,
    daysLeft: daysLeft,
    twrPct: 0,
  );
}

Future<FakeGamesApiClient> _pump(
  WidgetTester tester, {
  required GameRunDetail detail,
  List<GameQueuedOrder> orders = const [],
  bool cancelSucceeds = true,
}) async {
  final api = FakeGamesApiClient(
    queuedOrders: orders,
    cancelSucceeds: cancelSucceeds,
  );
  // A tall surface, because this screen is a scrolling ListView and these
  // tests tap things near the bottom of it (the queued-order Cancel, the
  // trade CTA). On the default 800px test window those taps land on whatever
  // the default viewport happens to cut at, so ADDING a card anywhere above
  // them breaks tests that have nothing to do with the card — which is
  // exactly what CR109 slice 5's arc beat did. Sizing the window past the
  // screen's full height makes these assertions about the screen rather
  // than about where the fold happens to fall.
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        gamesRunDetailProvider(_runId).overrideWith((ref) async => detail),
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

GameQueuedOrder _order({
  String id = 'o1',
  String ticker = 'AAPL',
  String side = 'buy',
  double quantity = 1.5958,
  double estTotal = 501.01,
  String priceSource = 'yfinance',
}) {
  return GameQueuedOrder(
    orderId: id,
    ticker: ticker,
    side: side,
    quantity: quantity,
    estPrice: 313.33,
    estNotional: estTotal - 1.0,
    estFee: 1.0,
    estTotal: estTotal,
    priceSource: priceSource,
  );
}

void main() {
  group('the queued-orders surface — §13.3\'s "most-seen state"', () {
    testWidgets('lists a pending order with its share count and est. cost',
        (tester) async {
      await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );

      expect(find.text('WAITING FOR THE OPEN'), findsOneWidget);
      expect(find.text('BUY AAPL'), findsOneWidget);
      expect(
        find.textContaining('501.01'),
        findsWidgets,
        reason: 'the estimated cost is the number that answers "why is my '
            'available cash lower than my book"',
      );
    });

    testWidgets('says the cost is an estimate, not the fill price',
        (tester) async {
      await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );
      expect(
        find.textContaining('It fills at the next open'),
        findsOneWidget,
        reason: 'the fill happens at a price nobody has yet; presenting the '
            'current-price estimate without saying so is CR040',
      );
    });

    testWidgets('a mock-walk estimate says it is simulated', (tester) async {
      await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order(priceSource: 'mock_walk')],
      );
      expect(find.textContaining('simulated, not live'), findsOneWidget);
      expect(
        find.textContaining('It fills at the next open'),
        findsNothing,
        reason: 'the ordinary estimate note would imply a live price behind '
            'a number that came from the fallback walk',
      );
    });
  });

  group('cancelling — the promise the app had already made', () {
    testWidgets('confirms first, then reports the cancellation',
        (tester) async {
      final api = await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );

      await tester.tap(find.text('Cancel').first);
      await tester.pumpAndSettle();
      expect(find.text('Cancel this order?'), findsOneWidget);
      expect(
        find.textContaining('Nothing is charged either way'),
        findsOneWidget,
        reason: 'an order that never filled owes no fee, and the player has '
            'no way to know that unless it is said',
      );

      await tester.tap(find.text('Cancel').last);
      await tester.pumpAndSettle();

      expect(api.cancelCallsSeen.single.orderId, 'o1');
      expect(find.text('Order cancelled.'), findsOneWidget);
    });

    testWidgets('a server refusal is NOT reported as a cancellation',
        (tester) async {
      // The order filled between the list being drawn and the tap. The
      // server returns 200 with `cancelled: false`. Reporting success on a
      // non-throwing call is precisely the `status ?? 'filled'` failure that
      // shipped in build 74 — same shape, different endpoint.
      await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
        cancelSucceeds: false,
      );

      await tester.tap(find.text('Cancel').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel').last);
      await tester.pumpAndSettle();

      expect(find.text('Order cancelled.'), findsNothing);
      expect(find.textContaining('already filled'), findsOneWidget);
    });

    testWidgets('dismissing the dialog places no call', (tester) async {
      final api = await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );
      await tester.tap(find.text('Cancel').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Keep it'));
      await tester.pumpAndSettle();
      expect(api.cancelCallsSeen, isEmpty);
    });
  });

  group('the cash that is actually spendable', () {
    testWidgets('committed cash is shown as the reason available is lower',
        (tester) async {
      await _pump(
        tester,
        detail: _detail(cash: 10000, committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );
      expect(find.text('Committed to queued orders'), findsOneWidget);
      expect(find.text('−501.01'), findsOneWidget);
      expect(
        find.text('9,498.99'),
        findsOneWidget,
        reason: 'available = cash − committed. The build Saiful used showed '
            'the full 10,000 with an order already queued against it',
      );
    });

    testWidgets('a run with no queued orders shows no committed row',
        (tester) async {
      await _pump(tester, detail: _detail());
      expect(find.text('Committed to queued orders'), findsNothing);
    });
  });

  group('the empty book — §13.3\'s "highest-anxiety moment"', () {
    testWidgets('is a stated surface, never a blank list', (tester) async {
      await _pump(tester, detail: _detail());
      expect(find.text('Nothing on the book yet'), findsOneWidget);
      expect(
        find.textContaining('no rule about how'),
        findsOneWidget,
        reason: '§13.3 asks for the honest note that nothing stops the '
            'player putting the whole stake in one name',
      );
      // Twice on purpose: the days-left chip in the header and the clock in
      // the empty-book copy. §13.3 asks for the clock IN that copy.
      expect(find.textContaining('5 days'), findsWidgets);
    });

    testWidgets('a player with orders queued is NOT shown the empty book',
        (tester) async {
      await _pump(
        tester,
        detail: _detail(committed: 501.01, queuedCount: 1),
        orders: [_order()],
      );
      expect(
        find.text('Nothing on the book yet'),
        findsNothing,
        reason: 'they have acted; the surface they need is the queue, and '
            '"nothing on the book" reads as though the order vanished',
      );
    });
  });

  group('positions and book heat', () {
    testWidgets('a holding renders with its unrealised P&L', (tester) async {
      await _pump(
        tester,
        detail: _detail(
          cash: 5000,
          stake: 10500,
          holdings: const [
            GameHolding(
                ticker: 'NVDA', quantity: 10, avgCost: 500, mark: 550),
          ],
        ),
      );
      expect(find.text('NVDA'), findsOneWidget);
      // Also the "Invested" row (10,500 book − 5,000 cash), which is the
      // same number by construction — both are correct.
      expect(find.text('5,500.00'), findsWidgets);
      expect(find.textContaining('+500.00'), findsOneWidget);
      expect(find.textContaining('10.0%'), findsOneWidget);
    });

    testWidgets('book heat states the concentration as a fact', (tester) async {
      await _pump(
        tester,
        detail: _detail(
          cash: 5000,
          stake: 10000,
          holdings: const [
            GameHolding(ticker: 'NVDA', quantity: 10, avgCost: 500, mark: 500),
          ],
        ),
      );
      // 5,000 of a 10,000 book. Stated, with nothing attached to it — the
      // game has no diversification rule and this gauge must not invent one.
      expect(find.text('50% in NVDA'), findsOneWidget);
    });

    testWidgets('an all-cash book says so rather than showing 0%',
        (tester) async {
      await _pump(tester, detail: _detail());
      expect(find.text('All cash. Nothing at risk yet.'), findsOneWidget);
    });
  });

  group('provenance on the book value', () {
    testWidgets('mock-walk marks on a real book are disclosed', (tester) async {
      await _pump(
        tester,
        detail: _detail(
          cash: 5000,
          stake: 10000,
          priceSource: 'mock_walk',
          holdings: const [
            GameHolding(ticker: 'NVDA', quantity: 10, avgCost: 500, mark: 500),
          ],
        ),
      );
      expect(
        find.textContaining('marked with simulated prices'),
        findsOneWidget,
      );
    });

    testWidgets('an all-cash book is not caveated, whatever the provider says',
        (tester) async {
      // Live Alpha reports `mock_walk` on a book with no holdings — the
      // snapshot echoes the provider regardless of whether a mark was used.
      // Nothing here was priced: the value IS the cash. A caveat on a number
      // no price touched is noise, and noise is how a player learns to skip
      // the caveat that matters.
      await _pump(tester, detail: _detail(priceSource: 'mock_walk'));
      expect(find.textContaining('marked with simulated prices'), findsNothing);
    });
  });

  group('an order the open refused', () {
    testWidgets('is shown with its reason, not silently dropped',
        (tester) async {
      // Saiful: "I have committed more than the 10K allocated AMI Cash...
      // what will happen when we trade for real?" At the open, orders that
      // no longer fit are refused WHOLE — never shrunk — and the row carries
      // the server's reason. The orders list used to filter to state ==
      // "queued", so those rows just vanished: some orders filled, some
      // gone, nothing anywhere saying which or why.
      await _pump(
        tester,
        detail: _detail(),
        orders: [
          const GameQueuedOrder(
            orderId: 'o9',
            ticker: 'BAC',
            side: 'buy',
            quantity: 7.5323,
            state: 'refused',
            cancelReason: 'insufficient cash: need \$476.82, have \$12.00',
          ),
        ],
      );

      expect(find.text('NOT PLACED AT THE OPEN'), findsOneWidget);
      expect(find.textContaining('insufficient cash'), findsOneWidget);
      expect(
        find.text('Cancel'),
        findsNothing,
        reason: 'nothing left to cancel — an action that cannot act is worse '
            'than no action',
      );
    });

    testWidgets('states the rule, so it can be planned around', (tester) async {
      await _pump(
        tester,
        detail: _detail(),
        orders: [
          const GameQueuedOrder(
            orderId: 'o9',
            ticker: 'BAC',
            side: 'buy',
            quantity: 7.5323,
            state: 'refused',
            cancelReason: 'insufficient cash',
          ),
        ],
      );
      expect(find.textContaining('oldest first'), findsOneWidget);
      expect(
        find.textContaining('never shrunk to fit'),
        findsOneWidget,
        reason: 'no partial fills — a shrunk order is a position the player '
            'did not choose',
      );
    });

    testWidgets('a refused order is not counted as pending', (tester) async {
      await _pump(
        tester,
        detail: _detail(),
        orders: [
          const GameQueuedOrder(
            orderId: 'o9',
            ticker: 'BAC',
            side: 'buy',
            quantity: 7.5323,
            state: 'refused',
            cancelReason: 'insufficient cash',
          ),
        ],
      );
      expect(find.text('WAITING FOR THE OPEN'), findsNothing);
    });
  });
}
