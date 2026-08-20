/// CR129 — wire-contract coverage for `ResolvedCaps`, the server-resolved
/// enforced values stamped onto GET/PATCH /v1/mandate responses.
///
/// Three backend generations exist in the wild and the model must parse all
/// of them without fabricating a value (CR040 degrade-loudly, applied as
/// NULL-over-invented-number):
///   * post-d1d4076d — all seven fields present and non-null;
///   * alpha-2026-08-19-2 (DEF193 only) — `resolved` carries just the two
///     CR101-BE1 caps, the other five must come back null;
///   * pre-DEF193 — no `resolved` key at all, the whole object must be null.
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _mandateJson({Object? resolved = _absent}) {
  final j = <String, dynamic>{'user_id': 'u1'};
  if (!identical(resolved, _absent)) j['resolved'] = resolved;
  return j;
}

const _absent = Object();

void main() {
  test('full 7-field resolved parses with the schema types (3 ints, 4 floats)',
      () {
    final m = UserMandate.fromJson(_mandateJson(resolved: {
      'sector_cap_pct': 40.0,
      'single_name_cap_pct': 3.0,
      'max_open_positions': 35,
      'post_loss_cooldown_hours': 1.0,
      'max_trades_per_day': 4,
      'max_trades_per_week': 12,
      'max_open_risk_pct': 10.5,
    }));
    final r = m.resolved;
    expect(r, isNotNull);
    expect(r!.sectorCapPct, 40.0);
    expect(r.singleNameCapPct, 3.0);
    expect(r.maxOpenPositions, 35);
    expect(r.postLossCooldownHours, 1.0);
    expect(r.maxTradesPerDay, 4);
    expect(r.maxTradesPerWeek, 12);
    expect(r.maxOpenRiskPct, 10.5);
  });

  test(
      'live-Alpha 2-field shape (DEF193, pre-d1d4076d) parses with the other '
      'five null — unknown, never invented', () {
    final m = UserMandate.fromJson(_mandateJson(resolved: {
      'sector_cap_pct': 40.0,
      'single_name_cap_pct': 3.0,
    }));
    final r = m.resolved;
    expect(r, isNotNull);
    expect(r!.sectorCapPct, 40.0);
    expect(r.singleNameCapPct, 3.0);
    expect(r.maxOpenPositions, isNull);
    expect(r.postLossCooldownHours, isNull);
    expect(r.maxTradesPerDay, isNull);
    expect(r.maxTradesPerWeek, isNull);
    expect(r.maxOpenRiskPct, isNull);
  });

  test('absent resolved (pre-DEF193 backend) parses to null', () {
    expect(UserMandate.fromJson(_mandateJson()).resolved, isNull);
    expect(UserMandate.fromJson(_mandateJson(resolved: null)).resolved, isNull);
  });

  test('valueFor maps every PATCH key and rejects unknown keys', () {
    const r = ResolvedCaps(
      sectorCapPct: 40.0,
      singleNameCapPct: 3.0,
      maxOpenPositions: 35,
      postLossCooldownHours: 1.0,
      maxTradesPerDay: 4,
      maxTradesPerWeek: 12,
      maxOpenRiskPct: 10.5,
    );
    expect(r.valueFor('sector_cap_pct'), 40.0);
    expect(r.valueFor('single_name_cap_pct'), 3.0);
    expect(r.valueFor('max_open_positions'), 35);
    expect(r.valueFor('post_loss_cooldown_hours'), 1.0);
    expect(r.valueFor('max_trades_per_day'), 4);
    expect(r.valueFor('max_trades_per_week'), 12);
    expect(r.valueFor('max_open_risk_pct'), 10.5);
    expect(r.valueFor('not_a_field'), isNull);
  });
}
