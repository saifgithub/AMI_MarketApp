/// DEF437 — `UserMandate.creditBalance`/`creditAllowance`/`roomCost` must
/// stay UNKNOWN (null) when the server sends a missing/null value, never
/// fall back to a fabricated number. Before this fix a missing
/// `credit_balance` silently rendered as `75` — a balance the user never
/// had, and the exact DEF059/CR040 "confident fake" class this codebase's
/// degrade-loudly rule exists to catch.
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _mandateJson(Map<String, dynamic> extra) =>
    {'user_id': 'u1', ...extra};

void main() {
  group('DEF437 — credit_balance', () {
    test('a missing credit_balance key parses as null, not 75', () {
      final m = UserMandate.fromJson(_mandateJson({}));
      expect(m.creditBalance, isNull);
    });

    test('an explicit null credit_balance parses as null, not 75', () {
      final m = UserMandate.fromJson(_mandateJson({'credit_balance': null}));
      expect(m.creditBalance, isNull);
    });

    test('a real credit_balance of 0 is 0, not null and not 75', () {
      final m = UserMandate.fromJson(_mandateJson({'credit_balance': 0}));
      expect(m.creditBalance, 0);
    });

    test('a real credit_balance is parsed verbatim', () {
      final m = UserMandate.fromJson(_mandateJson({'credit_balance': 63}));
      expect(m.creditBalance, 63);
    });
  });

  group('DEF437 — creditAllowance / roomCost', () {
    test('missing credit_allowance and room_cost parse as null, not 0', () {
      final m = UserMandate.fromJson(_mandateJson({}));
      expect(m.creditAllowance, isNull);
      expect(m.roomCost, isNull);
    });

    test('real zero values are 0, distinguishable from unknown', () {
      final m = UserMandate.fromJson(
          _mandateJson({'credit_allowance': 0, 'room_cost': 0}));
      expect(m.creditAllowance, 0);
      expect(m.roomCost, 0);
    });

    test('real non-zero values parse verbatim', () {
      final m = UserMandate.fromJson(
          _mandateJson({'credit_allowance': 200, 'room_cost': 8}));
      expect(m.creditAllowance, 200);
      expect(m.roomCost, 8);
    });
  });
}
