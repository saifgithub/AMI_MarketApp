/// CR186 — the waiting-order card says what the order actually is.
///
/// The card used to render side, quantity, ticker, one price and a state chip.
/// A **buy limit at $190 and a buy stop at $190 are opposite orders** — one
/// waits for a fall, the other for a rise — and both produced the identical
/// card, so the fact that distinguishes them was stated once in the ticket at
/// placement and never again. A stop-limit was worse: only its trigger showed,
/// and the limit price, the number that decides whether it fills at all, was
/// invisible everywhere in the app once the sheet closed.
///
/// Every test below asserts on rendered text rather than on a helper's return
/// value. Both facts already existed on the model — `orderType`, `limitPrice`,
/// `expiresAt` and `tif` were all parsed from the day CR170-FE landed and none
/// of them reached a pixel — so a test that stops at the model would have
/// passed against the defect.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/widgets/sim/resting_orders_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

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

SimRestingOrder _order({
  String state = 'working',
  String orderType = 'limit',
  String side = 'buy',
  double? limitPrice = 190,
  double? triggerPrice,
  String tif = 'day',
  DateTime? expiresAt,
  DateTime? retiredAt,
  String? cancelReason,
  double? distancePct = -2.5,
}) =>
    SimRestingOrder.fromJson({
      'id': 'o1',
      'ticker': 'AAPL',
      'side': side,
      'quantity': 10,
      'order_type': orderType,
      'state': state,
      'tif': tif,
      'limit_price': limitPrice,
      'trigger_price': triggerPrice,
      'expires_at': expiresAt?.toIso8601String(),
      'retired_at': retiredAt?.toIso8601String(),
      'cancel_reason': cancelReason,
      'distance_pct': distancePct,
      'last_seen_price': distancePct == null ? null : 195.0,
    });

Future<void> _pump(WidgetTester t, List<SimRestingOrder> orders) async {
  await t.binding.setSurfaceSize(const Size(390, 900));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) => _FixedSim(
            ref,
            SimState(
              portfolio: _portfolio(),
              restingOrders: orders,
              restingOrdersSupported: true,
            ),
          )),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(
        body: SingleChildScrollView(child: RestingOrdersSection()),
      ),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the card names the order type', () {
    testWidgets('a buy limit says LIMIT and waits for a FALL', (t) async {
      await _pump(t, [_order(orderType: 'limit', limitPrice: 190)]);
      expect(find.text('LIMIT'), findsOneWidget);
      expect(find.textContaining('waits for a fall to \$190.00'), findsOneWidget);
    });

    testWidgets('a buy stop at the SAME price waits for a RISE', (t) async {
      // The defect in one assertion: identical side, identical price, opposite
      // order. These two cards were byte-identical.
      await _pump(t, [
        _order(orderType: 'stop', limitPrice: null, triggerPrice: 190),
      ]);
      expect(find.text('STOP'), findsOneWidget);
      expect(find.textContaining('waits for a rise to \$190.00'), findsOneWidget);
    });

    testWidgets('a sell stop waits for a fall — the diagonal holds', (t) async {
      await _pump(t, [
        _order(side: 'sell', orderType: 'stop', limitPrice: null,
            triggerPrice: 90),
      ]);
      expect(find.textContaining('waits for a fall to \$90.00'), findsOneWidget);
    });

    testWidgets('a sell limit waits for a rise', (t) async {
      await _pump(t, [_order(side: 'sell', orderType: 'limit', limitPrice: 210)]);
      expect(find.textContaining('waits for a rise to \$210.00'), findsOneWidget);
    });

    testWidgets('an unrecognised type names no type at all', (t) async {
      // From a newer server. Naming a type the order does not have is worse
      // than naming none — the two behave oppositely (DEF210's shape).
      await _pump(t, [_order(orderType: 'trailing_stop')]);
      expect(find.text('ORDER'), findsOneWidget);
      expect(find.text('LIMIT'), findsNothing);
      expect(find.text('STOP'), findsNothing);
    });
  });

  group('a stop-limit shows the price that decides whether it fills', () {
    testWidgets('untriggered: both phases, in order', (t) async {
      await _pump(t, [
        _order(side: 'sell', orderType: 'stop_limit', triggerPrice: 90,
            limitPrice: 88),
      ]);
      expect(find.text('STOP-LIMIT'), findsOneWidget);
      expect(
        find.textContaining('waits for a fall to \$90.00'),
        findsOneWidget,
      );
      expect(find.textContaining('then a limit at \$88.00'), findsOneWidget,
          reason: 'a gap through \$88 rests forever and never fills — the '
              'classic stop-limit failure. The user cannot see it coming if '
              'the limit price is never rendered');
    });

    testWidgets('triggered: it stops describing a trigger it already hit',
        (t) async {
      await _pump(t, [
        _order(state: 'triggered', side: 'sell', orderType: 'stop_limit',
            triggerPrice: 90, limitPrice: 88),
      ]);
      expect(find.textContaining('triggered — now a limit at \$88.00'),
          findsOneWidget);
      expect(find.textContaining('waits for a fall'), findsNothing,
          reason: 'it is no longer waiting for the trigger; saying so would be '
              'the one actively false sentence on the card');
    });
  });

  group('the card says when the order dies', () {
    testWidgets('a DAY order shows the session close, not a day count',
        (t) async {
      await _pump(t, [
        _order(expiresAt: DateTime.now().add(const Duration(hours: 5))),
      ]);
      expect(find.textContaining('expires today'), findsOneWidget);
    });

    testWidgets('a 90-day order shows the days left', (t) async {
      await _pump(t, [
        _order(tif: 'gtd_90',
            expiresAt: DateTime.now().add(const Duration(days: 87, hours: 2))),
      ]);
      expect(find.textContaining('expires in 87d'), findsOneWidget);
    });

    testWidgets('and the two are visibly different orders', (t) async {
      // The whole point: before this, a DAY order and a 90-day order rendered
      // identically, so "why did my order disappear overnight" had no answer
      // anywhere on the screen.
      await _pump(t, [
        _order(expiresAt: DateTime.now().add(const Duration(hours: 5))),
      ]);
      expect(find.textContaining('expires in'), findsNothing);
    });

    testWidgets('no expiry from the server ⇒ no expiry line, not a guess',
        (t) async {
      await _pump(t, [_order(expiresAt: null)]);
      expect(find.textContaining('expires'), findsNothing);
    });
  });

  group('a closed order is dated', () {
    testWidgets('a refusal shows how long ago it happened', (t) async {
      await _pump(t, [
        _order(state: 'rejected',
            retiredAt: DateTime.now().subtract(const Duration(hours: 3)),
            cancelReason: 'AAPL is on your blocklist'),
      ]);
      expect(find.textContaining('3h ago'), findsOneWidget);
      // The reason still renders verbatim — a non-null cancel_reason means the
      // SYSTEM refused, and that sentence is the whole teaching value.
      expect(find.text('AAPL is on your blocklist'), findsOneWidget);
    });

    testWidgets('a fill shows its price and its age together', (t) async {
      await _pump(t, [
        SimRestingOrder.fromJson({
          'id': 'o2',
          'ticker': 'AAPL',
          'side': 'buy',
          'quantity': 10,
          'order_type': 'limit',
          'state': 'filled',
          'tif': 'day',
          'limit_price': 190.0,
          'fill_price': 190.0,
          'retired_at':
              DateTime.now().subtract(const Duration(minutes: 20)).toIso8601String(),
        }),
      ]);
      expect(find.textContaining('@ \$190.00'), findsWidgets);
      expect(find.textContaining('20m ago'), findsOneWidget);
    });

    testWidgets('a server with no retired_at dates nothing rather than lying',
        (t) async {
      await _pump(t, [_order(state: 'cancelled', retiredAt: null)]);
      expect(find.textContaining('ago'), findsNothing);
      expect(find.textContaining('cancelled'), findsOneWidget);
    });

    testWidgets('a closed order names no expiry and offers no cancel',
        (t) async {
      await _pump(t, [
        _order(state: 'expired',
            expiresAt: DateTime.now().add(const Duration(days: 40)),
            retiredAt: DateTime.now().subtract(const Duration(days: 2))),
      ]);
      expect(find.textContaining('expires'), findsNothing);
      expect(find.text('CANCEL ORDER'), findsNothing);
      expect(find.textContaining('2d ago'), findsOneWidget);
    });
  });
}
