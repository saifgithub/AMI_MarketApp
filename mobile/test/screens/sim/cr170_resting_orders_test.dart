/// CR170 + CR171 — the client half, at the places it can be wrong with money.
///
/// The single most important assertion in this file is the capability gate.
/// Against a pre-CR170 backend `POST /v1/sim/submit` accepts `order_type=limit`
/// and runs it through `fill_price = mark if MARKET else (limit_price or mark)`
/// — which rests nothing. It **fills, immediately, at whatever price the user
/// typed**. So an order-type picker shown against a server without the book is
/// not a missing feature, it is a control that quietly does something else with
/// a real ledger, which is the failure CR040 exists for.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/widgets/sim/resting_orders_section.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A server that answers everything except the book — which is what a
/// pre-CR170 backend is.
class _NoBookApi extends ApiClient {
  _NoBookApi({this.bookThrows = true}) : super(baseUrl: 'test://localhost');

  final bool bookThrows;

  @override
  Future<void> simEvaluate(String userId) async {}

  @override
  Future<SimPortfolio> simPortfolio(String userId) async => _portfolio();

  @override
  Future<List<SimTrade>> simListTrades(String userId,
          {String? statusFilter}) async =>
      const [];

  @override
  Future<List<SimRestingOrder>> simRestingOrders(String userId) async {
    if (bookThrows) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/sim/orders/$userId'),
        response: Response<dynamic>(
          requestOptions: RequestOptions(path: '/v1/sim/orders/$userId'),
          statusCode: 404,
        ),
      );
    }
    return [_order()];
  }
}

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

SimPortfolio _portfolio({List<SimHolding> holdings = const []}) => SimPortfolio(
      userId: 'u',
      portfolioId: 'p',
      startingCapital: 10000,
      currentCash: 10000,
      holdings: holdings,
      totalValue: 10000,
      drawdownPct: 0,
    );

SimHolding _holding(double qty) => SimHolding(
      ticker: 'AAPL',
      quantity: qty,
      avgCost: 180,
      mark: 190,
      value: qty * 190,
      unrealisedPnl: qty * 10,
      openedAt: DateTime.utc(2026, 8, 1),
    );

SimRestingOrder _order({
  String state = 'working',
  String orderType = 'limit',
  double? limitPrice = 190,
  String? cancelReason,
  double? distancePct,
}) =>
    SimRestingOrder.fromJson({
      'id': 'o1',
      'ticker': 'AAPL',
      'side': 'buy',
      'quantity': 10,
      'order_type': orderType,
      'state': state,
      'tif': 'day',
      'limit_price': limitPrice,
      'cancel_reason': cancelReason,
      'distance_pct': distancePct,
      'last_seen_price': distancePct == null ? null : 195.0,
    });

Future<void> _pump(
  WidgetTester t,
  Widget child, {
  required SimState sim,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 900));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) => _FixedSim(ref, sim)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  ));
  // Explicit pumps rather than pumpAndSettle: the sheet's own providers leave
  // pending Dio timers against no server, and settle would never return.
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  // `DeviceUser.getOrCreate()` reads SharedPreferences on every refresh; without
  // mock values the plugin channel throws and the whole refresh lands in the
  // error branch, which would make the probe tests below pass for the wrong
  // reason.
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the order-type controls are gated on the backend having a book', () {
    testWidgets('no book ⇒ no picker', (t) async {
      await _pump(t, const TradeTicketSheet(),
          sim: SimState(portfolio: _portfolio()));
      expect(find.text('ORDER TYPE'), findsNothing,
          reason: 'against a pre-CR170 server a limit order does not rest — it '
              'fills instantly at the price typed, so offering the control is '
              'worse than not having the feature');
      expect(find.text('MARKET'), findsNothing);
      expect(find.text('GOOD FOR'), findsNothing);
    });

    testWidgets('a book ⇒ the picker, defaulting to market', (t) async {
      await _pump(t, const TradeTicketSheet(),
          sim: SimState(
              portfolio: _portfolio(), restingOrdersSupported: true));
      expect(find.text('ORDER TYPE'), findsOneWidget);
      expect(find.text('MARKET'), findsOneWidget);
      // TIF only matters for an order that can rest, and market cannot.
      expect(find.text('GOOD FOR'), findsNothing);
    });

    testWidgets('choosing LIMIT reveals the price field and the time in force',
        (t) async {
      await _pump(t, const TradeTicketSheet(),
          sim: SimState(
              portfolio: _portfolio(), restingOrdersSupported: true));
      await t.tap(find.text('LIMIT'));
      await t.pump();
      expect(find.text('LIMIT PRICE'), findsOneWidget);
      expect(find.text('GOOD FOR'), findsOneWidget);
      expect(find.text('TRIGGER PRICE'), findsNothing,
          reason: 'a plain limit has no trigger; showing the field would ask '
              'for a number the order does not have');
    });

    testWidgets('STOP LIMIT asks for both prices', (t) async {
      await _pump(t, const TradeTicketSheet(),
          sim: SimState(
              portfolio: _portfolio(), restingOrdersSupported: true));
      await t.tap(find.text('STOP LIMIT'));
      await t.pump();
      expect(find.text('TRIGGER PRICE'), findsOneWidget);
      expect(find.text('LIMIT PRICE'), findsOneWidget);
    });
  });

  group('the capability probe itself', () {
    // The mutation that motivated this: flipping `_loadRestingOrders`' catch to
    // `supported: true` broke nothing, because every widget test above
    // constructs `SimState` by hand and never runs the probe. The probe is the
    // single most load-bearing decision in this slice, and it had no test at
    // all — a guard that cannot fail is the DEF190 shape.
    test('a backend without the routes is treated as having no book', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(_NoBookApi()),
      ]);
      addTearDown(container.dispose);
      await container.read(simNotifierProvider.notifier).refresh();
      final s = container.read(simNotifierProvider);
      expect(s.restingOrdersSupported, isFalse,
          reason: 'failing OPEN here puts a live order-type picker in front of '
              'a /submit that fills instantly at the price typed');
      expect(s.restingOrders, isEmpty);
      expect(s.portfolio, isNotNull,
          reason: 'an unreachable optional book must not take the portfolio, '
              'the holdings and the trades down with it');
      expect(s.error, isNull);
    });

    test('a backend with the routes is believed', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(_NoBookApi(bookThrows: false)),
      ]);
      addTearDown(container.dispose);
      await container.read(simNotifierProvider.notifier).refresh();
      final s = container.read(simNotifierProvider);
      expect(s.restingOrdersSupported, isTrue);
      expect(s.restingOrders, hasLength(1));
    });
  });

  group('the portfolio section', () {
    testWidgets('renders nothing at all without a book', (t) async {
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(portfolio: _portfolio(), restingOrders: [_order()]));
      expect(find.text('WAITING ORDERS'), findsNothing,
          reason: 'a heading on every portfolio in the app, over nothing, is '
              'the placeholder CR040 forbids');
    });

    testWidgets('renders nothing when the book is empty', (t) async {
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(
              portfolio: _portfolio(), restingOrdersSupported: true));
      expect(find.text('WAITING ORDERS'), findsNothing);
    });

    testWidgets('a working order shows, and offers a cancel', (t) async {
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(
            portfolio: _portfolio(),
            restingOrdersSupported: true,
            restingOrders: [_order()],
          ));
      expect(find.text('WAITING ORDERS'), findsOneWidget);
      expect(find.text('CANCEL ORDER'), findsOneWidget);
    });

    testWidgets('a settled order is shown, not silently dropped', (t) async {
      // The games lane's own docstring records the cost of the alternative:
      // "from the player's side the order simply VANISHED overnight."
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(
            portfolio: _portfolio(),
            restingOrdersSupported: true,
            restingOrders: [
              _order(state: 'rejected', cancelReason: 'blocked: halal universe')
            ],
          ));
      expect(find.text('RECENTLY CLOSED ORDERS'), findsOneWidget);
      expect(find.text('blocked: halal universe'), findsOneWidget,
          reason: 'a non-null cancel_reason always means the SYSTEM refused, '
              'and the sentence is the only thing that says why');
      expect(find.text('CANCEL ORDER'), findsNothing);
    });

    testWidgets('a claimed order cannot be cancelled', (t) async {
      // `filling` means a sweep has it and a money-moving operation is in
      // flight; a cancel there races an outcome that is already unknown.
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(
            portfolio: _portfolio(),
            restingOrdersSupported: true,
            restingOrders: [_order(state: 'filling')],
          ));
      expect(find.text('WAITING ORDERS'), findsOneWidget);
      expect(find.text('CANCEL ORDER'), findsNothing);
    });

    testWidgets('before the first sweep it says so, rather than showing a zero',
        (t) async {
      await _pump(t, const RestingOrdersSection(),
          sim: SimState(
            portfolio: _portfolio(),
            restingOrdersSupported: true,
            restingOrders: [_order()],
          ));
      expect(find.text('Waiting for the first price check'), findsOneWidget,
          reason: '"0.0% away" on an order nothing has checked reads as about '
              'to fill');
    });
  });

  group('the submit response', () {
    test('a resting response parses instead of throwing', () {
      // The CR locates this crash at the sheet's `result.trade!`. It is one
      // layer earlier: the parser used to cast `j['trade']` unconditionally, so
      // a resting response surfaced as a generic "couldn't place that trade"
      // over an order the server had accepted.
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'resting': true,
        'trade': null,
        'order': {
          'id': 'o1',
          'ticker': 'AAPL',
          'side': 'buy',
          'quantity': 10,
          'order_type': 'limit',
          'state': 'working',
          'tif': 'day',
          'limit_price': 190,
        },
      });
      expect(r.ok, isTrue);
      expect(r.resting, isTrue);
      expect(r.trade, isNull);
      expect(r.order?.namedPrice, 190);
    });

    test('resting is read, never inferred from a null trade', () {
      // Inference is a second source of truth for a fact the server already
      // states on every branch. The games lane learned this twice.
      final r = SimSubmitResult.fromJson({'ok': true, 'trade': null});
      expect(r.resting, isFalse,
          reason: 'a null trade with no `resting` flag is a malformed fill, '
              'not a resting order');
    });

    test('a pre-CR170 fill response is unchanged', () {
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': {
          'id': 't1',
          'user_id': 'u',
          'ticker': 'AAPL',
          'side': 'buy',
          'quantity': 10,
          'entry_price': 190.0,
          'status': 'open',
          'opened_at': '2026-08-13T00:00:00Z',
        },
      });
      expect(r.resting, isFalse);
      expect(r.trade?.ticker, 'AAPL');
    });
  });

  group('the cancel verdict comes from the server', () {
    test('a lost race is not reported as a success', () {
      final raced = RestingOrderCancelResult.fromJson(
          {'cancelled': false, 'state': 'filled'});
      expect(raced.cancelled, isFalse);
      expect(raced.state, RestingOrderState.filled);
    });

    test('a state this build does not know is its own thing', () {
      // DEF210 — an order shown as live after the server retired it is the one
      // error the user cannot recover from.
      final odd = RestingOrderCancelResult.fromJson(
          {'cancelled': false, 'state': 'partially_filled'});
      expect(odd.state, RestingOrderState.unknown);
      expect(_order(state: 'partially_filled').isLive, isFalse);
      expect(_order(state: 'partially_filled').isCancellable, isFalse);
    });
  });

  group('CR171 — the ticket refuses before the server has to', () {
    testWidgets('a sell larger than the holding is refused, with the number '
        'that would close', (t) async {
      await _pump(
        t,
        const TradeTicketSheet(tickerPrefill: 'AAPL'),
        sim: SimState(
          portfolio: _portfolio(holdings: [
            _holding(4),
          ]),
        ),
      );
      await t.tap(find.text('SELL'));
      await t.pump();
      await t.enterText(find.byType(TextField).at(1), '10');
      await t.pump();

      expect(find.textContaining('would close that position'), findsOneWidget,
          reason: 'splitting one action into a close plus a short is the '
              'P&L-attribution bug class DEF166 and DEF110 already cost us '
              'twice');
      expect(find.textContaining('sell 4 to close'), findsOneWidget);

      final cta = t.widget<ElevatedButton>(find.byType(ElevatedButton).last);
      expect(cta.onPressed, isNull,
          reason: 'a sentence over a live button is an instruction the user '
              'can ignore');
    });

    testWidgets('selling exactly what is held is not refused', (t) async {
      await _pump(
        t,
        const TradeTicketSheet(tickerPrefill: 'AAPL'),
        sim: SimState(
          portfolio: _portfolio(holdings: [
            _holding(10),
          ]),
        ),
      );
      await t.tap(find.text('SELL'));
      await t.pump();
      await t.enterText(find.byType(TextField).at(1), '10');
      await t.pump();
      expect(find.textContaining('would close that position'), findsNothing);
    });
  });

  test('the section helper cannot tell a resting-order user they have not '
      'traded', () {
    expect(hasAnyRestingOrders(const SimState()), isFalse);
    expect(
        hasAnyRestingOrders(SimState(restingOrders: [_order()])), isFalse,
        reason: 'orders we were never told about do not count');
    expect(
        hasAnyRestingOrders(SimState(
            restingOrdersSupported: true, restingOrders: [_order()])),
        isTrue);
  });
}
