// CR135 — wire mapping for the notification centre + the DEF210
// null-on-unknown contract (the backend ships by rsync days ahead of the
// store build, so a type this client predates must degrade, not throw).

import 'package:ami_trade/models/app_notification.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('every member round-trips through its own wire value', () {
    // Swept rather than listed, so a future member is covered the day it
    // is added. Backend↔Dart parity is pytest's job
    // (test_cr135_notification_type_parity.py); this pins Dart-internal
    // consistency between `wire` and `fromWire`.
    for (final type in NotificationType.values) {
      expect(NotificationTypeJson.fromWire(type.wire), type,
          reason: type.name);
    }
  });

  test('an unknown wire value stays null and is never coerced', () {
    expect(NotificationTypeJson.fromWire('never_heard_of_it'), isNull);
    expect(NotificationTypeJson.fromWire(null), isNull);
  });

  test('a row with an unknown type still parses and reads generically', () {
    final row = AppNotification.fromJson(const {
      'id': '11111111-1111-1111-1111-111111111111',
      'type': 'brand_new_type',
      'title': 'Something new',
      'body': 'A body.',
      'deep_link': {'route': 'open_holding_detail', 'ticker': 'AAPL'},
      'source_ref': null,
      'read_at': null,
      'created_at': '2026-08-20T10:00:00Z',
    });
    expect(row.knownType, isNull);
    expect(row.type, 'brand_new_type');
    expect(row.isUnread, isTrue);
    // The flat deep_link shape parses (notification_models.dart accepts
    // flat and nested); dispatch stays wired for unknown row types.
    expect(row.deepLink.route, 'open_holding_detail');
    expect(row.deepLink.params['ticker'], 'AAPL');
  });

  test('read stamps parse and flip isUnread', () {
    final row = AppNotification.fromJson(const {
      'id': '22222222-2222-2222-2222-222222222222',
      'type': 'price_alert',
      'title': 'AAPL crossed 240',
      'body': 'Above your 240.00 threshold.',
      'deep_link': {
        'route': 'open_holding_detail',
        'params': {'ticker': 'AAPL'},
      },
      'read_at': '2026-08-20T11:00:00Z',
      'created_at': '2026-08-20T10:00:00Z',
    });
    expect(row.knownType, NotificationType.priceAlert);
    expect(row.isUnread, isFalse);
    // Nested deep_link shape parses too.
    expect(row.deepLink.params['ticker'], 'AAPL');
  });

  test('a preference row with no stored toggle reads enabled', () {
    final p = NotificationPreference.fromJson(const {
      'type': 'daily_reminder',
      'enabled': true,
      'updated_at': null,
    });
    expect(p.enabled, isTrue);
    expect(p.updatedAt, isNull);
    expect(p.knownType, NotificationType.dailyReminder);
  });
}
