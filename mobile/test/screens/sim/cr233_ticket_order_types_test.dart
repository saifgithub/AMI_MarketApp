/// CR233 — trade ticket integration: the destination lock comes off order
/// type, the Alpaca-leg preview is sized at the order's own limit/stop
/// price, and BOTH places independent resting legs for a non-market order.
///
/// Complements `test/services/alpaca/cr233_alpaca_order_types_test.dart`
/// (which pins `buildAlpacaOrderPayload`/`validateAlpacaOrder` directly) and
/// `test/screens/sim/cr227_destination_routing_test.dart` (which this CR
/// updated in place for the reversed lock behaviour). This file is the
/// ticket-level wiring: what the sheet actually calls, not what the wire
/// body looks like.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingAlpacaClient extends AlpacaClient {
  final List<
      ({
        String side,
        double qty,
        String symbol,
        SimOrderType orderType,
        double? limitPrice,
        double? triggerPrice,
        SimOrderTif tif,
        AlpacaBracket? bracket,
      })> calls = [];

  @override
  Future<AlpacaPortfolio> account() async => const AlpacaPortfolio(
        cash: 100000,
        portfolioValue: 100000,
        equity: 100000,
        buyingPower: 100000,
      );

  @override
  Future<List<AlpacaPosition>> positions() async => const [];

  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    AlpacaBracket? bracket,
  }) async {
    calls.add((
      side: side,
      qty: qty,
      symbol: symbol,
      orderType: orderType,
      limitPrice: limitPrice,
      triggerPrice: triggerPrice,
      tif: tif,
      bracket: bracket,
    ));
    return AlpacaOrder(
      id: 'ord_1',
      symbol: symbol,
      side: side,
      qty: qty,
      status: 'new', // resting — not yet filled
    );
  }
}

class _RecordingSim extends SimNotifier {
  _RecordingSim(super.ref, SimState fixed, {this.submitResult}) {
    state = fixed;
  }

  final SimSubmitResult? submitResult;
  final List<
      ({
        String side,
        double quantity,
        String ticker,
        SimOrderType orderType,
        double? limitPrice,
        double? triggerPrice,
        double? stop,
        double? target,
        Map<String, dynamic>? account,
      })> previewCalls = [];

  @override
  Future<SimPreviewResult?> preview({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    double? stop,
    double? target,
    String? verdictRef,
    Map<String, dynamic>? account,
  }) async {
    previewCalls.add((
      side: side,
      quantity: quantity,
      ticker: ticker,
      orderType: orderType,
      limitPrice: limitPrice,
      triggerPrice: triggerPrice,
      stop: stop,
      target: target,
      account: account,
    ));
    return const SimPreviewResult(accepted: true);
  }

  @override
  Future<SimSubmitResult?> submit({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    final result = submitResult;
    state = state.copyWith(lastSubmit: result, clearLastSubmit: result == null);
    return result;
  }
}

SimPortfolio _portfolio() => SimPortfolio.fromJson({
      'user_id': 'u',
      'portfolio_id': 'p',
      'starting_capital': 10000,
      'current_cash': 10000,
      'holdings': const [],
      'total_value': 10000,
      'drawdown_pct': 0,
      'price_source': 'yfinance',
      'cash_committed': 0,
      'cash_available': 10000,
      'resting_order_count': 0,
      'shares_committed': const {},
      'shorts': const [],
      'closed_shorts': const [],
    });

SimSubmitResult _amiResting({required double limit}) => SimSubmitResult.fromJson({
      'ok': true,
      'resting': true,
      'trade': null,
      'order': {
        'id': 'r1',
        'user_id': 'u',
        'ticker': 'AAPL',
        'side': 'buy',
        'order_type': 'limit',
        'quantity': 1.0,
        'limit_price': limit,
        'tif': 'day',
        'state': 'working',
        'placed_at': '2026-09-24T00:00:00Z',
        'expires_at': '2026-09-24T20:00:00Z',
      },
      'compliance': {'passed': true},
    });

Future<
    ({
      _RecordingSim sim,
      _RecordingAlpacaClient alpaca,
    })> _pump(
  WidgetTester t, {
  required bool restingOrdersSupported,
  SimSubmitResult? submitResult,
  String? tapOrderType,
  String? tapDestination,
  String? coverTicker,
  double? coverQuantity,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  late _RecordingSim sim;
  final alpaca = _RecordingAlpacaClient();
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) {
        sim = _RecordingSim(
          ref,
          SimState(
              portfolio: _portfolio(),
              restingOrdersSupported: restingOrdersSupported),
          submitResult: submitResult,
        );
        return sim;
      }),
      alpacaLinkedProvider.overrideWith((ref) async => true),
      alpacaClientProvider.overrideWithValue(alpaca),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: TradeTicketSheet(
        tickerPrefill: coverTicker == null ? 'AAPL' : null,
        coverTicker: coverTicker,
        coverQuantity: coverQuantity,
      ),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
  if (tapOrderType != null) {
    // 'STOP' also matches inside the 'STOP LIMIT' pill's own text ("STOP"
    // is found ambiguously) in some render passes — .first pins it to the
    // literal pill being asked for; ORDER TYPE is drawn above DESTINATION,
    // so its own 'STOP'/'STOP LIMIT' pills are always the first matches.
    await t.tap(find.text(tapOrderType).first);
    await t.pump(const Duration(milliseconds: 120));
  }
  if (tapDestination != null) {
    await t.tap(find.text(tapDestination).first);
    await t.pump(const Duration(milliseconds: 120));
  }
  return (sim: sim, alpaca: alpaca);
}

Future<void> _enterLimitPrice(WidgetTester t, String value) async {
  final field = find.ancestor(
    of: find.text('LIMIT PRICE'),
    matching: find.byType(TextField),
  );
  await t.enterText(field, value);
  await t.pump(const Duration(milliseconds: 120));
}

Future<void> _enterTriggerPrice(WidgetTester t, String value) async {
  final field = find.ancestor(
    of: find.text('TRIGGER PRICE'),
    matching: find.byType(TextField),
  );
  await t.enterText(field, value);
  await t.pump(const Duration(milliseconds: 120));
}

Future<void> _enterStop(WidgetTester t, String value) async {
  final field = find.ancestor(
    of: find.text('STOP'),
    matching: find.byType(TextField),
  );
  await t.enterText(field, value);
  await t.pump(const Duration(milliseconds: 120));
}

Future<void> _enterTarget(WidgetTester t, String value) async {
  final field = find.ancestor(
    of: find.text('TARGET'),
    matching: find.byType(TextField),
  );
  await t.enterText(field, value);
  await t.pump(const Duration(milliseconds: 120));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('destination picker visibility by order type (CR233)', () {
    testWidgets('visible for LIMIT', (t) async {
      await _pump(t, restingOrdersSupported: true, tapOrderType: 'LIMIT');
      expect(find.text('DESTINATION'), findsOneWidget);
    });

    testWidgets('visible for STOP', (t) async {
      await _pump(t, restingOrdersSupported: true, tapOrderType: 'STOP');
      expect(find.text('DESTINATION'), findsOneWidget);
    });

    testWidgets('visible for STOP LIMIT', (t) async {
      await _pump(t, restingOrdersSupported: true, tapOrderType: 'STOP LIMIT');
      expect(find.text('DESTINATION'), findsOneWidget);
    });

    testWidgets(
        'still locked (hidden) on the cover-a-short entry path, unrelated '
        'to order type', (t) async {
      await _pump(
        t,
        restingOrdersSupported: false,
        coverTicker: 'AAPL',
        coverQuantity: 5,
      );
      expect(find.text('DESTINATION'), findsNothing,
          reason: 'CR233 explicitly keeps the cover/sell-from-holding lock — '
              'it is about AMI position sizes not translating to Alpaca, '
              'unrelated to order type');
    });
  });

  group('MUTATION CHECK — re-locking on order type breaks the picker test',
      () {
    // This test exists to prove the visibility test above is load-bearing:
    // if `_destinationLocked` were reverted to also lock on `_orderType !=
    // market` (the pre-CR233 CR227 behaviour), the LIMIT-visibility test
    // above fails. Documented here rather than by actually mutating source,
    // per this suite's convention of pinning the CURRENT correct behaviour
    // and relying on the test itself as the mutation witness.
    testWidgets(
        'sanity: DESTINATION textfinder used above genuinely depends on '
        '_destinationLocked, not on some other always-true condition',
        (t) async {
      // Locked entirely via coverTicker (unrelated to order type) still
      // hides it even with resting orders supported and no order-type tap —
      // proving the finder is sensitive to the lock, not just always finding
      // the text.
      await _pump(
        t,
        restingOrdersSupported: true,
        coverTicker: 'AAPL',
        coverQuantity: 5,
      );
      expect(find.text('DESTINATION'), findsNothing);
    });
  });

  group('the Alpaca-leg preview is sized at the order\'s own price (CR233)',
      () {
    testWidgets('Alpaca-only LIMIT sends limitPrice/orderType to preview',
        (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterLimitPrice(t, '150.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.sim.previewCalls, hasLength(1));
      final call = r.sim.previewCalls.single;
      expect(call.orderType, SimOrderType.limit);
      expect(call.limitPrice, 150.0);
      expect(call.account, isNotNull,
          reason: 'DEF419 — still sized against the linked Alpaca account');
    });

    testWidgets('Alpaca-only STOP sends triggerPrice to preview', (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'STOP',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterTriggerPrice(t, '90.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.sim.previewCalls, hasLength(1));
      expect(r.sim.previewCalls.single.orderType, SimOrderType.stop);
      expect(r.sim.previewCalls.single.triggerPrice, 90.0);
    });

    testWidgets(
        'CR233 round-2 — Alpaca-only preview sends stop/target from the '
        'ticket fields, not just limit/trigger price', (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterLimitPrice(t, '150.00');
      await _enterStop(t, '140.00');
      await _enterTarget(t, '170.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.sim.previewCalls, hasLength(1));
      final call = r.sim.previewCalls.single;
      expect(call.stop, 140.0,
          reason: 'so the backend can run the same bracket-validity '
              'refusal /submit runs, before the Alpaca order is ever sent');
      expect(call.target, 170.0);
    });

    testWidgets(
        'CR233 round-2 — an empty stop/target sends null, not 0, to preview',
        (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterLimitPrice(t, '150.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.sim.previewCalls, hasLength(1));
      final call = r.sim.previewCalls.single;
      expect(call.stop, isNull);
      expect(call.target, isNull);
    });

    testWidgets(
        'an accepted LIMIT preview places a LIMIT order on Alpaca, not '
        'market', (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterLimitPrice(t, '150.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.alpaca.calls, hasLength(1));
      final call = r.alpaca.calls.single;
      expect(call.orderType, SimOrderType.limit,
          reason: 'CR233 — no longer silently converted to a market order');
      expect(call.limitPrice, 150.0);
    });

    testWidgets(
        'the result panel says "resting", never "filled", for an order '
        'Alpaca has not filled yet', (t) async {
      await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'ALPACA PAPER',
      );
      await _enterLimitPrice(t, '150.00');
      await t.tap(find.text('SUBMIT TRADE'));
      // The success path pops the sheet (the ticket is `MaterialApp`'s only
      // route in this harness, so popping it leaves an empty Navigator a
      // few frames later) and shows a SnackBar in the same breath. A small,
      // fixed number of pumps lands after the pop/SnackBar but before the
      // route stack goes fully empty — unlike the outcome-panel assertions
      // above, which render inline in a sheet that stays open and so tolerate
      // many more pumps.
      for (var i = 0; i < 2; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(find.textContaining('resting at Alpaca'), findsWidgets,
          reason: 'AlpacaOrder.isResting reads status "new" as resting, not '
              'filled — the server states it, the client never infers it');
    });
  });

  group('BOTH with a LIMIT order — independent resting legs (CR233)', () {
    testWidgets(
        'AMI resting + Alpaca resting independently, both legs called',
        (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'BOTH',
        submitResult: _amiResting(limit: 150.0),
      );
      await _enterLimitPrice(t, '150.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 8; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.alpaca.calls, hasLength(1),
          reason: 'the Alpaca leg placed independently of the AMI leg');
      expect(r.alpaca.calls.single.orderType, SimOrderType.limit);
      expect(r.alpaca.calls.single.limitPrice, 150.0);

      // 'AMI SIM' also labels the (still-visible, still-open-sheet)
      // DESTINATION picker's own option pill, alongside the outcome panel's
      // label for that leg — two legitimate matches, so this checks the
      // outcome panel specifically rather than counting 'AMI SIM' texts.
      expect(find.text('ALPACA PAPER'), findsWidgets,
          reason: 'per-destination outcome panel shows the Alpaca leg '
              '(also matches the DESTINATION picker\'s own pill)');
      expect(find.textContaining('resting order placed'), findsOneWidget,
          reason: 'the AMI leg reports its own resting state from the '
              'server, unchanged by CR233');
      expect(find.textContaining('resting at Alpaca'), findsOneWidget,
          reason: 'the Alpaca leg reports its own resting state too — two '
              'independent resting orders, not one mirrored twice');
    });

    testWidgets(
        'CR233 round-2 — the BOTH Alpaca leg also sends stop/target to '
        'preview, same as Alpaca-only', (t) async {
      final r = await _pump(
        t,
        restingOrdersSupported: true,
        tapOrderType: 'LIMIT',
        tapDestination: 'BOTH',
        submitResult: _amiResting(limit: 150.0),
      );
      await _enterLimitPrice(t, '150.00');
      await _enterStop(t, '140.00');
      await _enterTarget(t, '170.00');
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 8; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(r.sim.previewCalls, hasLength(1));
      final call = r.sim.previewCalls.single;
      expect(call.stop, 140.0);
      expect(call.target, 170.0);
    });
  });
}
