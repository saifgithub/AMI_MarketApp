/// CR170 Rule 1 and CR171 §1/§5 — the pure rules, at their boundaries.
///
/// These two modules exist because the client has to *predict* what the server
/// will do: CR170's live hint, which is what stops a resting order reading as a
/// broken button, and CR171's two refusals, which the user meets at the tap
/// rather than three seconds later out of a round trip. A prediction that is
/// wrong at a boundary is worse than none, so the boundaries are the tests.
library;

import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/features/sim/short_rules.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CR170 Rule 1 — which side of the market an order waits on', () {
    // The diagonal from the CR's own table: buy-limit and sell-stop are the
    // SAME comparison, as are buy-stop and sell-limit. Get this wrong and the
    // hint tells a user their stop-loss is a take-profit.
    test('buy limit and sell stop both rest below', () {
      expect(restsBelow(side: 'buy', orderType: SimOrderType.limit), isTrue);
      expect(restsBelow(side: 'sell', orderType: SimOrderType.stop), isTrue);
      expect(
          restsBelow(side: 'sell', orderType: SimOrderType.stopLimit), isTrue);
    });

    test('buy stop and sell limit both rest above', () {
      expect(restsBelow(side: 'buy', orderType: SimOrderType.stop), isFalse);
      expect(
          restsBelow(side: 'buy', orderType: SimOrderType.stopLimit), isFalse);
      expect(restsBelow(side: 'sell', orderType: SimOrderType.limit), isFalse);
    });

    test('the trigger is inclusive at the exact touch, on both sides', () {
      // Matches `evaluate_outcomes`' existing `price <= stop` / `price >=
      // target`. The two run in the same sweep, and a user comparing them must
      // not find them disagreeing at the boundary.
      expect(
          isTriggered(
              side: 'buy',
              orderType: SimOrderType.limit,
              named: 190,
              mark: 190),
          isTrue);
      expect(
          isTriggered(
              side: 'sell',
              orderType: SimOrderType.limit,
              named: 210,
              mark: 210),
          isTrue);
      expect(
          isTriggered(
              side: 'buy',
              orderType: SimOrderType.limit,
              named: 190,
              mark: 190.01),
          isFalse);
    });

    test('the named price is the one the type is named by', () {
      expect(
          namedPriceFor(SimOrderType.limit, triggerPrice: 5, limitPrice: 9), 9);
      expect(
          namedPriceFor(SimOrderType.stop, triggerPrice: 5, limitPrice: 9), 5);
      expect(
          namedPriceFor(SimOrderType.stopLimit, triggerPrice: 5, limitPrice: 9),
          5,
          reason: 'a stop-limit triggers on its trigger; the limit is phase two');
      expect(namedPriceFor(SimOrderType.market, limitPrice: 9), isNull);
    });
  });

  group('CR170 — the hint says nothing rather than something wrong', () {
    test('a marketable order fills now', () {
      // A buy limit at or above the market is already through it, so it fills
      // exactly like a market order — same path, same price, same ruling.
      expect(
        predictIntent(
            side: 'buy',
            orderType: SimOrderType.limit,
            triggerPrice: null,
            limitPrice: 200,
            mark: 190),
        OrderIntent.fillsNow,
      );
    });

    test('a resting order rests', () {
      expect(
        predictIntent(
            side: 'buy',
            orderType: SimOrderType.limit,
            triggerPrice: null,
            limitPrice: 180,
            mark: 190),
        OrderIntent.rests,
      );
    });

    test('incomplete input produces no hint at all', () {
      // A hint that fills itself in from half-typed input is worse than a blank
      // line, because the user reads it.
      for (final missing in <Map<String, double?>>[
        {'limit': null, 'mark': 190},
        {'limit': 180, 'mark': null},
        {'limit': 0, 'mark': 190},
        {'limit': 180, 'mark': 0},
      ]) {
        expect(
          predictIntent(
              side: 'buy',
              orderType: SimOrderType.limit,
              triggerPrice: null,
              limitPrice: missing['limit'],
              mark: missing['mark']),
          isNull,
          reason: 'input $missing is not enough to say anything true',
        );
      }
    });

    test('an order type this build does not know produces no hint', () {
      expect(
        predictIntent(
            side: 'buy',
            orderType: SimOrderType.unknown,
            triggerPrice: 1,
            limitPrice: 1,
            mark: 1),
        isNull,
      );
    });
  });

  group('CR170 — wire values round-trip, and an unknown one stays unknown', () {
    test('every known order type survives the round trip', () {
      for (final t in SimOrderType.values) {
        if (t == SimOrderType.unknown) continue;
        expect(simOrderTypeFromWire(t.wire), t);
      }
      for (final t in SimOrderTif.values) {
        if (t == SimOrderTif.unknown) continue;
        expect(simOrderTifFromWire(t.wire), t);
      }
    });

    test('an unrecognised value never lands on market', () {
      // DEF210 — the cheapest-looking fallback is the one that would quietly
      // turn somebody's resting order into an immediate fill in the UI's
      // account of it.
      expect(simOrderTypeFromWire('trailing_stop'), SimOrderType.unknown);
      expect(simOrderTypeFromWire(null), SimOrderType.unknown);
      expect(SimOrderType.unknown.canRest, isFalse);
      expect(simOrderTifFromWire('gtc'), SimOrderTif.unknown);
    });
  });

  group('CR171 §1 — a sell never crosses zero', () {
    test('holding at least the quantity closes, exactly as today', () {
      expect(classifySell(held: 10, quantity: 10), SellIntent.closesLong);
      expect(classifySell(held: 10, quantity: 4), SellIntent.closesLong);
    });

    test('holding nothing opens a short', () {
      expect(classifySell(held: 0, quantity: 10), SellIntent.opensShort);
    });

    test('holding some but not enough is refused, never split', () {
      // Splitting one action into a close plus a short is the P&L-attribution
      // bug class DEF166 and DEF110 have already cost us twice.
      expect(classifySell(held: 4, quantity: 10), SellIntent.crossesZero);
      expect(closeableQuantity(4), 4,
          reason: 'the refusal offers the exact quantity that would close');
    });
  });

  group('CR171 §5 — the bracket inverts on a short', () {
    test('a short stop belongs above entry', () {
      expect(stopIsWrongSide(isShort: true, entry: 100, stop: 90), isTrue);
      expect(stopIsWrongSide(isShort: true, entry: 100, stop: 110), isFalse);
      // At entry is also wrong: a stop that fires the instant you open is not a
      // stop, it is a cancellation.
      expect(stopIsWrongSide(isShort: true, entry: 100, stop: 100), isTrue);
    });

    test('a long stop belongs below entry — the mirror', () {
      expect(stopIsWrongSide(isShort: false, entry: 100, stop: 110), isTrue);
      expect(stopIsWrongSide(isShort: false, entry: 100, stop: 90), isFalse);
    });

    test('a short target belongs below entry', () {
      expect(targetIsWrongSide(isShort: true, entry: 100, target: 110), isTrue);
      expect(
          targetIsWrongSide(isShort: true, entry: 100, target: 90), isFalse);
    });

    test('an unset field is not a violation', () {
      // Reporting one as a violation trains the user to read past the panel,
      // which is the same cost as no panel at all.
      expect(stopIsWrongSide(isShort: true, entry: 100, stop: null), isNull);
      expect(stopIsWrongSide(isShort: true, entry: null, stop: 90), isNull);
      expect(targetIsWrongSide(isShort: true, entry: 0, target: 90), isNull);
    });
  });
}
