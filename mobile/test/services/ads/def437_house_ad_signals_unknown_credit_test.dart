/// DEF437 — `HouseAdSignals.fromMandate` must fail CLOSED on an unknown
/// credit field (null `creditBalance`/`creditAllowance`/`roomCost`), never
/// read the absence as 0 (which would fire every credit-usage signal at
/// once) or as the old fabricated 75 (which would suppress them all
/// incorrectly). Ads targeting off a number the client doesn't actually have
/// is exactly the class of confident-fake CLAUDE.md's degrade-loudly rule
/// forbids.
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:flutter_test/flutter_test.dart';

UserMandate _mandateFromJson(Map<String, dynamic> extra) =>
    UserMandate.fromJson({'user_id': 'u1', 'plan': 'floor_pass', ...extra});

void main() {
  group('DEF437 — HouseAdSignals.fromMandate fails closed on unknown credits', () {
    test('unknown credit_balance never fires outOfFreeOneOnOnes', () {
      final m = _mandateFromJson({}); // no credit_balance key at all
      expect(m.creditBalance, isNull);
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.outOfFreeOneOnOnes, isFalse);
    });

    test('unknown credit_balance never fires usedFreeRoom even with a known room_cost', () {
      final m = _mandateFromJson({'room_cost': 8});
      expect(m.creditBalance, isNull);
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.usedFreeRoom, isFalse);
    });

    test('unknown room_cost never fires usedFreeRoom even with a known balance', () {
      final m = _mandateFromJson({'credit_balance': 0});
      expect(m.roomCost, isNull);
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.usedFreeRoom, isFalse);
    });

    test('unknown credit_allowance never fires nearCreditCap even with a known balance', () {
      final m = _mandateFromJson({'credit_balance': 1});
      expect(m.creditAllowance, isNull);
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.nearCreditCap, isFalse);
    });

    test('a genuinely exhausted balance (0) still fires outOfFreeOneOnOnes once known', () {
      final m = _mandateFromJson({'credit_balance': 0});
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.outOfFreeOneOnOnes, isTrue);
    });

    test('a genuine below-room-cost balance still fires usedFreeRoom once both are known', () {
      final m = _mandateFromJson({'credit_balance': 2, 'room_cost': 8});
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.usedFreeRoom, isTrue);
    });

    test('a genuine near-cap balance still fires nearCreditCap once both are known', () {
      final m = _mandateFromJson({'credit_balance': 10, 'credit_allowance': 60});
      final signals = HouseAdSignals.fromMandate(m);
      expect(signals.nearCreditCap, isTrue);
    });
  });
}
